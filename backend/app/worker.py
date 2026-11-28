"""Background worker: ``python -m app.worker`` (``--check`` for the container healthcheck).

Uses RQ's SimpleWorker (no fork per job). On macOS this avoids Objective-C
fork-safety crashes, and it keeps the speech-to-text model loaded in memory
between jobs instead of reloading it for every video.
"""

from __future__ import annotations

import logging
import socket
import sys

from rq import SimpleWorker, Worker

from app.config import get_settings
from app.jobs import get_queue, get_redis, run_maintenance, start_maintenance_thread
from app.logging_config import configure_logging

log = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    from app.auth import verify_agency_database

    verify_agency_database(settings)
    configure_logging(settings.log_level)
    # Startup pass: retention, analyses left "processing" by a crashed worker,
    # orphaned files. Then repeat on a schedule beside the job loop.
    run_maintenance()
    if settings.maintenance_interval_seconds > 0:
        start_maintenance_thread(settings.maintenance_interval_seconds)
    log.info(
        "worker starting: queue=%s provider=%s stt=%s/%s",
        settings.queue_name,
        settings.ai_provider,
        settings.stt_provider,
        settings.whisper_model,
    )
    worker = SimpleWorker([get_queue()], connection=get_redis())
    worker.work(with_scheduler=False)


def healthcheck() -> int:
    """0 when a worker on this host is registered in Redis (its key expires if it dies)."""
    try:
        host = socket.gethostname()
        alive = any(w.hostname == host for w in Worker.all(connection=get_redis()))
    except Exception:
        return 1
    return 0 if alive else 1


if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        raise SystemExit(healthcheck())
    main()
