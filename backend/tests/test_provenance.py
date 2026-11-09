"""Provenance & rights: fingerprints, cues, rights ledger, lookups, evidence pack.

Paid services (AudD, Google Vision) and YouTube search are exercised against
httpx.MockTransport fakes. No external API is called.
"""

from __future__ import annotations

import io
import json
import subprocess
import uuid
import zipfile
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.analysis.risk import compute_risk
from app.config import get_settings
from app.db import get_sessionmaker
from app.main import app
from app.media.probe import probe
from app.models import Analysis, PaidLookup
from app.provenance import budget, cues, music, pipeline, web, youtube_search
from app.provenance.common import LookupFailed
from app.provenance.findings import build
from app.provenance.fingerprint import (
    compare,
    compute_fingerprint,
    mirror_hash,
    thumbnail_hash,
)
from app.provenance.ledger import LedgerEntry
from app.schemas import FindingDraft

TODAY = date(2026, 10, 22)


# --------------------------------------------------------------------------- media fixtures


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


@pytest.fixture(scope="module")
def media(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    d = tmp_path_factory.mktemp("prov")
    rich = d / "rich.mp4"
    _ffmpeg(
        "-f", "lavfi", "-i", "testsrc2=s=360x640:d=16",
        "-f", "lavfi", "-i", "anoisesrc=d=16:c=pink:r=22050:a=0.3",
        "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(rich),
    )  # fmt: skip
    mirror = d / "mirror.mp4"
    _ffmpeg("-i", str(rich), "-vf", "hflip", "-c:a", "copy", str(mirror))
    reenc = d / "reenc.mp4"
    _ffmpeg(
        "-i", str(rich), "-vf", "scale=270:480,eq=brightness=0.04",
        "-c:v", "libx264", "-crf", "34", "-c:a", "aac", "-b:a", "48k", str(reenc),
    )  # fmt: skip
    other = d / "other.mp4"
    _ffmpeg(
        "-f", "lavfi", "-i", "mandelbrot=s=360x640:r=25", "-t", "16",
        "-c:v", "libx264", "-preset", "ultrafast", str(other),
    )  # fmt: skip
    thumb = d / "thumb.jpg"
    _ffmpeg("-ss", "6", "-i", str(rich), "-frames:v", "1", "-vf", "scale=480:-2", str(thumb))
    return {"rich": rich, "mirror": mirror, "reenc": reenc, "other": other, "thumb": thumb}


def _fp(path: Path):  # type: ignore[no-untyped-def]
    return compute_fingerprint(path, probe(path).duration_seconds, 900)


# --------------------------------------------------------------------------- fingerprints


@pytest.mark.slow
def test_fingerprint_matches_reencoded_and_mirrored_copies(media: dict[str, Path]) -> None:
    base = _fp(media["rich"])
    assert sum(1 for h in base.frame_hashes if h) >= 20 and len(base.audio_fp) > 50

    reenc = compare(_fp(media["reenc"]), base)
    assert reenc is not None and reenc["kind"] == "same_clip"
    assert reenc["video_coverage"] > 0.8

    mirrored = compare(_fp(media["mirror"]), base)
    assert mirrored is not None and mirrored["kind"] in {"mirrored_footage", "same_clip"}
    assert mirrored["video_coverage"] > 0.8

    assert compare(_fp(media["other"]), base) is None


@pytest.mark.slow
def test_text_on_colour_templates_do_not_match_each_other() -> None:
    samples = Path(__file__).resolve().parents[2] / "samples"
    if not (samples / "sample_promo_hi.mp4").exists():
        pytest.skip("run samples/generate_samples.py first")
    en = _fp(samples / "sample_promo_en.mp4")
    for name in ("sample_promo_hi.mp4", "sample_tips_en.mp4"):
        assert compare(_fp(samples / name), en) is None


@pytest.mark.slow
def test_same_clip_requires_the_same_reference_offset() -> None:
    from app.provenance.fingerprint import Segment, _same_offset

    video = Segment("video", 10, 20, 10, 20, 0.5, 0.9)
    aligned = Segment("audio", 10, 18, 11.4, 19.4, 0.4, 0.9)
    overlapping_query = Segment("audio", 12, 20, 90, 98, 0.4, 0.9)
    assert _same_offset(video, aligned)
    assert not _same_offset(video, overlapping_query)


def test_mirror_hash_is_an_involution(media: dict[str, Path]) -> None:
    h = thumbnail_hash(media["thumb"])
    assert h is not None
    assert mirror_hash(mirror_hash(h)) == h
    assert mirror_hash(h) != h


# --------------------------------------------------------------------------- cues


def test_cues_find_handles_and_broadcasters_but_not_emails() -> None:
    ocr = [
        {"id": "O1", "frame_id": "F1", "timestamp": 1.0, "text": "via @Cricket.Clips_HD"},
        {"id": "O2", "frame_id": "F2", "timestamp": 3.0, "text": "mail me at me@gmail.com"},
        {"id": "O3", "frame_id": "F3", "timestamp": 5.0, "text": "LIVE  Star Sports 1  IND 182/4"},
        {"id": "O4", "frame_id": "F4", "timestamp": 7.0, "text": "© 2024 All rights reserved"},
    ]
    handles = cues.find_handles(ocr)
    assert [h["handle"] for h in handles] == ["@cricket.clips_hd"]
    names = [b["name"] for b in cues.find_broadcasters(ocr)]
    assert "Star Sports" in names and "Copyright notice" in names


# --------------------------------------------------------------------------- ledger + findings


def _entry(
    kind: str,
    name: str,
    *terms: str,
    until: date | None = None,
    starts: date | None = None,
    client: str | None = None,
) -> LedgerEntry:
    return LedgerEntry(
        id=str(uuid.uuid4()),
        kind=kind,
        counterparty=name,
        terms=list(terms) or [name],
        platforms=[],
        client_label=client,
        valid_from=starts,
        valid_until=until,
        reference="LIC-1",
        has_proof=False,
    )


def _build(
    prov: dict[str, Any],
    entries: list[LedgerEntry] | None = None,
    *,
    caption: str = "",
    platform: str = "youtube_shorts",
    connected: set[str] | None = None,
    extraction: dict[str, Any] | None = None,
    client_label: str | None = "Client A",
) -> tuple[list[FindingDraft], list[dict[str, Any]]]:
    return build(
        provenance=prov,
        platform=platform,
        client_label=client_label,
        caption=caption,
        hashtags=[],
        extraction=extraction or {"transcript": {"segments": []}, "ocr": []},
        entries=entries or [],
        connected=connected or set(),
        today=TODAY,
    )


HANDLE_PROV = {
    "cues": {
        "handles": [
            {"handle": "@clipsdaily", "ref_id": "O1", "timestamp": 2.0, "text": "@clipsdaily"}
        ],
        "broadcasters": [],
    }
}


def test_unrecorded_handle_is_a_finding_and_permission_covers_it() -> None:
    findings, lines = _build(HANDLE_PROV)
    assert [f.title for f in findings] == ["Another account's handle is on screen: @clipsdaily"]
    assert lines[0]["status"] == "missing"

    perm = _entry("creator_permission", "Clips Daily", "@ClipsDaily")
    findings, lines = _build(HANDLE_PROV, [perm])
    assert findings == []
    assert lines[0]["status"] == "covered"
    assert "monetisation" in lines[0]["detail"]  # YouTube reused-content caveat
    assert "not originality" in lines[0]["detail"]


def test_expired_permission_and_own_handles() -> None:
    expired = _entry("creator_permission", "Clips Daily", "@clipsdaily", until=TODAY - timedelta(1))
    findings, lines = _build(HANDLE_PROV, [expired])
    assert lines[0]["status"] == "expired"
    assert "ended" in findings[0].explanation

    findings, lines = _build(HANDLE_PROV, connected={"clipsdaily"})
    assert findings == [] and lines[0]["status"] == "own"


def test_client_scoped_right_does_not_cover_another_client() -> None:
    perm = _entry("creator_permission", "Clips Daily", "@clipsdaily", client="Client B")
    findings, lines = _build(HANDLE_PROV, [perm])
    assert lines[0]["status"] == "missing"
    assert findings

    findings, lines = _build(HANDLE_PROV, [perm], client_label=None)
    assert lines[0]["status"] == "missing"

    own = _entry("creator_permission", "Clips Daily", "@clipsdaily", client="Client A")
    findings, lines = _build(HANDLE_PROV, [own])
    assert findings == [] and lines[0]["status"] == "covered"


def test_future_right_is_not_described_as_ended() -> None:
    future = _entry(
        "creator_permission", "Clips Daily", "@clipsdaily", starts=TODAY + timedelta(2)
    )
    findings, lines = _build(HANDLE_PROV, [future])
    assert lines[0]["status"] == "not_started"
    assert "not yet valid" in lines[0]["detail"]
    assert "ended" not in lines[0]["detail"]
    assert "not yet valid" in findings[0].explanation
    assert "ended" not in findings[0].explanation

    brand = _entry("brand_agreement", "FitFuel", "FitFuel", starts=TODAY + timedelta(2))
    findings, _lines = _build({}, [brand], caption="Loving my FitFuel shake every morning")
    assert "not yet valid" in findings[0].explanation
    assert "now ended" not in findings[0].explanation


def test_broadcaster_branding_and_footage_licence() -> None:
    prov = {
        "cues": {
            "handles": [],
            "broadcasters": [
                {"name": "Star Sports", "ref_id": "O3", "timestamp": 5.0, "text": "x"}
            ],
        }
    }
    findings, _ = _build(prov)
    assert findings[0].category == "licensing" and findings[0].severity == "medium"
    licence = _entry("footage_license", "Star India", "Star Sports")
    findings, lines = _build(prov, [licence])
    assert findings == [] and lines[0]["status"] == "covered"


def test_brand_agreement_requires_disclosure() -> None:
    brand = _entry("brand_agreement", "FitFuel", "FitFuel", "@fitfuel")
    findings, lines = _build({}, [brand], caption="Loving my FitFuel shake every morning")
    assert findings[0].category == "disclosure" and findings[0].severity == "high"
    assert findings[0].finding_type == "observed_evidence"

    findings, lines = _build({}, [brand], caption="#ad Loving my FitFuel shake")
    assert findings == [] and lines[0]["status"] == "covered"

    findings, _ = _build({}, [brand], caption="Nothing about brands here")
    assert findings == []


def _match(**kw: Any) -> dict[str, Any]:
    base = {
        "kind": "same_clip",
        "query_start": 0.0,
        "query_end": 12.0,
        "ref_start": 4.0,
        "ref_end": 16.0,
        "video_coverage": 0.9,
        "audio_coverage": 0.9,
        "owner_label": "Client B",
        "same_owner": False,
        "unlabelled": False,
        "source": "catalogue",
        "title": "Old post",
        "analysis_id": None,
        "fingerprint_id": "x",
    }
    return base | kw


def test_catalogue_matches_by_owner() -> None:
    other, _ = _build({"catalogue": {"matches": [_match()]}})
    assert other[0].title == "Footage also appears under another client: Client B"
    assert other[0].confidence == "high"

    own, lines = _build(
        {"catalogue": {"matches": [_match(owner_label="Client A", same_owner=True)]}}
    )
    assert own[0].severity == "low" and lines[0]["status"] == "own"

    draft, lines = _build({"catalogue": {"matches": [_match(same_owner=True, source="analysis")]}})
    assert draft == [] and lines[0]["status"] == "info"

    audio, lines = _build({"catalogue": {"matches": [_match(kind="same_audio")]}})
    assert audio == [] and lines[0]["status"] == "info"

    perm = _entry("creator_permission", "Client B")
    covered, lines = _build({"catalogue": {"matches": [_match()]}}, [perm])
    assert covered == [] and lines[0]["status"] == "covered"


def test_music_identification_and_licence() -> None:
    clip = {"matched": True, "title": "Kesariya", "artist": "Arijit Singh", "label": "Sony Music",
            "start": 2.0, "end": 14.0}  # fmt: skip
    prov = {"music": {"is_mock": False, "clips": [clip]}}
    findings, _ = _build(prov)
    assert findings[0].title.startswith("Identified music: “Kesariya” by Arijit Singh")
    assert findings[0].confidence == "high"
    licensed, lines = _build(prov, [_entry("music_license", "Sony Music India", "Sony Music")])
    assert licensed == [] and lines[0]["status"] == "covered"

    mock, _ = _build({"music": {"is_mock": True, "clips": [clip]}})
    assert mock[0].title.startswith("[MOCK]") and mock[0].confidence == "low"


def test_web_matches_become_a_finding() -> None:
    prov = {
        "web": {
            "is_mock": False,
            "frames": [
                {
                    "frame_id": "F2",
                    "timestamp": 4.0,
                    "pages": [
                        {"url": "https://news.example/a", "title": "Match report",
                         "domain": "news.example", "full_match": True}
                    ],
                }
            ],
        }
    }  # fmt: skip
    findings, _ = _build(prov)
    assert findings[0].severity == "medium"
    assert findings[0].evidence[0]["url"] == "https://news.example/a"


def test_brand_finding_absorbs_generic_promo_finding() -> None:
    promo = FindingDraft(
        source="deterministic",
        category="disclosure",
        finding_type="suspected_violation",
        severity="medium",
        confidence="medium",
        title=pipeline.PROMO_TITLE,
        explanation="x",
        suggested_action="y",
        evidence=[{"source": "caption", "ref_id": "T9", "detail": "code", "timestamp": None}],
    )
    brand, _ = _build({}, [_entry("brand_agreement", "FitFuel")], caption="FitFuel code FIT50")
    out = pipeline.fold_disclosure([promo, *brand])
    assert len(out) == 1 and out[0].source == "provenance"
    assert any(e["ref_id"] == "T9" for e in out[0].evidence)


# --------------------------------------------------------------------------- budget + lookups


def _transport(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], httpx.Client]:
    return lambda: httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def paid_env(monkeypatch: pytest.MonkeyPatch, settings_override: None) -> Iterator[None]:
    monkeypatch.setenv("MUSIC_ID_PROVIDER", "audd")
    monkeypatch.setenv("AUDD_API_TOKEN", "test-audd")
    monkeypatch.setenv("WEB_DETECTION_PROVIDER", "google")
    monkeypatch.setenv("GOOGLE_VISION_API_KEY", "test-vision")
    monkeypatch.setenv("PAID_LOOKUPS_MONTHLY_BUDGET_USD", "0.012")
    get_settings.cache_clear()
    yield


