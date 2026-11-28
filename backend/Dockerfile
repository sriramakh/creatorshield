FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg libchromaprint-tools tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
# /app/var is the media volume: storage, upload spool (UPLOAD_TMP_DIR) and model cache.
# A fresh named volume copies this ownership; the app recreates missing subfolders.
RUN useradd --create-home --uid 1001 app \
 && mkdir -p /app/var/storage /app/var/tmp /app/var/hf \
 && chown -R app /app/var
USER app

ENV PATH="/app/.venv/bin:$PATH" UPLOAD_TMP_DIR=/app/var/tmp HF_HOME=/app/var/hf
EXPOSE 8000
# Healthchecks are defined per service in the compose files (API: /api/health/ready,
# worker: python -m app.worker --check); the same image runs both.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
