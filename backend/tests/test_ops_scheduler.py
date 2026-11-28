"""Scheduler and log redaction (no database needed)."""

from __future__ import annotations

import asyncio
import logging
import sys

import pytest

from app import jobs
from app.logging_config import RedactingFormatter, RedactSecrets, redact


def test_maintenance_loop_runs_at_start_and_on_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(jobs, "run_maintenance", lambda: calls.append(1) or {})

    async def run() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(jobs.maintenance_loop(0.02, stop))
        await asyncio.sleep(0.15)
        stop.set()
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(run())
    assert len(calls) >= 3


def test_maintenance_loop_survives_a_failing_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def boom() -> None:
        calls.append(1)
        raise RuntimeError("database unreachable")

    monkeypatch.setattr(jobs, "run_maintenance", boom)

    async def run() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(jobs.maintenance_loop(0.02, stop))
        await asyncio.sleep(0.1)
        stop.set()
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(run())
    assert len(calls) >= 2


def test_worker_maintenance_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    ran = threading.Event()
    monkeypatch.setattr(jobs, "run_maintenance", lambda: ran.set() or {})
    thread, stop = jobs.start_maintenance_thread(0.01)
    assert ran.wait(2)
    stop.set()
    thread.join(2)
    assert not thread.is_alive()


@pytest.mark.parametrize(
    "secret",
    [
        "sk-ant-api03-abcdefghijklmnop",
        "AIzaSyA1234567890abcdefghijklmnopqrstuv",
        "ya29.a0AfH6SMBx-secret_token.value",
        "IGQWRPa1ZAabcdefghijklmnopqrstuvwxyz0123",
        "EAAGm0PX4ZCpsBAabcdefghijklmnop",
        "gAAAAABlZ2V0aGlzaXNhZmVybmV0dG9rZW5fZm9yX3Rlc3Rz",
        "q7f0nxqv1Ztq3oV8b1yV7Tq0QnCw5kq3m8y5Yk2fZcA=",
    ],
)
def test_redacts_tokens(secret: str) -> None:
    assert secret not in redact(f"failed with {secret} in it")


@pytest.mark.parametrize(
    ("text", "leak"),
    [
        ("Authorization: Basic YWdlbmN5OnNlY3JldHBhc3M=", "YWdlbmN5OnNlY3JldHBhc3M="),
        ("headers={'authorization': 'Bearer abcdef123456'}", "abcdef123456"),
        (
            "GET https://vision.googleapis.com/v1/images:annotate?key=XYZsecret1 HTTP/1.1",
            "XYZsecret1",
        ),
        ("callback ?code=4/0AbCdEf&state=s3cr3tstate", "4/0AbCdEf"),
        ("url=https://x/?access_token=tok123&fields=id", "tok123"),
        ('{"refresh_token": "1//0gabc", "client_secret": "GOCSPX-abc"}', "GOCSPX-abc"),
        ("postgresql+psycopg://creatorshield:hunter2pw@postgres:5432/db", "hunter2pw"),
    ],
)
def test_redacts_labelled_values(text: str, leak: str) -> None:
    out = redact(text)
    assert leak not in out and "[REDACTED]" in out


def test_redaction_keeps_ordinary_text() -> None:
    text = "analysis 5f1c completed: 3 findings, risk=medium (Basic plan)"
    assert redact(text) == text


def test_filter_redacts_exception_text_and_keeps_args_shape() -> None:
    try:
        raise RuntimeError("upstream rejected key=AIzaSyA1234567890abcdefghijklmnopqrstuv")
    except RuntimeError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        "x",
        logging.ERROR,
        __file__,
        1,
        '%s - "%s %s"',
        ("1.2.3.4", "GET", "/cb?code=abc123"),
        exc_info,
    )
    RedactSecrets().filter(record)
    assert isinstance(record.args, tuple) and len(record.args) == 3
    assert "abc123" not in record.getMessage()
    assert record.exc_text and "AIzaSy" not in record.exc_text
    line = RedactingFormatter("%(message)s").format(record)
    assert "AIzaSy" not in line and "abc123" not in line
