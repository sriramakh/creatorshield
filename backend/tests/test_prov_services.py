"""Regression tests that need the database / Redis: stale coverage, the evidence pack,
client-scoped connected accounts, paid-lookup budget concurrency, network failures and
OAuth hardening. External services are fakes (httpx.MockTransport, tests.fake_platforms)."""

from __future__ import annotations

import io
import json
import threading
import uuid
import zipfile
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import get_sessionmaker
from app.integrations import common, connections
from app.integrations import youtube as yt
from app.integrations.common import IntegrationError
from app.integrations.importer import download
from app.main import app
from app.models import Analysis, PaidLookup, PlatformConnection, RightsRecord
from app.provenance import budget, music, pipeline, web, youtube_search
from app.provenance.common import LookupFailed, ProviderMayHaveBilled
from app.provenance.ledger import connected_accounts_for
from tests import fake_platforms

HANDLE_CUES = {
    "cues": {
        "handles": [{"handle": "@clipsdaily", "ref_id": "O1", "timestamp": 1.0, "text": "x"}],
        "broadcasters": [],
    }
}


def _analysis(db: Any, **kw: Any) -> Analysis:
    base: dict[str, Any] = {
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "platform": "youtube_shorts",
        "language": "en",
        "caption": "",
        "hashtags": [],
        "file_ext": ".mp4",
        "content_type": "video/mp4",
        "size_bytes": 1,
        "status": "completed",
        "provenance": json.loads(json.dumps(HANDLE_CUES)),
        "limitations": [],
        "client_label": "Client A",
    }
    a = Analysis(**(base | kw))
    db.add(a)
    db.commit()
    return a


def _permission(db: Any, **kw: Any) -> RightsRecord:
    base: dict[str, Any] = {
        "kind": "creator_permission",
        "counterparty": "Clips Daily",
        "match_terms": ["@clipsdaily"],
        "platforms": [],
        "reference": "Email 1",
        "notes": "private fee: $500",
    }
    rec = RightsRecord(**(base | kw))
    db.add(rec)
    db.commit()
    return rec


def _handle_status(a: Analysis) -> str:
    lines = (a.provenance or {}).get("rights") or []
    return next(line["status"] for line in lines if line["area"] == "handle")


# --------------------------------------------------------------------------- 1: stale coverage


def test_coverage_is_rederived_when_the_day_or_the_ledger_changes() -> None:
    with get_sessionmaker()() as db:
        rec = _permission(db, valid_until=date.today())
        a = _analysis(db)
        pipeline.rebuild(db, a)
        assert _handle_status(a) == "covered"
        assert not pipeline.ensure_current(db, a)  # same day, same ledger: no work

        # The licence lapses overnight: yesterday's derivation is stale.
        rec.valid_until = date.today() - timedelta(days=1)
        prov = dict(a.provenance or {})
        prov["rights_checked_on"] = (date.today() - timedelta(days=1)).isoformat()
        prov["ledger_digest"] = "old"
        a.provenance = prov
        db.commit()
        assert pipeline.ensure_current(db, a)
        assert _handle_status(a) == "expired"
        assert [f.source for f in a.findings] == ["provenance"]

        # A ledger change made without a rebuild (e.g. directly in the DB) is noticed.
        db.delete(rec)
        db.commit()
        assert pipeline.ensure_current(db, a)
        assert _handle_status(a) == "missing"


def test_ledger_changes_rebuild_every_completed_analysis_in_batches() -> None:
    with get_sessionmaker()() as db:
        ids = [_analysis(db).id for _ in range(7)]
        _permission(db)
        assert pipeline.rebuild_all(db, batch_size=2) == 7
        for aid in ids:
            a = db.get(Analysis, aid)
            assert a is not None and _handle_status(a) == "covered"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def _pack(client: TestClient, aid: uuid.UUID) -> zipfile.ZipFile:
    res = client.get(f"/api/analyses/{aid}/evidence-pack.zip")
    assert res.status_code == 200, res.text
    return zipfile.ZipFile(io.BytesIO(res.content))


