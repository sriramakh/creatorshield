"""Turn provenance facts and the rights ledger into findings and coverage lines.

Pure functions: the same facts and ledger always give the same result, so the
report can be rebuilt after the ledger changes without re-running any lookup.

Coverage lines ("rights") list everything the checks noticed with its status:
own / covered / expired / not_started / missing / info. Findings are created only for gaps.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.analysis.deterministic import PLATFORM_RULES
from app.analysis.disclosure import sponsor_disclosed
from app.provenance.ledger import (
    LedgerEntry,
    find_entries,
    handle_matches,
    normalise_handle,
)
from app.schemas import FindingDraft

PERMISSION_KINDS = {"creator_permission"}
FOOTAGE_KINDS = {"footage_license", "creator_permission"}
MUSIC_KINDS = {"music_license"}
BRAND_KINDS = {"brand_agreement"}
OWN_KINDS = {"own_channel"}


def _fmt(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    s = max(0, int(round(seconds)))
    return f"{s // 60}:{s % 60:02d}"


def _line(
    area: str,
    subject: str,
    status: str,
    detail: str,
    *,
    records: list[LedgerEntry] | None = None,
    today: date,
    start: float | None = None,
    end: float | None = None,
) -> dict[str, Any]:
    return {
        "area": area,
        "subject": subject,
        "status": status,
        "detail": detail,
        "records": [r.summary(today) for r in records or []],
        "start_seconds": start,
        "end_seconds": end,
    }


def _best(entries: list[LedgerEntry], today: date) -> tuple[str, list[LedgerEntry]]:
    active = [e for e in entries if e.status(today) == "active"]
    if active:
        return "covered", active
    pending = [e for e in entries if e.status(today) == "not_started"]
    if entries and len(pending) == len(entries):
        return "not_started", pending
    expired = [e for e in entries if e.status(today) == "expired"]
    if expired:
        return "expired", expired
    return "missing", []


def _expiry_text(entries: list[LedgerEntry]) -> str:
    dates = sorted(e.valid_until.isoformat() for e in entries if e.valid_until)
    return f" (ended {dates[-1]})" if dates else ""


def _start_text(entries: list[LedgerEntry]) -> str:
    dates = sorted(e.valid_from.isoformat() for e in entries if e.valid_from)
    return f" (starts {dates[0]})" if dates else ""


def _gap_detail(status: str, entries: list[LedgerEntry], noun: str) -> str | None:
    if status == "expired":
        return f"{noun} has ended{_expiry_text(entries)}."
    if status == "not_started":
        return f"{noun} is not yet valid{_start_text(entries)}."
    return None


def build(
    *,
    provenance: dict[str, Any],
    platform: str,
    client_label: str | None,
    caption: str,
    hashtags: list[str],
    extraction: dict[str, Any],
    entries: list[LedgerEntry],
    connected: set[str],
    today: date,
) -> tuple[list[FindingDraft], list[dict[str, Any]]]:
    rules = PLATFORM_RULES[platform]
    findings: list[FindingDraft] = []
    lines: list[dict[str, Any]] = []
    scope: dict[str, Any] = {"platform": platform, "client_label": client_label}
    own_terms = {
        normalise_handle(t)
        for e in entries
        if e.kind in OWN_KINDS
        and e.applies_to(platform, client_label)
        and e.status(today) == "active"
        for t in e.terms
    } | connected
    cues = provenance.get("cues") or {}

    # ---- handles on screen --------------------------------------------------
    missing_handles: list[dict[str, Any]] = []
    for item in cues.get("handles") or []:
        handle = item["handle"]
        ts = item.get("timestamp")
        if normalise_handle(handle) in own_terms:
            lines.append(_line("handle", handle, "own", "Your own account.", today=today, start=ts))
            continue
        brand = find_entries(entries, BRAND_KINDS, handle=handle, **scope)
        if brand:
            lines.append(
                _line(
                    "handle",
                    handle,
                    "info",
                    "A brand you have a recorded agreement with (see disclosure below).",
                    records=brand,
                    today=today,
                    start=ts,
                )
            )
            continue
        status, recs = _best(
            find_entries(entries, PERMISSION_KINDS | OWN_KINDS, handle=handle, **scope), today
        )
        if status == "covered":
            detail = (
                "Permission recorded in your rights ledger. Permission covers the rights, not "
                "originality: reposted clips without significant original commentary or "
                "editing can still be held back from recommendations"
                + (" and, on YouTube, from monetisation." if platform == "youtube_shorts" else ".")
            )
            lines.append(
                _line("handle", handle, "covered", detail, records=recs, today=today, start=ts)
            )
            continue
        lines.append(
            _line(
                "handle",
                handle,
                status,
                _gap_detail(status, recs, "Permission")
                or "No permission recorded for this account.",
                records=recs,
                today=today,
                start=ts,
            )
        )
        missing_handles.append(
            {**item, "expired": status == "expired", "not_started": status == "not_started"}
        )

    if missing_handles:
        names = ", ".join(h["handle"] for h in missing_handles[:4])
        if any(h["expired"] for h in missing_handles):
            ledger_note = "A permission in your ledger for this account has ended. "
        elif any(h["not_started"] for h in missing_handles):
            ledger_note = "A permission in your ledger for this account is not yet valid. "
        else:
            ledger_note = ""
        findings.append(
            FindingDraft(
                source="provenance",
                category="originality",
                finding_type="suspected_violation",
                severity="medium",
                confidence="medium",
                title=f"Another account's handle is on screen: {names}",
                explanation=(
                    "On-screen text shows an account handle that is not one of your connected "
                    "accounts or rights-ledger entries. That usually means the clip, or part of "
                    "it, came from that account. Crediting a creator is not the same as having "
                    "their permission. "
                    + ledger_note
                    + "OCR can misread text, so confirm visually."
                ),
                suggested_action=(
                    "If the footage is theirs, get written permission and add it to the rights "
                    "ledger (it then appears in your evidence pack), or replace the clip. If it is "
                    "your own second account or a collaborator, add the handle to the ledger."
                ),
                start_seconds=min(
                    (h["timestamp"] for h in missing_handles if h.get("timestamp") is not None),
                    default=None,
                ),
                end_seconds=max(
                    (h["timestamp"] for h in missing_handles if h.get("timestamp") is not None),
                    default=None,
                ),
                evidence=[
                    {
                        "source": "ocr",
                        "ref_id": h["ref_id"],
                        "detail": f'"{h["handle"]}" in: {h["text"]}',
                        "timestamp": h.get("timestamp"),
                    }
                    for h in missing_handles[:6]
                ],
                policy_rule_ids=rules["reused"] + rules["copyright"],
                requires_human_review=True,
            )
        )

    # ---- broadcaster / studio / label branding -----------------------------
    missing_brands: list[dict[str, Any]] = []
    for item in cues.get("broadcasters") or []:
        name = item["name"]
        ts = item.get("timestamp")
        status, recs = _best(find_entries(entries, FOOTAGE_KINDS, text=name, **scope), today)
        if status == "covered":
            lines.append(
                _line(
                    "broadcaster",
                    name,
                    "covered",
                    "Licence recorded in your rights ledger.",
                    records=recs,
                    today=today,
                    start=ts,
                )
            )
            continue
        lines.append(
            _line(
                "broadcaster",
                name,
                status,
                _gap_detail(status, recs, "Licence")
                or "No licence recorded. Branding suggests third-party footage.",
                records=recs,
                today=today,
                start=ts,
            )
        )
        missing_brands.append(item)
    if missing_brands:
        names = ", ".join(b["name"] for b in missing_brands[:4])
        only_notice = all(b["name"] == "Copyright notice" for b in missing_brands)
        findings.append(
            FindingDraft(
                source="provenance",
                category="licensing",
                finding_type="licensing_uncertainty",
                severity="low" if only_notice else "medium",
                confidence="low" if only_notice else "medium",
                title=f"Third-party branding on screen: {names}",
                explanation=(
                    "On-screen text names a broadcaster, studio, label or streaming service, or "
                    "shows a copyright notice. Footage carrying that branding is usually owned by "
                    "them, and sports, film, TV and music clips are among the most actively "
                    "claimed content. Commentary, criticism or news use can change how the rules "
                    "apply, but does not make the clip licensed."
                ),
                suggested_action=(
                    "Use the clip only with a licence (record it in the rights ledger) or with "
                    "substantial original commentary you are prepared to defend. Otherwise cut it."
                ),
                start_seconds=min(
                    (b["timestamp"] for b in missing_brands if b.get("timestamp") is not None),
                    default=None,
                ),
                end_seconds=max(
                    (b["timestamp"] for b in missing_brands if b.get("timestamp") is not None),
                    default=None,
                ),
                evidence=[
                    {
                        "source": "ocr",
                        "ref_id": b["ref_id"],
                        "detail": f'"{b["name"]}" in: {b["text"]}',
                        "timestamp": b.get("timestamp"),
                    }
                    for b in missing_brands[:6]
                ],
                policy_rule_ids=rules["copyright"] + rules["reused"],
                requires_human_review=True,
            )
        )

    # ---- brand agreements vs disclosure -------------------------------------
    texts = _text_items(caption, hashtags, extraction)
    mentioned = [
        e
        for e in entries
        if e.kind in BRAND_KINDS
        and e.applies_to(platform, client_label)
        and any(find_entries([e], BRAND_KINDS, text=t["text"], **scope) for t in texts)
    ]
    for entry in entries:
        if entry.kind not in BRAND_KINDS or not entry.applies_to(platform, client_label):
            continue
        hits = [
            t
            for t in texts
            if any(
                handle_matches(term, h)
                for term in entry.terms
                if term.strip().startswith("@")
                for h in _handles_in(t["text"])
            )
            or find_entries([entry], BRAND_KINDS, text=t["text"], **scope)
        ]
        if not hits:
            continue
        status = entry.status(today)
        if sponsor_disclosed(caption, entry.terms, len(mentioned) > 1):
            lines.append(
                _line(
                    "brand",
                    entry.counterparty,
                    "info",
                    "Opening-caption disclosure wording detected; adequacy needs human review. "
                    "On-screen duration and prominence were not verified. Enable the platform's "
                    "paid-partnership / paid-promotion setting when publishing.",
                    records=[entry],
                    today=today,
                )
            )
            continue
        lines.append(
            _line(
                "brand",
                entry.counterparty,
                "missing",
                "Brand mentioned with no disclosure.",
                records=[entry],
                today=today,
            )
        )
        findings.append(
            FindingDraft(
                source="provenance",
                category="disclosure",
                finding_type="observed_evidence",
                severity="high" if status == "active" else "medium",
                confidence="high",
                title=f"Paid agreement with {entry.counterparty}: opening disclosure needs review",
                explanation=(
                    f"Your rights ledger records a paid agreement with {entry.counterparty}"
                    + (
                        ""
                        if status == "active"
                        else " (not yet valid)"
                        if status == "not_started"
                        else " (now ended)"
                    )
                    + ", but no associated opening disclosure such as #ad, "
                    "'paid partnership' or 'sponsored' was established in the caption. "
                    "Video or speech disclosure may exist and requires review. "
                    "Platforms and ASCI require material connections to be "
                    "disclosed clearly."
                ),
                suggested_action=(
                    "Add a clear disclosure at the start of the caption and on screen, and turn "
                    "on the platform's paid-partnership / paid-promotion setting when publishing."
                ),
                evidence=[
                    {
                        "source": t["source"],
                        "ref_id": t["ref_id"],
                        "detail": t["text"][:160],
                        "timestamp": t["timestamp"],
                    }
                    for t in hits[:6]
                ],
                start_seconds=min(
                    (t["timestamp"] for t in hits if t["timestamp"] is not None), default=None
                ),
                end_seconds=max(
                    (t["timestamp"] for t in hits if t["timestamp"] is not None), default=None
                ),
                policy_rule_ids=rules["disclosure"],
                requires_human_review=True,
            )
        )

    # ---- catalogue matches --------------------------------------------------
    catalogue = provenance.get("catalogue") or {}
    for m in catalogue.get("matches") or []:
        findings_for, line = _catalogue_match(m, platform, entries, scope, rules, today)
        lines.append(line)
        findings.extend(findings_for)

    # ---- identified music ---------------------------------------------------
    music = provenance.get("music") or {}
    for clip in music.get("clips") or []:
        if not clip.get("matched"):
            continue
        mock = bool(music.get("is_mock"))
        song = f"“{clip.get('title')}” by {clip.get('artist')}"
        if clip.get("label"):
            song += f" ({clip['label']})"
        text = " ".join(str(clip.get(k) or "") for k in ("artist", "title", "label", "album"))
        status, recs = _best(find_entries(entries, MUSIC_KINDS, text=text, **scope), today)
        lines.append(
            _line(
                "music",
                song,
                status if not mock else "info",
                ("MOCK identification - not real. " if mock else "")
                + (
                    "Licence recorded in your rights ledger."
                    if status == "covered"
                    else _gap_detail(status, recs, "Licence")
                    or "No licence recorded for this track."
                ),
                records=recs,
                today=today,
                start=clip.get("start"),
                end=clip.get("end"),
            )
        )
        if status == "covered":
            continue
        findings.append(
            FindingDraft(
                source="provenance",
                category="licensing",
                finding_type="licensing_uncertainty",
                severity="low" if mock else "medium",
                confidence="low" if mock else "high",
                title=("[MOCK] " if mock else "") + f"Identified music: {song}",
                explanation=(
                    ("This is a MOCK result from the placeholder provider. " if mock else "")
                    + f"The audio at {_fmt(clip.get('start'))}-{_fmt(clip.get('end'))} matches "
                    f"{song}. Commercial recordings are commonly registered for automatic "
                    "matching, so a post with this track may be claimed, muted or blocked unless "
                    "it is licensed. Adding the track through the platform's own music library "
                    "covers use on that platform only; music already mixed into your file is "
                    "not covered by it."
                    + (
                        " The licence in your ledger has ended."
                        if status == "expired"
                        else " The licence in your ledger is not yet valid."
                        if status == "not_started"
                        else ""
                    )
                ),
                suggested_action=(
                    "Remove the track from the file and add it through the platform's music "
                    "library, or record your licence for it in the rights ledger. Otherwise "
                    "replace it with licensed or original audio."
                ),
                start_seconds=clip.get("start"),
                end_seconds=clip.get("end"),
                evidence=[
                    {
                        "source": "audio",
                        "ref_id": "MUSIC",
                        "detail": song
                        + (f" - {clip['song_link']}" if clip.get("song_link") else ""),
                        "timestamp": clip.get("start"),
                    }
                ],
                policy_rule_ids=rules["copyright"],
                requires_human_review=True,
            )
        )

    # ---- web image matches ---------------------------------------------------
    web = provenance.get("web") or {}
    web_hits = []
    for frame in web.get("frames") or []:
        pages = frame.get("pages") or []
        full = [p for p in pages if p.get("full_match")] or (
            [{"url": u, "title": "", "domain": ""} for u in frame.get("full_matches") or []]
        )
        partial = [p for p in pages if not p.get("full_match")]
        if not full and not partial:
            continue
        active_entries = [e for e in entries if e.status(today) == "active"]
        covered = [
            p
            for p in full + partial
            if find_entries(
                active_entries,
                FOOTAGE_KINDS | OWN_KINDS,
                text=f"{p.get('domain', '')} {p.get('title', '')}",
                **scope,
            )
        ]
        uncovered_full = [p for p in full if p not in covered]
        uncovered_partial = [p for p in partial if p not in covered]
        status = (
            "covered" if covered and not uncovered_full and not uncovered_partial else "missing"
        )
        mock = bool(web.get("is_mock"))
        lines.append(
            _line(
                "web",
                f"Frame {frame['frame_id']} at {_fmt(frame.get('timestamp'))}",
                "info" if mock else status,
                ("MOCK result - not real. " if mock else "")
                + f"{len(full)} page(s) with the same image, {len(partial)} with a similar one.",
                today=today,
                start=frame.get("timestamp"),
            )
        )
        if uncovered_full or uncovered_partial:
            web_hits.append((frame, uncovered_full, uncovered_partial, mock))
    if web_hits:
        mock = all(h[3] for h in web_hits)
        any_full = any(h[1] for h in web_hits)
        evidence = []
        for frame, full, partial, _ in web_hits:
            for page in (full or partial)[:3]:
                evidence.append(
                    {
                        "source": "frame",
                        "ref_id": frame["frame_id"],
                        "detail": f"{'Same' if full else 'Similar'} image on "
                        f"{page.get('domain') or page.get('url')}: "
                        f"{page.get('title') or page.get('url')}",
                        "timestamp": frame.get("timestamp"),
                        "url": page.get("url"),
                    }
                )
        findings.append(
            FindingDraft(
                source="provenance",
                category="licensing",
                finding_type="licensing_uncertainty",
                severity="low" if mock or not any_full else "medium",
                confidence="low" if mock else "medium",
                title=("[MOCK] " if mock else "")
                + (
                    "Frames from this video already appear on the web"
                    if any_full
                    else "Frames resemble images already on the web"
                ),
                explanation=(
                    ("These are MOCK results from the placeholder provider. " if mock else "")
                    + "A reverse image search found pages carrying the same or a similar picture. "
                    "If those pages are earlier and not yours, the footage may come from them or "
                    "from a common source (stock library, film, broadcast). The search cannot tell "
                    "who published first or who owns the image."
                ),
                suggested_action=(
                    "Open the pages listed. If the image is theirs, license it and record the "
                    "licence in the rights ledger, or replace the shot."
                ),
                evidence=evidence[:8],
                start_seconds=min((h[0].get("timestamp") or 0 for h in web_hits), default=None),
                end_seconds=max((h[0].get("timestamp") or 0 for h in web_hits), default=None),
                policy_rule_ids=rules["copyright"],
                requires_human_review=True,
            )
        )

    # ---- YouTube look-alikes (leads only, no finding) ------------------------
    youtube = provenance.get("youtube") or {}
    for result in youtube.get("results") or []:
        if result.get("visual_match") not in {"strong", "possible"} or result.get("own_channel"):
            continue
        lines.append(
            _line(
                "youtube",
                f"{result.get('title')} - {result.get('channel_title')}",
                "review",
                f"{'Very similar' if result['visual_match'] == 'strong' else 'Possibly similar'} "
                f"thumbnail (closest frame {_fmt(result.get('matched_at'))}); published "
                f"{str(result.get('published_at') or '')[:10]}. Check whether it is an earlier "
                "upload of the same footage.",
                today=today,
                start=result.get("matched_at"),
            )
        )
    return findings, lines


def _catalogue_match(
    m: dict[str, Any],
    platform: str,
    entries: list[LedgerEntry],
    scope: dict[str, Any],
    rules: dict[str, list[str]],
    today: date,
) -> tuple[list[FindingDraft], dict[str, Any]]:
    label = m["owner_label"]
    title = m.get("title") or "untitled"
    span = f"{_fmt(m['query_start'])}-{_fmt(m['query_end'])}"
    kind_text = {
        "identical_file": "the identical file",
        "same_clip": "the same footage and audio",
        "same_footage": "the same footage",
        "mirrored_footage": "the same footage, mirrored",
        "same_audio": "the same audio",
    }[m["kind"]]
    subject = f"{label}: {title}"
    evidence = [
        {
            "source": "metadata",
            "ref_id": "CATALOGUE",
            "detail": f"{span} matches {kind_text} in {subject} "
            f"({_fmt(m['ref_start'])}-{_fmt(m['ref_end'])} there)",
            "timestamp": m["query_start"],
        }
    ]

    def line(status: str, detail: str, recs: list[LedgerEntry] | None = None) -> dict[str, Any]:
        out = _line(
            "catalogue",
            subject,
            status,
            detail,
            records=recs,
            today=today,
            start=m["query_start"],
            end=m["query_end"],
        )
        out["match"] = {k: m.get(k) for k in ("kind", "analysis_id", "fingerprint_id", "source")}
        return out

    if m["kind"] == "same_audio":
        return [], line("info", f"{span} uses {kind_text} as this video. Usually a shared track.")
    if m.get("unlabelled"):
        return [], line(
            "info",
            f"{span} shows {kind_text}. Add a client / account label to both videos so the "
            "owner can be compared.",
        )
    if m.get("same_owner"):
        if m.get("source") != "catalogue":
            return [], line("info", f"{span} shows {kind_text} as a video reviewed earlier.")
        if max(m["video_coverage"], m["audio_coverage"]) < 0.5:
            return [], line("own", f"{span} reuses part of an earlier post ({kind_text}).")
        return [
            FindingDraft(
                source="provenance",
                category="originality",
                finding_type="suspected_violation",
                severity="low",
                confidence="high" if m["kind"] in {"identical_file", "same_clip"} else "medium",
                title=f"Most of this video repeats an earlier post ({label})",
                explanation=(
                    f"{span} of this video has {kind_text} as the indexed post “{title}”. "
                    "Reposting your own content is allowed, but reposts with only minor edits "
                    "are less likely to be recommended and can count as repetitive content for "
                    "monetisation."
                ),
                suggested_action=(
                    "If this is a deliberate repost, add something new (commentary, a new edit "
                    "or context). Otherwise check that the right file was chosen."
                ),
                start_seconds=m["query_start"],
                end_seconds=m["query_end"],
                evidence=evidence,
                policy_rule_ids=rules["reused"],
                requires_human_review=True,
            )
        ], line("own", f"{span} repeats an earlier post ({kind_text}).")

    status, recs = _best(
        find_entries(entries, PERMISSION_KINDS | FOOTAGE_KINDS, text=label, **scope), today
    )
    if status == "covered":
        return [], line(
            "covered", f"{span} shows {kind_text}. Permission or licence recorded.", recs
        )
    mirrored = m["kind"] == "mirrored_footage"
    return [
        FindingDraft(
            source="provenance",
            category="licensing",
            finding_type="licensing_uncertainty",
            severity="medium",
            confidence="high" if m["kind"] in {"identical_file", "same_clip"} else "medium",
            title=f"Footage also appears under another client: {label}",
            explanation=(
                f"{span} of this video has {kind_text} as “{title}” in {label}'s catalogue. "
                "The same footage under two different owners means at least one of them may not "
                "hold the rights to it."
                + (
                    " Mirroring a clip does not stop platforms from matching it."
                    if mirrored
                    else ""
                )
                + (
                    " A permission for it has ended."
                    if status == "expired"
                    else " A permission for it is not yet valid."
                    if status == "not_started"
                    else ""
                )
            ),
            suggested_action=(
                "Confirm who shot the footage. Record permission or a licence in the rights "
                "ledger before publishing, or replace the clip."
            ),
            start_seconds=m["query_start"],
            end_seconds=m["query_end"],
            evidence=evidence,
            policy_rule_ids=rules["copyright"] + rules["reused"],
            requires_human_review=True,
        )
    ], line(status, f"{span} shows {kind_text} under a different client.", recs)


def _handles_in(text: str) -> list[str]:
    return re.findall(r"@[\w.]{2,30}", text)


def _text_items(
    caption: str, hashtags: list[str], extraction: dict[str, Any]
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if caption.strip():
        items.append({"source": "caption", "ref_id": "CAPTION", "text": caption, "timestamp": None})
    if hashtags:
        items.append(
            {
                "source": "hashtags",
                "ref_id": "HASHTAGS",
                "text": " ".join(f"#{h}" for h in hashtags),
                "timestamp": None,
            }
        )
    for seg in (extraction.get("transcript") or {}).get("segments") or []:
        items.append(
            {
                "source": "transcript",
                "ref_id": seg["id"],
                "text": seg["text"],
                "timestamp": seg["start"],
            }
        )
    for o in extraction.get("ocr") or []:
        items.append(
            {"source": "ocr", "ref_id": o["id"], "text": o["text"], "timestamp": o.get("timestamp")}
        )
    return items