def test_pick_clips_prefers_long_music_stretches() -> None:
    clips = music.pick_clips([[0, 3], [5, 30], [40, 48]], 12, 2)
    assert clips == [(11.5, 23.5), (40.0, 48.0)]


@pytest.mark.slow
def test_music_lookup_caches_and_respects_budget(
    media: dict[str, Path], paid_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert b"test-audd" in request.content
        return httpx.Response(
            200,
            json={"status": "success", "result": {"artist": "A", "title": "T", "label": "L"}},
        )

    monkeypatch.setattr("app.provenance.music.get_http_client", _transport(handler))
    settings = get_settings()
    with get_sessionmaker()() as db:
        block = music.identify(db, media["rich"], tmp_path, [[0, 8], [8, 16]], settings, None)
        assert block["status"] == "completed"
        assert [c["title"] for c in block["clips"]] == ["T", "T"]
        assert len(calls) == 2
        assert round(budget.month_spend(db), 3) == 0.01

        # Same clips again: served from cache, no new call, no new cost.
        again = music.identify(db, media["rich"], tmp_path, [[0, 8], [8, 16]], settings, None)
        assert all(c["cached"] for c in again["clips"]) and len(calls) == 2

        # A new clip would take spend to 0.015 > 0.012: skipped, never called.
        over = music.identify(db, media["rich"], tmp_path, [[2, 9]], settings, None)
        assert over["status"] == "budget_exceeded" and len(calls) == 2
        assert db.query(PaidLookup).count() == 2


@pytest.mark.slow
def test_web_lookup_parses_google_response(
    media: dict[str, Path], paid_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    (frames_dir / "F1.jpg").write_bytes(media["thumb"].read_bytes())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["key"] == "test-vision"
        body = json.loads(request.content)
        assert body["requests"][0]["features"][0]["type"] == "WEB_DETECTION"
        return httpx.Response(
            200,
            json={
                "responses": [
                    {
                        "webDetection": {
                            "pagesWithMatchingImages": [
                                {
                                    "url": "https://www.stock.example/p/1",
                                    "pageTitle": "<b>Test</b> card",
                                    "fullMatchingImages": [{"url": "https://x/1.jpg"}],
                                }
                            ],
                            "bestGuessLabels": [{"label": "test card"}],
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("app.provenance.web.get_http_client", _transport(handler))
    frames = [{"id": "F1", "timestamp": 6.0, "reason": "scene", "file": "F1.jpg"}]
    with get_sessionmaker()() as db:
        block = web.search(db, frames, frames_dir, [], get_settings(), None)
    page = block["frames"][0]["pages"][0]
    assert page == {
        "url": "https://www.stock.example/p/1",
        "title": "Test card",
        "domain": "stock.example",
        "full_match": True,
    }


def test_lookups_off_without_keys() -> None:
    settings = get_settings()
    with get_sessionmaker()() as db:
        block = music.identify(db, Path("/nonexistent.mp4"), Path("/tmp"), [[0, 9]], settings, None)  # noqa: S108
    assert block["status"] == "not_configured"


@pytest.mark.slow
def test_youtube_lookalike_search(
    media: dict[str, Path], monkeypatch: pytest.MonkeyPatch, settings_override: None
) -> None:
    monkeypatch.setenv("YOUTUBE_SEARCH_API_KEY", "test-yt-key")
    get_settings.cache_clear()
    thumb_bytes = media["thumb"].read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "i.ytimg.com":
            return httpx.Response(200, content=thumb_bytes)
        assert request.url.path.endswith("/search")
        assert request.url.params["key"] == "test-yt-key"
        assert request.url.params["videoDuration"] == "short"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": {"videoId": "abcdefghijk"},
                        "snippet": {
                            "title": "Reupload",
                            "channelTitle": "Someone",
                            "channelId": "UCx",
                            "publishedAt": "2026-01-01T00:00:00Z",
                            "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/a/hq.jpg"}},
                        },
                    },
                    {
                        "id": {"videoId": "zzzzzzzzzzz"},
                        "snippet": {
                            "title": "Off-host thumbnail",
                            "thumbnails": {"high": {"url": "https://evil.example/t.jpg"}},
                        },
                    },
                ]
            },
        )

    monkeypatch.setattr("app.provenance.youtube_search.get_http_client", _transport(handler))
    fp = _fp(media["rich"])
    youtube_search._redis().delete(youtube_search._quota_key())
    with get_sessionmaker()() as db:
        block = youtube_search.search(
            db, "test card", fp.frame_hashes, fp.frame_step, get_settings()
        )
        assert block["results"][0]["visual_match"] == "strong"
        assert block["results"][1]["visual_match"] == "unknown"  # host not allow-listed
        assert youtube_search.quota_used() == 100

        monkeypatch.setenv("YOUTUBE_SEARCH_DAILY_UNIT_CAP", "150")
        get_settings.cache_clear()
        with pytest.raises(LookupFailed):
            youtube_search.search(db, "test card", fp.frame_hashes, fp.frame_step, get_settings())
    youtube_search._redis().delete(youtube_search._quota_key())


def test_suggested_query_skips_filler_words() -> None:
    q = youtube_search.suggest_query(
        "Morning routine with FitFuel #ad",
        None,
        [{"text": "today we make protein pancakes protein pancakes are easy"}],
    )
    assert q.startswith("Morning routine FitFuel") and "protein" in q and "#ad" not in q


# --------------------------------------------------------------------------- API end to end


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def _upload(client: TestClient, path: Path, label: str) -> str:
    with path.open("rb") as fh:
        res = client.post(
            "/api/analyses",
            files={"file": ("v.mp4", fh, "video/mp4")},
            data={"platform": "youtube_shorts", "language": "en", "client_label": label},
        )
    assert res.status_code == 202, res.text
    return str(res.json()["id"])


@pytest.mark.slow
def test_cross_client_match_ledger_and_evidence_pack(
    client: TestClient, media: dict[str, Path]
) -> None:
    # Index Client B's past post, then review a mirrored copy for Client A.
    with media["rich"].open("rb") as fh:
        res = client.post(
            "/api/catalogue",
            files={"file": ("old.mp4", fh, "video/mp4")},
            data={"owner_label": "Client B", "title": "B's viral clip"},
        )
    assert res.status_code == 201, res.text
    assert res.json()["entry"]["frames_hashed"] > 20
    assert client.get("/api/catalogue").json()[0]["owner_label"] == "Client B"

    aid = _upload(client, media["mirror"], "Client A")
    a = client.get(f"/api/analyses/{aid}").json()
    assert a["status"] == "completed", a["error_message"]
    match = a["provenance"]["catalogue"]["matches"][0]
    assert match["owner_label"] == "Client B" and match["video_coverage"] > 0.8
    cross = [f for f in a["findings"] if f["source"] == "provenance"]
    assert cross[0]["title"] == "Footage also appears under another client: Client B"
    assert all(len(f["policies"]) == len(f["policy_rule_ids"]) for f in cross)
    risk_before = a["risk_score"]

    # Recording permission (with a PDF proof) clears the finding on rebuild.
    res = client.post(
        "/api/rights",
        data={
            "kind": "creator_permission",
            "counterparty": "Client B",
            "reference": "Email 2026-10-01",
            "platforms": "youtube",
        },
        files={"proof": ("p.pdf", b"%PDF-1.4 permission", "application/pdf")},
    )
    assert res.status_code == 201, res.text
    record = res.json()
    assert record["has_proof"] and record["match_terms"] == ["Client B"]
    a = client.get(f"/api/analyses/{aid}").json()
    assert not [f for f in a["findings"] if f["source"] == "provenance"]
    assert a["risk_score"] < risk_before
    covered = [r for r in a["provenance"]["rights"] if r["area"] == "catalogue"]
    assert covered[0]["status"] == "covered"

    pack = client.get(f"/api/analyses/{aid}/evidence-pack.zip")
    assert pack.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(pack.content))
    names = set(zf.namelist())
    assert {"README.txt", "report.html", "manifest.json", "dispute-draft.txt"} <= names
    assert f"rights/{record['id']}-proof.pdf" in names
    manifest = json.loads(zf.read("manifest.json"))
    assert len(manifest["file"]["sha256"]) == 64
    draft = zf.read("dispute-draft.txt").decode()
    assert draft.startswith("DRAFT") and "Email 2026-10-01" in draft

    # Wrong file types are refused; deleting the record brings the finding back.
    bad = client.post(
        "/api/rights",
        data={"kind": "creator_permission", "counterparty": "X"},
        files={"proof": ("p.pdf", b"<html>", "application/pdf")},
    )
    assert bad.status_code == 415
    assert client.delete(f"/api/rights/{record['id']}").status_code == 204
    a = client.get(f"/api/analyses/{aid}").json()
    assert [f for f in a["findings"] if f["source"] == "provenance"]

    # An explicit delete removes the analysis' catalogue fingerprint too.
    assert client.delete(f"/api/analyses/{aid}").status_code == 204
    assert all(e["source"] == "catalogue" for e in client.get("/api/catalogue").json())