def test_evidence_pack_never_relies_on_a_lapsed_or_deleted_record(client: TestClient) -> None:
    with get_sessionmaker()() as db:
        rec = _permission(db)
        a = _analysis(db)
        pipeline.rebuild(db, a)
        assert _handle_status(a) == "covered"
        aid, rid = a.id, rec.id
        # Lapse the record behind the stored coverage without rebuilding anything.
        rec.valid_until = date.today() - timedelta(days=2)
        db.commit()

    draft = _pack(client, aid).read("dispute-draft.txt").decode()
    assert "is used under" not in draft and "No active rights-ledger entries" in draft

    with get_sessionmaker()() as db:
        rec2 = db.get(RightsRecord, rid)
        assert rec2 is not None
        rec2.valid_until = None
        db.commit()
    zf = _pack(client, aid)
    assert (
        "is used under Permission from a creator with Clips Daily"
        in zf.read("dispute-draft.txt").decode()
    )
    records = json.loads(zf.read("rights/records.json"))
    assert [r["id"] for r in records] == [str(rid)]
    assert "notes" not in records[0]  # private notes stay in the workspace

    with get_sessionmaker()() as db:
        db.delete(db.get(RightsRecord, rid))
        db.commit()
    zf = _pack(client, aid)
    assert "is used under" not in zf.read("dispute-draft.txt").decode()
    assert json.loads(zf.read("rights/records.json")) == []


def test_evidence_pack_redacts_other_clients_and_attaches_only_relied_records(
    client: TestClient,
) -> None:
    match = {
        "kind": "same_clip",
        "query_start": 0.0,
        "query_end": 12.0,
        "ref_start": 0.0,
        "ref_end": 12.0,
        "video_coverage": 0.9,
        "audio_coverage": 0.9,
        "owner_label": "Client C",
        "same_owner": False,
        "unlabelled": False,
        "source": "catalogue",
        "title": "C launch teaser",
        "analysis_id": str(uuid.uuid4()),
        "fingerprint_id": str(uuid.uuid4()),
    }
    with get_sessionmaker()() as db:
        ended = _permission(db, valid_until=date.today() - timedelta(days=5))
        brand = RightsRecord(
            kind="brand_agreement",
            counterparty="FitFuel",
            match_terms=["FitFuel"],
            platforms=[],
            reference="contract",
            notes="fee 1000",
        )
        db.add(brand)
        db.commit()
        a = _analysis(
            db,
            caption="#ad FitFuel shake",
            provenance={
                **json.loads(json.dumps(HANDLE_CUES)),
                "catalogue": {"owner_label": "Client A", "matches": [match]},
            },
        )
        pipeline.rebuild(db, a)
        aid, ended_id, brand_id = a.id, ended.id, brand.id

    zf = _pack(client, aid)
    everything = " ".join(zf.read(n).decode("utf-8", "replace") for n in zf.namelist())
    assert "Client C" not in everything and "C launch teaser" not in everything
    assert match["analysis_id"] not in everything
    assert "another client in this workspace" in everything
    ids = {r["id"] for r in json.loads(zf.read("rights/records.json"))}
    assert str(ended_id) not in ids and str(brand_id) not in ids  # expired / info only


# --------------------------------------------------------------------------- 3: connected accounts


def _conn(db: Any, platform: str, external_id: str, username: str) -> PlatformConnection:
    c = PlatformConnection(
        platform=platform,
        external_id=external_id,
        display_name="@" + username,
        account_meta={"username": username, "custom_url": "@" + username},
        access_token_enc="x",
    )
    db.add(c)
    db.commit()
    return c


def test_connected_accounts_count_as_own_only_for_their_client_and_platform() -> None:
    with get_sessionmaker()() as db:
        ig_a = _conn(db, "instagram", "1", "client_a")
        ig_b = _conn(db, "instagram", "2", "client_b")
        yt_a = _conn(db, "youtube", "UCa", "client_a_yt")
        _analysis(db, client_label="Client A", connection_id=ig_a.id, platform="instagram_reels")
        _analysis(db, client_label="Client B", connection_id=ig_b.id, platform="instagram_reels")

        for_a = connected_accounts_for(db, platform="instagram_reels", client_label="Client A")
        assert "client_a" in for_a.own and "client_b" in for_a.review
        assert "client_a_yt" in for_a.review  # other platform: review, not own

        # A YouTube channel with no history in a two-client workspace is not assumed own.
        yt_view = connected_accounts_for(db, platform="youtube_shorts", client_label="Client A")
        assert "client_a_yt" in yt_view.review and yt_view.own_channel_ids == set()
        # ...but the account an analysis was imported through always is.
        via = connected_accounts_for(
            db, platform="youtube_shorts", client_label="Client A", connection_id=yt_a.id
        )
        assert via.own_channel_ids == {"UCa"}


