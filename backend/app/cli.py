"""Maintenance commands.

python -m app.cli purge-expired      # delete analyses past retention
python -m app.cli delete-all          # delete every analysis and its media
python -m app.cli check-kb            # validate the policy knowledge base
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.config import get_settings
from app.db import get_sessionmaker
from app.jobs import delete_analysis, purge_expired
from app.models import Analysis
from app.policies.kb import load_kb


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "purge-expired":
        with get_sessionmaker()() as db:
            print(f"purged {purge_expired(db)} analyses")
        return 0
    if cmd == "delete-all":
        with get_sessionmaker()() as db:
            rows = db.scalars(select(Analysis)).all()
            for a in rows:
                delete_analysis(db, a)
            print(f"deleted {len(rows)} analyses")
        return 0
    if cmd == "check-kb":
        kb = load_kb(get_settings().policy_kb_path)
        print(f"policy KB {kb.version}: {len(kb.rules)} rules OK")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
