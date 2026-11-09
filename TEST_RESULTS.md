# Test results — 2026-10-22 (updated: provenance & rights)

Environment: Mac mini M4, 16 GB, macOS 26.5.2 · Python 3.13.12 · Node 25.8.1 ·
PostgreSQL 17.9 · Redis 8.6.1 · FFmpeg 9.0.2 (upgraded with Chromaprint 1.6.2) · Tesseract 5.5.2 · Next.js 16.4.2.

## Summary

| Check | Result |
|---|---|
| Backend unit + integration tests (`pytest`) | **113 passed**, 0 failed (≈25 s) |
| Ruff lint + format | Pass |
| mypy (app, 60 files) | Pass |
| Frontend ESLint / TypeScript | Pass |
| Frontend production build (`next build`) | Pass |
| Playwright E2E (real browser, running stack, **live OpenAI**) | **2 passed** (re-run after connected-accounts work: no regression) |
| Playwright E2E — connected accounts (fake Instagram/YouTube server, mock AI) | **1 passed** (connect ×2, IG full video, IG caption+thumbnail fallback, YT ownership refusal, YT metadata+captions, disconnect deletes data) |
| Playwright E2E — rights ledger (add / delete record) | **1 passed** |
| Provenance flow in a real browser (catalogue → ledger → review with **live gpt-5**, 1 run) | Pass — see below |
| AudD song ID / Google Vision web search / YouTube search | Exercised against HTTP fakes only; **not live-tested** (no keys, no paid calls authorised) |
| Real Instagram / Google OAuth | **Not tested** — requires your Meta app and Google OAuth client |
| Live AI analyses (OpenAI `gpt-5-2025-08-07`) | 6 runs, all completed, 0 invented citations |
| Docker Compose | `docker compose config` valid; **images not built or run** |
| Anthropic provider | Request/response handling unit-tested with a stubbed client; **not live-tested** (no key) |

## Backend tests (48)

| File | Tests | Covers |
|---|---|---|
| test_policy_kb.py | 6 | KB loads; official domains only; duplicate IDs rejected; platform scoping; every rule ID used by deterministic checks exists for its platform |
| test_validation.py | 8 | Invented citations removed; cross-platform citations removed; ID normalisation; unknown evidence dropped + "observed" downgraded; timestamp clamping/derivation; injection note; mock labelling |
| test_deterministic.py | 8 | Promo-without-disclosure; disclosure suppresses it; Hindi variants; YouTube 60-hashtag limit; watermark OCR; music → licensing uncertainty; clean video → only "cannot check", risk 0; risk levels |
| test_merge.py | 5 | Corroborating findings merge; severity/citation/evidence union; unrelated kept; **regression for the cross-category merge bug found in live testing** |
| test_prompt_and_providers.py | 8 | Untrusted delimiting; forged boundary neutralised; control/bidi chars stripped; platform-scoped KB in prompt; Anthropic + OpenAI request shapes (stubbed); refusal handling; API-key log redaction |
| test_media.py | 6 | Extension validation; non-video rejected; probe + 60 s limit (synthetic 62 s clip); frame selection; interval maths; **real FFmpeg + faster-whisper + Tesseract** extraction on owned sample |
| test_api.py | 7 | Health; full upload→report with mock AI (frames, range requests, HTML/JSON report, listing, delete removes files); AI failure still yields rule-based report; bad inputs (platform, language, .txt, fake mp4, 62 s, >100 hashtags, size limit); path traversal; retention purge |

| test_integrations.py | 32 | Link parsing (incl. look-alike hosts); media host allow-list (https, SSRF targets); SRT/ISO duration/caption-track choice; token encryption; OAuth state single-use + platform-bound; denied consent; encrypted tokens never exposed; IG full-video import; IG withheld-file fallback (no fake timestamps); IG ownership/type checks; redirect to non-allow-listed host blocked; YouTube PKCE + least-privilege scope; YT ownership, metadata audit, ≤30-day retention, report banner, disconnect revokes + deletes; captions with scope; token refresh; missing key / unconfigured platform; import can wait for an owner file; owner-file rejected on a plain upload; YouTube owner-file review cross-checks duration without downloading platform video |
| test_cross_check.py | 8 | Duration match / mismatch / trim; mismatch is a validity verdict with zero risk; caption-track overlap incl. **identical Hindi text** (combining marks); Instagram withheld-file signal (no severity inversion); cover text missing from the video; cross-checked mode still runs the file checks |
| test_provenance.py | 25 | Fingerprints match re-encoded, mirrored copies and reject unrelated video; **text-on-colour templates don't match each other** (regression); mirror hash involution; OCR cues (handles, broadcasters, © notices, not emails); ledger coverage / expiry / own handles; brand agreement → disclosure finding; catalogue owner rules (other client, own repost, earlier draft, shared audio); music + web findings and mock labelling; AudD calls, cache and **budget cap stops calls**; Google Vision request/response; YouTube search, thumbnail host allow-list and daily quota cap; AI duplicates not double-counted, more severe one counted, ledger covers AI licensing findings but not originality; API: catalogue → mirrored copy under another client → finding → permission with PDF proof clears it → evidence pack contents → delete restores it; proof type check; retention keeps fingerprints, explicit delete and disconnect remove them |

