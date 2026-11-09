"""Application settings, loaded from environment variables / .env.

Secrets (API keys) are read here and nowhere else. They are never logged and
never returned by any API endpoint - `public_summary()` exposes only booleans.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    agency_id: str | None = None
    pilot_username: str | None = None
    pilot_password_hash: SecretStr | None = None

    database_url: str = (
        "postgresql+psycopg://creatorshield:creatorshield_dev@localhost:5432/creatorshield"
    )
    redis_url: str = "redis://localhost:6379/0"
    # When false, jobs run inline in the API process (used by tests).
    use_job_queue: bool = True
    queue_name: str = "creatorshield"
    job_timeout_seconds: int = 900

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Storage
    storage_backend: Literal["local"] = "local"
    storage_dir: Path = BACKEND_DIR / "var" / "storage"

    # Upload limits
    max_upload_mb: int = 200
    max_duration_seconds: float = 60.0
    # Allow container rounding (e.g. 60.02s) without rejecting a 60s clip.
    duration_tolerance_seconds: float = 0.5

    # Retention
    retention_hours: int = 72
    delete_media_after_analysis: bool = False

    # Speech to text
    stt_provider: Literal["faster_whisper", "openai", "none"] = "faster_whisper"
    whisper_model: str = "small"
    whisper_compute_type: str = "int8"

    # OCR
    ocr_enabled: bool = True
    tesseract_cmd: str = "tesseract"

    # Frame sampling
    max_frames: int = 16
    scene_threshold: float = 0.25
    uniform_frame_interval_seconds: float = 4.0
    frame_width: int = 768

    # AI inference
    ai_provider: Literal["anthropic", "openai", "mock"] = "anthropic"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5"
    ai_max_output_tokens: int = 16000
    ai_timeout_seconds: float = 300.0

    policy_kb_path: Path = Field(
        default=Path(__file__).resolve().parent / "policies" / "data" / "policy_kb.yaml"
    )

    # ---- Connected accounts (official platform APIs only) -------------------
    frontend_url: str = "http://localhost:3000"
    api_public_url: str = "http://localhost:8000"
    # Fernet key used to encrypt OAuth tokens at rest (scripts/dev.sh generates one).
    token_encryption_key: SecretStr | None = None
    oauth_state_ttl_seconds: int = 600

    # Instagram API with Instagram Login (professional accounts)
    instagram_app_id: str | None = None
    instagram_app_secret: SecretStr | None = None
    instagram_redirect_uri: str | None = (
        None  # default: {api_public_url}/api/connections/instagram/callback
    )
    instagram_oauth_url: str = "https://www.instagram.com/oauth/authorize"
    instagram_token_url: str = "https://api.instagram.com/oauth/access_token"  # noqa: S105
    instagram_graph_url: str = "https://graph.instagram.com"
    instagram_api_version: str = "v26.0"
    instagram_media_scan_pages: int = 10  # x25 posts searched when resolving a pasted URL

    # YouTube Data API v3 via Google OAuth
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str | None = (
        None  # default: {api_public_url}/api/connections/youtube/callback
    )
    google_auth_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_token_url: str = "https://oauth2.googleapis.com/token"  # noqa: S105
    google_revoke_url: str = "https://oauth2.googleapis.com/revoke"
    youtube_api_url: str = "https://www.googleapis.com/youtube/v3"
    # Captions need youtube.force-ssl ("manage your YouTube account"); off by default.
    youtube_captions_scope: bool = False
    # YouTube API policy: authorized data must be refreshed or deleted within 30 days.
    youtube_max_retention_hours: int = 720

    # Imported media
    import_max_seconds: float = 60.0  # longer imported videos are trimmed to this
    import_media_hosts: list[str] = ["cdninstagram.com", "fbcdn.net"]

    # ---- Provenance & rights ---------------------------------------------------
    # Catalogue fingerprints (frame hashes + audio fingerprint, no media) are kept
    # after an analysis expires so later videos can be matched against them.
    catalogue_retention_days: int = 365
    catalogue_max_seconds: float = 900.0  # longest file accepted for catalogue indexing
    catalogue_scan_limit: int = 2000  # newest fingerprints compared per video
    fpcalc_cmd: str = "fpcalc"
    rights_proof_max_mb: int = 10

    # YouTube look-alike search (official search.list, 100 quota units per call).
    # Uses YOUTUBE_SEARCH_API_KEY, or a connected channel's token when unset.
    youtube_search_api_key: SecretStr | None = None
    youtube_search_daily_unit_cap: int = 3000
    youtube_thumbnail_hosts: list[str] = ["i.ytimg.com"]

    # Paid lookups: off unless a provider and key are set. All paid calls share
    # one monthly budget; a call that would exceed it is skipped, not made.
    paid_lookups_monthly_budget_usd: float = 5.0
    paid_lookup_cache_days: int = 30
    # none | audd | mock (mock = clearly labelled placeholder, no call)
    music_id_provider: Literal["none", "audd", "mock"] = "none"
    audd_api_token: SecretStr | None = None
    audd_api_url: str = "https://api.audd.io/"
    audd_cost_per_request_usd: float = 0.005
    music_id_clip_seconds: float = 12.0
    music_id_max_clips: int = 2
    music_id_auto: bool = True  # run automatically when music is detected
    # none | google | mock
    web_detection_provider: Literal["none", "google", "mock"] = "none"
    google_vision_api_key: SecretStr | None = None
    google_vision_url: str = "https://vision.googleapis.com/v1/images:annotate"
    web_detection_cost_per_image_usd: float = 0.0035
    web_detection_max_frames: int = 4
    web_detection_auto: bool = True  # run automatically when third-party cues are found

    @property
    def music_id_configured(self) -> bool:
        if self.music_id_provider == "audd":
            return bool(self.audd_api_token and self.audd_api_token.get_secret_value())
        return self.music_id_provider == "mock"

    @property
    def web_detection_configured(self) -> bool:
        if self.web_detection_provider == "google":
            return bool(
                self.google_vision_api_key and self.google_vision_api_key.get_secret_value()
            )
        return self.web_detection_provider == "mock"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def instagram_configured(self) -> bool:
        return bool(self.instagram_app_id and self.instagram_app_secret)

    @property
    def youtube_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def instagram_callback(self) -> str:
        return self.instagram_redirect_uri or (
            f"{self.api_public_url.rstrip('/')}/api/connections/instagram/callback"
        )

    @property
    def youtube_callback(self) -> str:
        return self.google_redirect_uri or (
            f"{self.api_public_url.rstrip('/')}/api/connections/youtube/callback"
        )

    def ai_credentials_present(self) -> bool:
        if self.ai_provider == "anthropic":
            return self.anthropic_api_key is not None and bool(
                self.anthropic_api_key.get_secret_value()
            )
        if self.ai_provider == "openai":
            return self.openai_api_key is not None and bool(self.openai_api_key.get_secret_value())
        return True

    def public_summary(self) -> dict[str, object]:
        """Non-secret configuration safe to expose to the frontend."""
        return {
            "ai_provider": self.ai_provider,
            "ai_model": self.active_model_name(),
            "ai_credentials_present": self.ai_credentials_present(),
            "mock_mode": self.ai_provider == "mock",
            "stt_provider": self.stt_provider,
            "whisper_model": self.whisper_model if self.stt_provider == "faster_whisper" else None,
            "ocr_enabled": self.ocr_enabled,
            "max_upload_mb": self.max_upload_mb,
            "max_duration_seconds": self.max_duration_seconds,
            "retention_hours": self.retention_hours,
            "delete_media_after_analysis": self.delete_media_after_analysis,
            "instagram_configured": self.instagram_configured,
            "youtube_configured": self.youtube_configured,
            "youtube_captions_scope": self.youtube_captions_scope,
            "import_max_seconds": self.import_max_seconds,
            "music_id_provider": self.music_id_provider,
            "music_id_configured": self.music_id_configured,
            "web_detection_provider": self.web_detection_provider,
            "web_detection_configured": self.web_detection_configured,
            "youtube_search_available": bool(
                self.youtube_search_api_key and self.youtube_search_api_key.get_secret_value()
            )
            or self.youtube_configured,
            "paid_lookups_monthly_budget_usd": self.paid_lookups_monthly_budget_usd,
        }

    def active_model_name(self) -> str:
        if self.ai_provider == "anthropic":
            return self.anthropic_model
        if self.ai_provider == "openai":
            return self.openai_model
        return "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
