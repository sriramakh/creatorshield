# Architecture

## Overview

```
Browser (Next.js 16, React 19, Tailwind 4)
   │  multipart upload / JSON polling / video range requests
   ▼
FastAPI (backend/app/api) ──► PostgreSQL (analyses, findings)
   │ enqueue                   ▲
   ▼                           │ status + results
Redis ──► RQ SimpleWorker (backend/app/worker.py)
            │
            ├─ media/        ffprobe validation → audio (16 kHz WAV) → faster-whisper transcript
            │                → silencedetect (non-speech sound) → scene-aware frame sampling
            │                → Tesseract OCR
            ├─ analysis/deterministic.py   rule-based checks (no AI)
            ├─ analysis/prompt.py          provider-neutral prompt with injection defences
            ├─ analysis/providers/*        openai | anthropic | mock
            ├─ analysis/validation.py      server-side validation of AI output
            ├─ analysis/merge.py           fold corroborating rule findings into AI findings
            ├─ provenance/                 cues, catalogue fingerprints, rights ledger,
            │                              optional music / web / YouTube lookups, evidence pack
            └─ analysis/risk.py            heuristic risk indicator
   Local storage (backend/var/storage/analyses/<id>/…) — S3-style keys
```

## Request / job flow

1. `POST /api/analyses` streams the file to storage (size-capped), probes it with
   ffprobe (container whitelist, video stream, duration ≤ `MAX_DURATION_SECONDS` (30 min) + 0.5 s tolerance),
   stores metadata, and enqueues `process_analysis(id)`. Returns `202`.
   Before extraction the worker hashes the original (`media_info.original_sha256`) and, for files above
   1080p or 8 Mbps, makes an H.264 1080p working copy (`app/media/working_copy.py`, stage `optimizing_video`),
   deletes the original and analyses the copy. If encoding fails it falls back to the original with a note.
2. The worker updates `stage`/`progress` as it goes; the UI polls `GET /api/analyses/{id}`.
3. Extraction output (transcript segments `T#`, frames `F#`, OCR `O#`, audio intervals)
   is stored as JSON on the analysis; frame JPEGs stay in storage for the UI.
4. Deterministic checks always run. The AI provider runs if configured; if it is
   missing or fails, the analysis still completes with rule-based findings and a
   clear `ai_status` (`skipped` / `failed`) shown in UI and report.
5. AI output is validated, merged with corroborating rule findings, sorted, scored
   and persisted. The schema-valid raw AI output is kept in `analyses.ai_output` for audit.
6. Reports: `GET …/report.html` (self-contained, printable, CSP-locked) and `…/report.json`.

## Connected accounts & imports (`backend/app/integrations/`)

```
Browser ──POST /api/connections/{p}/authorize──► API ──state (+PKCE verifier) → Redis (10 min, single-use)
   └──► platform consent page ──► GET /api/connections/{p}/callback ──► code → token exchange
        ──► tokens Fernet-encrypted in platform_connections ──► 303 → /connections?connected=p
POST /api/analyses/import {connection_id, url|media_id}
   ──► ownership check via platform API (IG: post in the account's own media; YT: channelId match)
   ──► Analysis(source, analysis_mode, connection_id) ──► worker: importer.prepare_import()
```

| Module | Role |
|---|---|
| `common.py` | HTTP client factory, error mapping, Fernet token encryption, OAuth state + PKCE |
| `instagram.py` | Instagram API with Instagram Login: authorize, short→long-lived token (60 d), refresh, `/me`, `/<IG_ID>/media`, `/<media_id>` |
| `youtube.py` | Google OAuth (code + PKCE, offline), refresh, revoke; Data API v3 channels / playlistItems / videos / captions; SRT + ISO-8601 parsing |
| `urls.py` | Strict link parsing (host allow-lists; YouTube 11-char IDs; IG shortcodes) |
| `connections.py` | Connect/refresh/disconnect, media listing, ownership-checked resolution |
| `importer.py` | Worker side: IG download (HTTPS + CDN host allow-list re-checked on every redirect, size cap, trim to `IMPORT_MAX_SECONDS`, 30 min) or caption+thumbnail fallback; YT metadata + captions |