def test_single_client_workspace_keeps_unlabelled_connections_as_own() -> None:
    with get_sessionmaker()() as db:
        _conn(db, "instagram", "1", "solo")
        _analysis(db, client_label=None, platform="instagram_reels")
        out = connected_accounts_for(db, platform="instagram_reels", client_label=None)
        assert out.own == {"solo"}


def test_youtube_search_does_not_hide_another_clients_channel(
    monkeypatch: pytest.MonkeyPatch, settings_override: None
) -> None:
    monkeypatch.setenv("YOUTUBE_SEARCH_API_KEY", "k")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        items = [
            {"id": {"videoId": f"vid0000000{i}"}, "snippet": {"channelId": ch, "title": ch}}
            for i, ch in enumerate(("UCmine", "UCother"))
        ]
        return httpx.Response(200, json={"items": items})

    monkeypatch.setattr(
        youtube_search,
        "get_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    youtube_search._redis().delete(youtube_search._quota_key())
    with get_sessionmaker()() as db:
        block = youtube_search.search(db, "query words", [], 0.5, get_settings(), {"UCmine"})
    youtube_search._redis().delete(youtube_search._quota_key())
    own = {r["channel_id"]: r["own_channel"] for r in block["results"]}
    assert own == {"UCmine": True, "UCother": False}


# --------------------------------------------------------------------------- 6: network failures


class _Drip(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield b"x" * 1024
        raise httpx.ReadTimeout("stalled")


def test_download_removes_partial_files_and_reports_network_errors(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "video/mp4"}, stream=_Drip())

    dest = tmp_path / "video.mp4"
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as http,
        pytest.raises(IntegrationError, match="could not be reached"),
    ):
        download(
            http, "https://x.cdninstagram.com/v.mp4", dest,
            allowed=["cdninstagram.com"], max_bytes=10_000, kind="video",
        )  # fmt: skip
    assert not dest.exists()

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with httpx.Client(transport=httpx.MockTransport(refuse)) as http:
        with pytest.raises(IntegrationError, match="could not be reached"):
            common.send(http, "Instagram", "GET", "https://graph.instagram.com/me")
        client = yt.YouTubeClient(http, get_settings())
        with pytest.raises(IntegrationError):
            client.videos("t", ["abcdefghijk"])


def test_instagram_thumbnail_network_failure_falls_back_to_caption_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations import importer

    item = {
        "id": "1",
        "media_type": "VIDEO",
        "caption": "hello #x",
        "thumbnail_url": "https://x.cdninstagram.com/t.jpg",
    }
    monkeypatch.setattr(importer.ig.InstagramClient, "media", lambda self, mid, tok: item)

    def boom(*a: Any, **k: Any) -> int:
        raise httpx.ReadTimeout("slow cdn")

    monkeypatch.setattr(importer, "download", boom)
    with get_sessionmaker()() as db:
        a = _analysis(db, source="instagram", source_media_id="1", platform="instagram_reels")
        with httpx.Client() as http:
            out = importer._prepare_instagram(db, a, get_settings(), http, "token")
    assert out is not None and out["frames"] == []
    assert any("could not be analysed" in w for w in out["warnings"])


def _client_factory(
    handler: Callable[[httpx.Request], httpx.Response],
) -> Callable[[], httpx.Client]:
    return lambda: httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def paid_env(monkeypatch: pytest.MonkeyPatch, settings_override: None) -> Iterator[None]:
    monkeypatch.setenv("MUSIC_ID_PROVIDER", "audd")
    monkeypatch.setenv("AUDD_API_TOKEN", "t")
    monkeypatch.setenv("WEB_DETECTION_PROVIDER", "google")
    monkeypatch.setenv("GOOGLE_VISION_API_KEY", "k")
    monkeypatch.setenv("PAID_LOOKUPS_MONTHLY_BUDGET_USD", "1.0")
    get_settings.cache_clear()
    yield


