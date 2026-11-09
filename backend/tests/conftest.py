"""Test configuration.

Tests use the separate ``creatorshield_test`` database, a temporary storage
directory, inline job execution and the mock AI provider. No paid API is called.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

_STORAGE = tempfile.mkdtemp(prefix="creatorshield-test-")
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+psycopg://creatorshield:creatorshield_dev@localhost:5432/creatorshield_test",
        ),
        "USE_JOB_QUEUE": "false",
        "STORAGE_DIR": _STORAGE,
        "AI_PROVIDER": "mock",
        "ANTHROPIC_API_KEY": "",
        "OPENAI_API_KEY": "",
        "LOG_LEVEL": "WARNING",
        # Connected accounts: test credentials; HTTP goes to tests/fake_platforms.py
        "TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "INSTAGRAM_APP_ID": "test-ig-app",
        "INSTAGRAM_APP_SECRET": "test-ig-secret",
        "GOOGLE_CLIENT_ID": "test-google-client",
        "GOOGLE_CLIENT_SECRET": "test-google-secret",
        "YOUTUBE_CAPTIONS_SCOPE": "false",
    }
)

from app.config import get_settings  # noqa: E402
from app.db import Base, get_engine  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SAMPLES = REPO / "samples"


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    get_settings.cache_clear()
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    shutil.rmtree(_STORAGE, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    with get_engine().begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def settings_override() -> Iterator[None]:
    """Clears the settings cache after a test that mutates os.environ."""
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def sample_promo_en() -> Path:
    path = SAMPLES / "sample_promo_en.mp4"
    if not path.exists():
        pytest.skip("run samples/generate_samples.py first")
    return path


@pytest.fixture(scope="session")
def long_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A synthetic 62-second clip (exceeds the 60s limit)."""
    out = tmp_path_factory.mktemp("media") / "long.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x284:d=62",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono",
            "-t",
            "62",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-shortest",
            str(out),
        ],
        check=True,
    )
    return out