def test_rights_validation(client: TestClient) -> None:
    assert client.post("/api/rights", data={"kind": "nope", "counterparty": "x"}).status_code == 422
    res = client.post(
        "/api/rights",
        data={
            "kind": "music_license",
            "counterparty": "Epidemic Sound",
            "valid_from": "2026-01-01",
            "valid_until": "2025-01-01",
        },
    )
    assert res.status_code == 422
    status = client.get("/api/provenance/status").json()
    assert status["music_id"]["configured"] is False
    assert status["budget"]["spent_usd"] == 0


def test_risk_unchanged_by_info_lines() -> None:
    findings, lines = _build({"catalogue": {"matches": [_match(kind="same_audio")]}})
    assert compute_risk(findings) == (0, "low") and lines


def test_analysis_rebuild_is_idempotent() -> None:
    with get_sessionmaker()() as db:
        analysis = Analysis(
            expires_at=__import__("datetime").datetime.now().astimezone() + timedelta(hours=1),
            platform="youtube_shorts",
            language="en",
            caption="",
            hashtags=[],
            file_ext=".mp4",
            content_type="video/mp4",
            size_bytes=1,
            status="completed",
            provenance={"cues": HANDLE_PROV["cues"]},
            limitations=[],
        )
        db.add(analysis)
        db.commit()
        pipeline.rebuild(db, analysis)
        pipeline.rebuild(db, analysis)
        assert [f.source for f in analysis.findings] == ["provenance"]


