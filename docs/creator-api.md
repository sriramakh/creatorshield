# Creator features: API reference

Everything here sits under `/api` beside the existing review endpoints and behind the same
login. Interactive docs: `http://localhost:8000/docs`.

## What the workspace offers: `GET /api/config`

Adds to the existing fields:

```jsonc
{
  "platforms": [   // only platforms whose policies are in the knowledge base
    {"id": "youtube_shorts", "label": "YouTube Shorts", "short_label": "Shorts", "family": "youtube",
     "description": "Community Guidelines, monetisation and paid-promotion rules", "short_form": true},
    {"id": "youtube_video", "label": "YouTube video", "short_label": "YouTube", "family": "youtube", "...": "..."},
    {"id": "instagram_reels", "label": "Instagram Reels", "short_label": "Reels", "family": "instagram", "...": "..."}
  ],
  "markets": [     // audience markets with a regulator pack in the knowledge base
    {"id": "IN", "label": "India", "regulator": "ASCI", "summary": "ASCI influencer advertising guidelines"},
    {"id": "US", "label": "United States", "regulator": "FTC", "summary": "..."},
    {"id": "UK", "label": "United Kingdom", "regulator": "ASA / CMA", "summary": "..."}
  ],
  "default_markets": ["IN"],
  "limits": {"caption_max": 5000, "hashtags_max": 100, "sponsors_max": 10, "sponsor_name_max": 100,
             "brief_items_max": 20, "brief_item_max": 200},
  "catalogue_max_seconds": 3600.0
}
```

Render platform and market pickers from this, never from a hard-coded list. TikTok is defined
in `app/platforms.py` but is not offered until its policy pages have been read into the
knowledge base.

## Markets

A review targets one or more audience markets. Each adds that regulator's rules to the
knowledge base the checks and the AI may cite, and its view of which disclosure labels are
clear. Omitted markets fall back to the workspace default (`GET /api/settings`).

- `POST /api/analyses` (multipart): `markets` = comma-separated IDs, e.g. `IN,UK`.
- `POST /api/analyses/import` (JSON): `markets: ["IN", "UK"]`.
- Review summaries and details return `markets: string[]`.

## Brand briefs

A brief is what a sponsor asked for. Reviews and caption checks can be compared with one.

```jsonc
// BriefInput (every list: up to 20 entries of up to 200 characters)
{
  "name": "GlowUp Q4 launch",        // required when saving
  "brand": "GlowUp",
  "must_say": ["patch test first"],       // lines that must appear in caption, speech or on-screen text
  "must_not_say": ["cures acne"],         // wording that must not appear anywhere
  "required_hashtags": ["GlowUpPartner"], // "#" optional
  "required_mentions": ["glowup.official"], // "@" optional; must be in the caption
  "competitors": ["Lumina"],              // must not be named anywhere
  "required_disclosure": "#ad",           // must open the caption; null for none
  "notes": "Reel must go live before 5 Dec."
}
```

| Method | Path | Result |
|---|---|---|
| `GET` | `/api/briefs` | `Brief[]` (BriefInput + `id`, `created_at`, `updated_at`), newest first |
| `POST` | `/api/briefs` | `201 Brief`; `422` with a readable `detail` string |
| `PUT` | `/api/briefs/{id}` | `Brief` (full replace) |
| `DELETE` | `/api/briefs/{id}` | `204`; reviews keep their own copy of the brief they used |

Attach a brief to a review with **either** `brief_id` (a saved brief) **or** `brief` (inline
BriefInput): as form fields on `POST /api/analyses` (`brief` is a JSON string) or JSON properties
on `POST /api/analyses/import` and `POST /api/quick-check`.

A review detail then carries:

```jsonc
"brief": { /* the BriefInput used */ },
"brief_check": {
  "brand": "GlowUp", "name": "", "scope": "video",   // or "caption_only" when the video was not read
  "items": [{"kind": "must_say", "text": "patch test first", "status": "missing",
             "where": [{"source": "transcript", "ref_id": "T3", "timestamp": 6.5}]}],
  "met": 0, "total": 2, "failed": 2, "unverified": 0
}
```

`kind`: `must_say | must_not_say | required_hashtag | required_mention | competitor | required_disclosure`.
`status`: `met | missing | violated | unverified` (`unverified` = can only be confirmed in the video).
Brief findings have `category: "brand_brief"`, `report_section: "brief"`, no policy references,
and are not counted in `risk_score`.

## Instant caption check: `POST /api/quick-check`

Rule-based, answers in milliseconds, stores nothing. Safe to call on every pause in typing.