def test_unreadable_provider_answers_are_handled(paid_env: None) -> None:
    def garbage(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>oops</html>")

    with httpx.Client(transport=httpx.MockTransport(garbage)) as http:
        with pytest.raises(ProviderMayHaveBilled):
            music._audd(b"clip", get_settings(), http)
        with pytest.raises(ProviderMayHaveBilled):
            web._google([b"img"], get_settings(), http)


def test_youtube_search_unreadable_answer_is_a_lookup_failure(
    monkeypatch: pytest.MonkeyPatch, settings_override: None
) -> None:
    monkeypatch.setenv("YOUTUBE_SEARCH_API_KEY", "k")
    get_settings.cache_clear()
    monkeypatch.setattr(
        youtube_search,
        "get_http_client",
        _client_factory(lambda r: httpx.Response(200, content=b"not json")),
    )
    youtube_search._redis().delete(youtube_search._quota_key())
    with get_sessionmaker()() as db, pytest.raises(LookupFailed, match="unreadable"):
        youtube_search.search(db, "query words", [], 0.5, get_settings())
    youtube_search._redis().delete(youtube_search._quota_key())


# --------------------------------------------------------------------------- 7: budget


def _acquire(db: Any, key: str, cost: float = 0.6, **kw: Any) -> Any:
    return budget.acquire(
        db,
        service="music_id",
        provider="audd",
        key=key,
        est_cost=cost,
        settings=get_settings(),
        analysis_id=None,
        **kw,
    )


def test_concurrent_reservations_cannot_exceed_the_budget(paid_env: None) -> None:
    results: list[str] = []
    barrier = threading.Barrier(4)

    def worker(i: int) -> None:
        with get_sessionmaker()() as db:
            barrier.wait()
            try:
                _acquire(db, f"{i:064x}")
                results.append("reserved")
            except budget.BudgetExceeded:
                results.append("refused")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["refused", "refused", "refused", "reserved"]
    with get_sessionmaker()() as db:
        assert budget.month_spend(db) == pytest.approx(0.6)


def test_identical_concurrent_request_waits_for_the_first_answer(paid_env: None) -> None:
    key = "c" * 64
    with get_sessionmaker()() as db:
        hit, res = _acquire(db, key, cost=0.1)
        assert hit is None and res is not None
        sleeps: list[float] = []

        def settle_while_waiting(seconds: float) -> None:
            sleeps.append(seconds)
            with get_sessionmaker()() as other:
                budget.settle(other, res, {"matched": True, "title": "T"})

        with get_sessionmaker()() as db2:
            hit2, res2 = _acquire(db2, key, cost=0.1, sleep=settle_while_waiting)
        assert sleeps and res2 is None and hit2 == {"matched": True, "title": "T"}
        assert db.query(PaidLookup).count() == 1  # paid once


def test_timeouts_keep_the_charge_but_never_become_a_cache_entry(
    paid_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider still working")

    monkeypatch.setattr(music, "cut_clip", lambda *a, **k: b"clip-bytes")
    monkeypatch.setattr(music, "get_http_client", _client_factory(slow))
    settings = get_settings()
    with get_sessionmaker()() as db:
        block = music.identify(db, Path("v.mp4"), Path("."), [[0, 12]], settings, None)
        assert block["status"] == "partial"
        assert budget.month_spend(db) == pytest.approx(settings.audd_cost_per_request_usd)
        key = budget.cache_key("music_id", "audd", b"clip-bytes")
        assert budget.cached(db, key, settings) is None

    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    monkeypatch.setattr(music, "get_http_client", _client_factory(refused))
    with get_sessionmaker()() as db:
        before = budget.month_spend(db)
        music.identify(db, Path("v.mp4"), Path("."), [[0, 12]], settings, None)
        assert budget.month_spend(db) == pytest.approx(before)  # never sent: released


# --------------------------------------------------------------------------- 12: OAuth


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    fake_platforms.STATE.update({"revoked": [], "token_requests": []})
    for knob in ("last_scope", "rotate_refresh", "revoke_fails"):
        fake_platforms.STATE.pop(knob, None)

    def factory() -> TestClient:
        return TestClient(fake_platforms.app, follow_redirects=False)

    monkeypatch.setattr("app.integrations.connections.get_http_client", factory)
    yield fake_platforms.STATE
    for knob in ("rotate_refresh", "revoke_fails"):
        fake_platforms.STATE.pop(knob, None)


def _yt_connection(db: Any) -> PlatformConnection:
    conn = PlatformConnection(
        platform="youtube",
        external_id=fake_platforms.YT_CHANNEL,
        display_name="Chan",
        account_meta={},
        access_token_enc=common.encrypt_token(fake_platforms.YT_ACCESS),
        refresh_token_enc=common.encrypt_token(fake_platforms.YT_REFRESH),
        token_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db.add(conn)
    db.commit()
    return conn


def test_rotated_refresh_tokens_are_persisted(fake: dict[str, Any]) -> None:
    fake["rotate_refresh"] = True
    with get_sessionmaker()() as db:
        conn = _yt_connection(db)
        assert connections.access_token(db, conn, get_settings()) == fake_platforms.YT_ACCESS
        db.refresh(conn)
        assert conn.refresh_token_enc is not None
        assert common.decrypt_token(conn.refresh_token_enc) == fake_platforms.YT_REFRESH_ROTATED


def test_failed_revocation_is_reported_and_local_data_still_deleted(fake: dict[str, Any]) -> None:
    fake["revoke_fails"] = True
    with get_sessionmaker()() as db:
        conn = _yt_connection(db)
        _analysis(db, connection_id=conn.id, source="youtube")
        out = connections.disconnect_account(db, conn, get_settings())
        assert out.revoked is False and out.revoke_error and "revocation" in out.revoke_error
        assert out.deleted_analyses == 1
        assert db.query(PlatformConnection).count() == 0
    fake.pop("revoke_fails")
    with get_sessionmaker()() as db:
        out = connections.disconnect_account(db, _yt_connection(db), get_settings())
        assert out.revoked is True


def test_revoke_checks_googles_answer() -> None:
    def answer(status: int, body: dict[str, Any]) -> httpx.Client:
        return httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body))
        )

    with answer(200, {}) as http:
        yt.YouTubeClient(http, get_settings()).revoke("t")
    with answer(400, {"error": "invalid_token"}) as http:
        yt.YouTubeClient(http, get_settings()).revoke("t")  # already revoked: fine
    with answer(500, {"error": "backend"}) as http, pytest.raises(IntegrationError):
        yt.YouTubeClient(http, get_settings()).revoke("t")