def _fingerprint_row(**kw: Any) -> Any:
    from app.models import MediaFingerprint

    base = {
        "source": "analysis",
        "owner_label": "Client A",
        "duration_seconds": 10.0,
        "sha256": "0" * 64,
        "frame_step": 0.5,
        "frame_hashes": [],
        "audio_fp": [],
        "expires_at": __import__("datetime").datetime.now().astimezone() + timedelta(days=30),
    }
    return MediaFingerprint(**(base | kw))


def test_expiry_keeps_fingerprint_but_disconnect_and_delete_remove_it() -> None:
    from datetime import UTC, datetime

    from app.jobs import delete_analysis, purge_expired
    from app.models import MediaFingerprint, PlatformConnection

    with get_sessionmaker()() as db:
        conn = PlatformConnection(
            platform="youtube", external_id="UCx", display_name="Chan", access_token_enc="x"
        )
        db.add(conn)
        db.flush()

        def analysis(**kw: Any) -> Analysis:
            a = Analysis(
                expires_at=datetime.now(UTC) - timedelta(hours=1),
                platform="youtube_shorts",
                language="en",
                file_ext=".mp4",
                content_type="video/mp4",
                size_bytes=1,
                limitations=[],
                **kw,
            )
            db.add(a)
            db.flush()
            return a

        expired = analysis(connection_id=conn.id, source="youtube")
        db.add(_fingerprint_row(analysis_id=expired.id, connection_id=conn.id))
        kept = analysis()
        kept.expires_at = datetime.now(UTC) + timedelta(hours=1)
        db.add(_fingerprint_row(analysis_id=kept.id))
        db.commit()

        assert purge_expired(db) == 1
        rows = db.query(MediaFingerprint).all()
        assert len(rows) == 2  # expiry keeps the catalogue entry, detached from the analysis
        assert any(r.analysis_id is None and r.connection_id == conn.id for r in rows)

        delete_analysis(db, kept)  # explicit delete removes its fingerprint
        assert db.query(MediaFingerprint).count() == 1

        db.delete(conn)  # disconnect: the database cascades to the account's fingerprints
        db.commit()
        assert db.query(MediaFingerprint).count() == 0

        db.add(_fingerprint_row(expires_at=datetime.now(UTC) - timedelta(days=1)))
        db.commit()
        purge_expired(db)
        assert db.query(MediaFingerprint).count() == 0