```jsonc
// request
{"platform": "instagram_reels", "markets": ["IN", "UK"], "caption": "...", "hashtags": ["skincare"],
 "sponsorship": {"relationship": "paid", "sponsors": ["GlowUp"]},
 "brief": { /* BriefInput */ }  /* or "brief_id": "..." */ }

// response
{
  "platform": "instagram_reels", "markets": ["IN", "UK"],
  "findings": [ /* same shape as review findings; ids are "q1", "q2", ...; no "cannot_check" items */ ],
  "readiness": { /* see below */ },
  "risk_score": 5, "risk_level": "low",
  "caption_fix": { /* see below */ },
  "market_disclosure": { /* see below */ },
  "brief_check": null,
  "not_checked": ["Speech, on-screen text and imagery in the video", "..."],
  "policy_kb_version": "2026.11.28"
}
```

## Readiness, caption fix and market labels

Present on `POST /api/quick-check` and on completed reviews (`GET /api/analyses/{id}`).
Review summaries carry `readiness_verdict` only.

```jsonc
"readiness": {
  "verdict": "fix_first",              // ready | review | fix_first
  "headline": "Fix before posting",    // "No issues found by these checks" | "Review before posting"
  "blockers": 2, "warnings": 1,
  "checklist": [
    {"key": "disclosure", "label": "Sponsorship disclosure", "status": "fail",
     "detail": "1 open finding (medium)", "finding_ids": ["..."]}
    // keys: disclosure, community, claims, rights, brief (only with a brief),
    //       coverage (limited or caption-only reviews), ai_review
    // status: pass | warn | fail | unknown
  ]
},
"caption_fix": {
  "needed": true,
  "suggested_caption": "Ad: paid partnership with GlowUp. Loving my new serum, code GLOW20",
  "suggested_hashtags": ["skincare"],
  "label": "Ad",
  "changes": ["Opened the caption with \"Ad\"", "Named GlowUp next to the label"],
  "note": "\"Ad\" is the label ASCI and ASA / CMA guidance describes as clear. ...",
  "markets": {"IN": "clear", "UK": "unclear"}   // status of the ORIGINAL caption per market
},
"market_disclosure": {
  "labels": [{"text": "Sponsored", "kind": "sponsored", "kind_label": "Sponsored", "opening": true,
              "denied": false, "clear_in": ["IN"], "unclear_in": ["UK"]}],
  "by_market": {"UK": {"status": "unclear", "regulator": "ASA / CMA",
                       "clear_labels": [], "unclear_labels": ["Sponsored"]}}
  // status: clear | buried (clear label, not at the start) | unclear | none
}
```

The verdict never says content is safe or approved. `ready` means these checks found nothing to
fix; without a completed AI review the best verdict is `review`.

## Workspace settings

`GET /api/settings` and `PUT /api/settings` (partial update; send only what changes).

```jsonc
{"mode": "creator",                    // creator | agency
 "display_name": "", "default_platform": "instagram_reels",
 "default_markets": ["IN"], "default_language": "en", "onboarded": false}
```

## Insights: `GET /api/insights?days=30`

`days` 7 to 365. Built from one row per completed review that holds its outcome and no content,
so the numbers survive the review's own retention period. Deleting a review removes its row.

```jsonc
{
  "window_days": 30, "generated_at": "...", "stats_retention_days": 365,
  "totals":   {"reviews": 12, "ready": 5, "review": 4, "fix_first": 3, "ready_rate": 0.417,
               "avg_risk_score": 14.2, "open_findings": 31},
  "previous": { /* the same summary for the preceding window, for deltas */ },
  "by_day":   [{"date": "2026-11-27", /* same summary keys; every day in the window, zero-filled */ }],
  "by_group": [{"group": "disclosure", "label": "Sponsorship disclosure", "findings": 9, "reviews": 7}],
  "by_severity": {"critical": 0, "high": 2, "medium": 14, "low": 9, "info": 6},
  "by_platform": [{"platform": "instagram_reels", "label": "Instagram Reels", /* summary keys */ }],
  "by_market":   [{"market": "IN", "label": "India", "reviews": 12}],
  "by_client":   [{"client_label": "Client A", /* summary keys */ }]
}
```

## Other changes

- `DELETE /api/connections/{id}` returns `{"deleted_analyses": n, "revoked": true | false | null,
  "revoke_error": string | null}`. `revoked: false` means the platform could not be told to revoke
  access; the local data was still deleted.
- Finding `report_section` may be `brief`; `category` may be `brand_brief`.
- A YouTube import longer than 3 minutes is created as `youtube_video`.
