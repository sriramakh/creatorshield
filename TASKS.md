# Tasks

## Milestone 1 — end-to-end pipeline (v0.1) ✅

Acceptance criteria and status:

- [x] Frontend and backend start locally with one command (`scripts/dev.sh`)
- [x] Upload MP4/MOV/WebM ≤ 60 s with caption, hashtags, platform (YT Shorts / IG Reels), language (EN / HI); file info + processing status shown
- [x] FFmpeg metadata, audio extraction, timestamped transcript (faster-whisper), scene-aware frames, OCR, non-speech audio intervals
- [x] Versioned policy KB with official URLs, rule IDs, verification dates, platform scoping (35 rules, verified 2026-10-21)
- [x] Rule-based checks: undisclosed promotion, absolute/health claims, YouTube 60-hashtag limit, other-app watermarks, music licensing uncertainty, "cannot check" items
- [x] AI review (OpenAI live-tested; Anthropic implemented) with structured output and server-side validation (citations, evidence, timestamps)
- [x] Prompt-injection defences + tests
- [x] Review dashboard: video, findings timeline, severity groups, filters, timestamps → seek, evidence, policy links, confidence, human-review flags, transcript/OCR, limitations
- [x] Downloadable HTML report + JSON
- [x] Retention + delete controls
- [x] Tests: 48 backend tests, lint/type checks, production build, Playwright E2E
- [x] Docs: README, ARCHITECTURE, DECISIONS, TASKS, TEST_RESULTS, .env.example

## Milestone 2 — analyse posts by link (connected accounts) ✅ (live platform test pending)

- [x] Instagram Login OAuth (professional accounts): connect, long-lived token, refresh, disconnect
- [x] Google OAuth + PKCE for YouTube (read-only default, optional captions scope), refresh, revoke
- [x] Encrypted token storage, single-use OAuth state, no tokens in API responses/logs
- [x] Post picker + paste-a-link; server-side ownership verification
- [x] Instagram full-video import (CDN allow-list, redirect re-check, size cap, 60 s trim) with caption+thumbnail fallback
- [x] YouTube metadata (+ captions) audit; analysis modes surfaced in prompt, UI and report
- [x] Owner-file review on limited imports: frames, speech, on-screen text and audio from the creator's file, cross-checked against platform duration, captions and (Instagram) cover text. No platform video download. Copyright fingerprinting still not performed
- [x] Disconnect deletes imported data; YouTube retention ≤ 30 days
- [x] 29 new backend tests + browser E2E against fake platform server
- [ ] **Live test with real Meta app + Google OAuth client** (needs your developer credentials)
- [ ] Meta deauthorize + data-deletion callbacks (required for App Review)
- [ ] Per-user ownership of connections (needs authentication)

## Milestone 3 — provenance & rights ✅ (paid providers not live-tested)

- [x] Cross-check fixes: Hindi tokenisation (combining marks), mismatch → validity verdict, withheld-file severity, unique upload temp names, stale frames removed, upload progress
- [x] Third-party cues from OCR: other accounts' @handles, broadcaster / studio / label names, copyright notices; AI prompt asks for visual cues (logos, scoreboards, letterboxing, face-cams)
- [x] Rights ledger (5 record types, validity, proof files) with automatic re-derivation of findings
- [x] Brand-agreement disclosure check (high severity when a recorded paid partner is mentioned without disclosure)
- [x] Catalogue fingerprinting: every reviewed video + bulk-indexed past posts; repost and cross-client matching; mirror-aware
- [x] YouTube look-alike search (official API, thumbnail similarity, daily quota cap)
- [x] Song ID (AudD) and web image search (Google Vision) behind opt-in config, signal-triggered, cached, monthly budget cap, labelled mock modes
- [x] Claim-ready evidence pack (report, manifest with SHA-256, ledger records + proofs, dispute-note draft)
- [x] Rights ledger and catalogue pages; provenance panel on the review page
- [ ] Live test of AudD + Google Vision with real keys (needs your authorisation + accounts)
- [ ] Evaluation of catalogue matching on real agency footage (crops, overlays, speed changes)

## Next (proposed priority order)

1. **Security before sharing**: authentication (accounts/orgs), per-analysis authorisation, rate limits/upload quotas, HTTPS deployment
2. **Evaluation set**: 30–50 owned/licensed clips with expected findings to measure precision/recall per category; compare `gpt-5` vs newer OpenAI models vs Claude
3. Live-test the Anthropic provider (needs key) and record results
4. Hindi quality: try Whisper `medium` (or `large-v3-turbo`) for Hindi; Devanagari OCR evaluation with real (properly shaped) text
5. Music: live-test the AudD integration; add ACRCloud as a second provider; ISRC → label lookup for ledger matching
6. PDF export; shareable report links with expiry
7. Policy KB refresh job (re-fetch pages, diff, flag changed rules for human re-verification)
8. ~~Longer videos~~ done (30 min / 5 GB default with a 1080p working copy, see DECISIONS #40–41). Still open: resumable/chunked uploads for multi-GB files on slow connections; TikTok/Facebook targets
9. S3-compatible storage backend; production deployment (managed Postgres/Redis, worker autoscaling)
10. Agency features: workspaces, batch uploads, reviewer sign-off workflow on "human review" findings
11. Catalogue at scale: index past posts straight from connected accounts' exports; LSH index instead of a linear scan (fine to ~2,000 entries today)

## Known issues

- Docker Compose images not yet built/run on this machine.
- Next dev overlay "N" indicator is shown in development only.
- Whisper occasionally misspells Hindi words (e.g. गोरा → गोडा), which can hide keyword-based signals; the AI review usually still catches the meaning.