def _ai(
    category: str, title: str, refs: list[str], text: str = "", severity: str = "medium"
) -> FindingDraft:
    return FindingDraft(
        source="ai",
        category=category,  # type: ignore[arg-type]
        finding_type="licensing_uncertainty",
        severity=severity,  # type: ignore[arg-type]
        confidence="medium",
        title=title,
        explanation=text,
        suggested_action="x",
        evidence=[{"source": "frame", "ref_id": r, "detail": "", "timestamp": 0.0} for r in refs],
    )


def licence_for_star() -> LedgerEntry:
    return _entry("footage_license", "Star India", "Star Sports")


def test_ai_duplicates_are_not_counted_twice_and_ledger_covers_ai_findings() -> None:
    from app.provenance.reconcile import reconcile

    prov = {
        "cues": {
            "handles": [],
            "broadcasters": [
                {"name": "Star Sports", "ref_id": "O1", "timestamp": 0.0, "text": "x"}
            ],
        }
    }
    extraction = {"ocr": [{"id": "O1", "frame_id": "F1", "timestamp": 0.0, "text": "x"}]}
    ai = _ai("licensing", "Broadcast footage present", ["F1"])
    unrelated = _ai("licensing", "Music bed", ["A1"], "background track")

    found, lines = _build(prov, extraction=extraction)
    drafts = [*found, ai, unrelated]
    reconcile(drafts, lines, prov, extraction)
    assert ai.rights_status == "duplicate" and unrelated.rights_status is None
    assert any("Also flagged by the AI review" in n for n in found[0].validation_notes)
    counted_once = compute_risk([found[0], unrelated])
    assert compute_risk(drafts) == counted_once

    # When the AI rates it more severe, the AI finding is counted instead.
    severe = _ai("licensing", "Broadcast footage present", ["F1"], severity="high")
    found, lines = _build(prov, extraction=extraction)
    reconcile([*found, severe], lines, prov, extraction)
    assert severe.rights_status is None and found[0].rights_status == "duplicate"
    assert compute_risk([*found, severe]) == compute_risk([severe])

    # An AI finding that matches several provenance findings absorbs all of them.
    both = {
        "cues": {
            "handles": [{"handle": "@clipsdaily", "ref_id": "O1", "timestamp": 0.0, "text": "x"}],
            "broadcasters": prov["cues"]["broadcasters"],
        }
    }
    found, lines = _build(both, extraction=extraction)
    severe = _ai("licensing", "Broadcast footage via @clipsdaily", ["F1"], severity="high")
    reconcile([*found, severe], lines, both, extraction)
    assert len(found) == 2 and all(p.rights_status == "duplicate" for p in found)

    # Permission covers licensing findings, but not originality ones.
    perm = _entry("creator_permission", "Clips Daily", "@clipsdaily")
    found, lines = _build(both, [perm, licence_for_star()], extraction=extraction)
    repost = _ai("originality", "Reposted clip from @clipsdaily", ["F1"])
    reconcile([*found, repost], lines, both, extraction)
    assert repost.rights_status is None and "still counts" in (repost.rights_note or "")

    licence = _entry("footage_license", "Star India", "Star Sports")
    found, lines = _build(prov, [licence], extraction=extraction)
    drafts = [*found, ai, unrelated]
    reconcile(drafts, lines, prov, extraction)
    assert found == []
    assert ai.rights_status == "covered" and "footage" in (ai.rights_note or "")
    assert compute_risk(drafts) == compute_risk([unrelated])