Tests use the separate `creatorshield_test` database, a temp storage dir, inline
jobs and the mock provider — **no paid API calls**.

## Provenance flow — real browser, live AI (2026-10-22)

Synthetic test reel we own (FFmpeg test pattern + text overlay "via @clipsdaily / LIVE Star
Sports", pink-noise audio), caption "Loving my FitFuel shake… code FIT50", client "Client A".
Catalogue: a mirrored copy indexed as "Client B". Ledger: FitFuel brand agreement.

| Step | Result |
|---|---|
| Catalogue upload (UI) | Fingerprinted, file discarded |
| Review (gpt-5, ≈ $0.05) | Provenance: FitFuel agreement without disclosure (**high**), @clipsdaily handle, Star Sports branding, same clip under Client B (100 % video + audio, mirrored). AI independently flagged broadcast footage, repost and undisclosed promotion |
| Duplicates | AI findings that repeat a provenance finding marked "duplicate · not counted"; the more severe of each pair counts. Risk 56 → 40 after reconciliation |
| Ledger: permission (Client B, PNG proof) + Star Sports licence | Coverage lines → covered; AI licensing finding → "covered · not counted"; AI originality finding still counts (permission ≠ originality); risk 40 → 29 |
| Evidence pack | README, report, manifest (SHA-256), records + proof, dispute draft listing covered items and the open FitFuel disclosure item |
| Defects found and fixed | AI/provenance double-counting; permission wrongly clearing an originality finding; one AI finding absorbing only one of two duplicates; "No record" label on a recorded brand; "valid ... to open" wording |

Test records and the "Client B" catalogue entry were deleted afterwards; the demo review was kept.

## Live AI verification (OpenAI gpt-5)

Real pipeline: browser/HTTP upload → Redis → worker → FFmpeg/Whisper/Tesseract →
rule checks → OpenAI structured output → validation/merge → dashboard/report.

| Sample → platform | Risk | AI findings (after validation/merge) |
|---|---|---|
| sample_promo_en → YouTube Shorts | Elevated | HIGH medical cure/guarantee claim (YT-CG-MEDMISINFO, YT-MON-AD-FRIENDLY, ASCI) @0:07–0:13; MEDIUM possible undisclosed paid promotion (YT-DISC-PAID-PROMO, ASCI) @0:13–0:20; LOW music rights unclear (YT-COPY-BASICS) @0:21–0:27 |
| sample_tips_en → YouTube Shorts (control) | **Low, 0** | **No findings** — model identified instructional content with a safety note |
| sample_promo_hi → Instagram Reels | Elevated | HIGH branded promotion without disclosure (IG-BRANDED-CONTENT, IG-PAID-PARTNERSHIP, ASCI); MEDIUM guaranteed "fair skin in 7 days" claim (META-CS-COMMERCIAL, IG-MON-CONTENT, IG-RECOMMENDATIONS); LOW static-text format monetization limit |

- Validation removed **0** citations across all live runs (every cited ID existed in the KB for that platform).
- Processing time ≈ 90 s per video (Whisper ≈ 5 s, OpenAI call is the bulk).
- Token usage ≈ 4.7–5.0k input, 1.6–5.0k output per video; total for 6 runs ≈ 29k in / 26k out
  (≈ $0.30 at gpt-5 list prices as known to the developer — confirm on the OpenAI dashboard).

### Defects found and fixed during testing

| Defect | Found by | Fix |
|---|---|---|
| faster-whisper crashed (PyAV API change) | first extraction run | decode WAV ourselves |
| Trailing silence reported as "sound" when audio track shorter than video | extraction run | use real audio length |
| Frame cap could drop scene-change frames | unit test | prioritise scene changes when capping |
| `usePathname()` outside Suspense (Next 16 Cache Components) | browser console check | suspended nav component |
| Hidden (Activity) upload page kept its `<video>`/form state | Playwright | reset form after submit; scoped selectors; pause video on hide |
| Hindi "guarantee" spelling variant missed | live Hindi run | broader regex |
| AI + rule findings duplicated | live run review | merge corroborating findings |
| Merge folded a disclosure finding into a health-claim finding (one shared transcript line) | live run review | stricter matching + regression test |
| Model marked a suspected high-severity finding as not needing review | live run review | suspected/licensing findings always require review |

## Not tested / limitations of this test pass

- Real creator videos (only synthetic, project-owned samples were used) — accuracy on real-world content is **unmeasured**; no precision/recall evaluation exists yet.
- Videos with real copyrighted music, real faces, violence, nudity, hate speech etc. (deliberately not used).
- MOV and WebM uploads were not exercised end-to-end (MP4 only); validation code paths are shared.
- Anthropic provider live call; OpenAI hosted STT.
- Docker images; production deployment; load/concurrency; authentication (does not exist).
- Mobile layout was not visually tested.
