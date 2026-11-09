"""Background worker: ``python -m app.worker``.

Uses RQ's SimpleWorker (no fork per job). On macOS this avoids Objective-C
fork-safety crashes, and it keeps the speech-to-text model loaded in memory
between jobs instead of reloading it for every video.
"""

from __future__ import annotations

import logging

from rq import SimpleWorker

from app.config import get_settings
from app.db import get_sessionmaker
from app.jobs import get_queue, get_redis, purge_expired
from app.logging_config import configure_logging

log = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    from app.auth import verify_agency_database

    verify_agency_database(settings)
    configure_logging(settings.log_level)
    with get_sessionmaker()() as db:
        purge_expired(db)
    log.info(
        "worker starting: queue=%s provider=%s stt=%s/%s",
        settings.queue_name,
        settings.ai_provider,
        settings.stt_provider,
        settings.whisper_model,
    )
    worker = SimpleWorker([get_queue()], connection=get_redis())
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