def test_reconcile_does_not_match_short_substrings() -> None:
    from app.provenance.reconcile import reconcile

    clip = {
        "matched": True,
        "title": "Apple",
        "artist": "Someone",
        "start": 0.0,
        "end": 8.0,
    }
    prov = {"music": {"is_mock": False, "clips": [clip]}}
    licence = _entry("music_license", "Label", "Apple")
    found, lines = _build(prov, [licence])
    assert found == [] and lines[0]["status"] == "covered"
    pineapple = _ai("licensing", "Pineapple smoothie tips", [], "free to use pineapple")
    apple = _ai("licensing", "The track Apple is in the bed", [], "song Apple")
    reconcile([pineapple, apple], lines, prov, {})
    assert pineapple.rights_status is None
    assert apple.rights_status == "covered"

    news = {
        "cues": {
            "handles": [{"handle": "@news", "ref_id": "O1", "timestamp": 1.0, "text": "@news"}],
            "broadcasters": [],
        }
    }
    found, lines = _build(news, [_entry("creator_permission", "News", "@news")])
    assert lines[0]["status"] == "covered"
    paper = _ai("licensing", "Newspaper delivery route", [], "today's newspaper")
    reconcile([*found, paper], lines, news, {})
    assert paper.rights_status is None


def test_identical_file_under_three_seconds_is_kept() -> None:
    from app.provenance.catalogue import find_matches
    from app.provenance.fingerprint import Fingerprint

    with get_sessionmaker()() as db:
        db.add(_fingerprint_row(sha256="ab" * 32, duration_seconds=1.5, owner_label="Client A"))
        db.commit()
        fp = Fingerprint(duration_seconds=1.5, sha256="ab" * 32)
        found = find_matches(db, fp, "Client B", None, get_settings())
    assert [m["kind"] for m in found["matches"]] == ["identical_file"]


def test_ai_disclosure_finding_folds_into_brand_finding() -> None:
    from app.provenance.reconcile import reconcile

    brand = _entry("brand_agreement", "FitFuel")
    found, lines = _build({}, [brand], caption="FitFuel shake, code FIT50")
    ai = _ai("disclosure", "Possible undisclosed promotion of FitFuel", ["CAPTION"])
    asci = _ai("disclosure", "ASCI on-screen label", ["CAPTION"], "India rules")
    reconcile([*found, ai, asci], lines, {}, {})
    assert ai.rights_status == "duplicate" and asci.rights_status is None