Analysis modes: `full_video` (upload or IG file), `caption_thumbnail` (IG withheld the file),
`metadata_only` (YouTube), `cross_checked` (the creator attaches their own file to an imported
post). The mode is passed to the prompt (the model is told what it does *not* have), adds a
"not analysed" item for limited modes, mode-specific limitations, UI banners and report banners.
Timestamps are dropped when duration is unknown or evidence is a thumbnail.

`cross_checked` does not download platform video or audio. The worker refreshes the post's
official caption, duration and (YouTube) caption track, runs the normal extraction pipeline on
the file the creator supplied, then compares duration, caption-track wording and — for Instagram —
cover text. An Instagram `media_url` withhold is recorded as a licensing signal and compared
with non-speech audio in the file. It is not a song identification and not a Content ID result.

## Provenance & rights (`backend/app/provenance/`)

Copyright review without access to Content ID / Rights Manager. Each check produces
**facts** stored in `analyses.provenance`; `findings.build()` turns facts + the rights
ledger into findings (source `provenance`) and coverage lines (`own / covered /
expired / missing / info / review`). Because derivation is pure, a ledger change or a
new lookup re-derives findings and the risk score without re-running anything paid.

```
worker (after OCR, stage "provenance")
  ├─ cues.py         @handles + broadcaster/studio/label names + copyright notices in OCR   free
  ├─ fingerprint.py  2 fps frame hashes (17×16 edge-masked dHash, mirror-aware)
  │                  + Chromaprint raw audio (fpcalc)                                      free
  ├─ catalogue.py    save fingerprint; compare with catalogue (offset-aligned matching)     free
  ├─ music.py        song ID on detected music only (≤2 × 12 s clips)          paid, opt-in, capped
  └─ web.py          reverse image search on ≤4 cue frames (Google Vision)      paid, opt-in, capped
on demand (API)
  ├─ youtube_search.py  search.list by keywords → thumbnail hash vs frame hashes   free, quota-capped
  ├─ lookups/web, lookups/music, recheck-rights
  └─ evidence_pack.py   zip: report, manifest (SHA-256, matches, coverage), ledger records + proofs,
                        dispute-note draft
budget.py: every paid call recorded in paid_lookups with an estimated cost; a call that
would exceed PAID_LOOKUPS_MONTHLY_BUDGET_USD is skipped; identical inputs are served from cache.
```

| Table | Purpose |
|---|---|
| `rights_records` | Ledger: `own_channel`, `creator_permission`, `music_license`, `footage_license`, `brand_agreement`; match terms (handles, names, labels, domains), platforms, client, validity, reference, optional proof file (PDF/PNG/JPEG, magic-byte checked) |
| `media_fingerprints` | Frame hashes + audio fingerprint per reviewed video (`source=analysis`) or indexed past post (`source=catalogue`), owner/client label. Kept `CATALOGUE_RETENTION_DAYS` (YouTube imports ≤ 30 days); deleted with an explicit analysis delete or a disconnect |
| `paid_lookups` | Paid-call log, response cache and monthly budget |

Matching rules worth knowing:
- Frames with few edges (black, solid colour, plain text-on-colour backgrounds) carry
  little information; the hash only compares real edges, so template "quote" reels don't
  all match each other. Video matches need ≥ 3 s of frames at a **consistent time offset**.
- Audio matches use bit-error rate on Chromaprint values (≤ 0.35; unrelated audio ≈ 0.5),
  ignoring static stretches (silence, held tones).
- Catalogue findings depend on owner labels: same client + indexed past post → low
  "repost" finding; different client → "footage also appears under another client";
  earlier reviews of the same client's drafts and shared audio only → info lines.