def test_oauth_state_can_be_bound_to_the_initiating_session() -> None:
    state = common.create_oauth_state("youtube", {"verifier": "v"}, binding="session-1")
    with pytest.raises(IntegrationError, match="browser session"):
        common.consume_oauth_state(state, "youtube", binding="session-2")
    state = common.create_oauth_state("youtube", {"verifier": "v"}, binding="session-1")
    assert common.consume_oauth_state(state, "youtube", binding="session-1")["verifier"] == "v"
    unbound = common.create_oauth_state("instagram")
    assert common.consume_oauth_state(unbound, "instagram")["platform"] == "instagram"


def test_search_quota_counts_pacific_days() -> None:
    # 06:30 UTC on 1 Nov is still 31 Oct (23:30 PDT) in California, where the quota resets.
    assert youtube_search._quota_day(datetime(2026, 11, 1, 6, 30, tzinfo=UTC)) == "2026-10-31"
    assert youtube_search._quota_day(datetime(2026, 11, 1, 9, 30, tzinfo=UTC)) == "2026-11-01"


def test_reconnect_without_a_new_refresh_token_keeps_the_stored_one() -> None:
    with get_sessionmaker()() as db:
        conn = _yt_connection(db)
        stored = conn.refresh_token_enc
        connections._upsert(
            db, "youtube", conn.external_id, display_name="Chan", refresh_token_enc=None
        )
        db.refresh(conn)
        assert conn.refresh_token_enc == stored