- `reconcile.py` links AI / rule findings to coverage lines (shared evidence IDs or the
  subject named in the finding): duplicates of a provenance finding get `rights_status=duplicate` and are excluded
  from scoring. Ledger matches add supporting-record notes to AI/rule licensing findings,
  which remain counted for human review. Only specific provenance matches can be covered
  by active, correctly typed records. Recomputed on every rebuild.
- YouTube search never downloads candidate videos; only the public thumbnail is fetched
  from `i.ytimg.com`, hashed and discarded.

## Policy knowledge base

`backend/app/policies/data/policy_kb.yaml` (version `2026.11.09`, 35 rules):
YouTube (16), Meta Community Standards (11, apply to Instagram), Instagram (7),
India/ASCI advisory (1). Each rule has a CreatorShield ID (platforms don't number
their policies), the official URL and title, the verification date, paraphrased
key points, and optionally a verbatim quote. The loader (Pydantic) rejects
non-official domains and duplicate IDs. Rules are scoped per target platform.

## AI safety design

| Risk | Control |
|---|---|
| Prompt injection via caption/speech/on-screen text | All user content wrapped in `<untrusted-{random}>` delimiters; boundary stripped from content; control/bidi chars removed; system prompt treats it as data and asks the model to flag embedded instructions |
| Invented citations | Rule IDs re-checked against the KB and target platform; unknown IDs removed and noted; findings without a verified rule are marked advisory + human review |
| Hallucinated evidence | Evidence IDs must exist (T#/F#/O#/CAPTION/HASHTAGS/METADATA); otherwise dropped; "observed" findings without valid evidence are downgraded to "suspected" |
| Bad timestamps | Clamped to video duration; derived from evidence when missing |
| Over-confidence | Suspected and licensing findings always require human review; "cannot check" items always shown; no guarantee language |
| Malformed output | Provider-native structured outputs (Pydantic schema) + server-side re-validation |
| Secrets | Keys only in `backend/.env`; `SecretStr`; never returned by the API; log filter redacts key-like strings |

Finding types: `observed_evidence`, `suspected_violation`, `licensing_uncertainty`,
`cannot_check`. Sources: `deterministic`, `ai`, `combined` (AI finding corroborated
by a rule check).

## Providers

`AnalysisProvider.analyze(PromptPayload) -> ProviderResult`. Implementations:
- **OpenAI** — `chat.completions.parse(response_format=AIAnalysisOutput)`, images as
  base64 data URLs (`detail: low`). Live-tested with `gpt-5`.
- **Anthropic** — `beta.messages.parse(output_format=AIAnalysisOutput)`, adaptive
  thinking, effort setting, server-side refusal fallback. Request shape unit-tested;
  not yet live-tested (no key).
- **Mock** — placeholder only, always labelled.
A local model provider can be added by implementing the same protocol.

Speech-to-text is pluggable too: `faster_whisper` (local, default `small`),
`openai` (hosted), or `none`.

## Storage

`Storage` protocol with `LocalStorage` (path-traversal-safe keys). Keys are
S3-style (`analyses/<uuid>/video.mp4`, `…/frames/F1.jpg`) so an S3-compatible
backend can be added without changing callers.

## Production deployment notes (not yet done)

- Run API (uvicorn/gunicorn) and workers as separate services; scale workers by CPU.
- Use managed Postgres + Redis; object storage (S3/R2/GCS) with signed URLs for video/frames.
- Put the API behind TLS, add authentication (accounts/orgs), per-user authorisation on
  every analysis **and connection**, rate limiting and upload quotas — **none of these exist yet**;
  connected accounts currently belong to the whole installation (single-user local MVP).
- Meta App Review + data-deletion/deauthorize callbacks; Google OAuth verification for YouTube scopes.
- Malware scanning of uploads, structured logging/metrics, error tracking, backups.
- Re-verify the policy KB on a schedule; version reports against the KB version used.
