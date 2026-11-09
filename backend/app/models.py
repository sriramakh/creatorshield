"""ORM models.

Personal-data minimisation: we do not store uploader identity, IP addresses or
the original filename (only its extension). Captions/hashtags are stored because
they are analysed; everything is removed by deletion or retention expiry.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(64), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    platform: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8))
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list)

    file_ext: Mapped[str] = mapped_column(String(8))
    content_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Where the content came from. "upload" = user file; otherwise imported from a
    # connected account through the platform's official API.
    source: Mapped[str] = mapped_column(String(16), default="upload", server_default="upload")
    # full_video | caption_thumbnail (IG file withheld) | metadata_only (YouTube)
    # | cross_checked (owner file compared with the published post)
    analysis_mode: Mapped[str] = mapped_column(
        String(24), default="full_video", server_default="full_video"
    )
    # True once the creator attaches their own file to an imported post.
    owner_supplied_media: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("platform_connections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_media_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(300), nullable=True)

    sponsorship: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Optional client / account name (agency use). Groups the catalogue so a match
    # with another client's footage can be told apart from the same client's reposts.
    client_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Provenance facts: third-party cues, catalogue matches, music / web / YouTube
    # lookups and rights-ledger coverage (see app.provenance).
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    media_info: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # transcript segments, frames, OCR, audio analysis
    extraction: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    ai_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mock_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_kb_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Schema-valid AI output before server-side validation/merging (audit trail).
    ai_output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    findings: Mapped[list[Finding]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="Finding.sort_order",
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    source: Mapped[str] = mapped_column(String(16))  # deterministic | ai
    category: Mapped[str] = mapped_column(String(48))
    finding_type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(300))
    explanation: Mapped[str] = mapped_column(Text)
    suggested_action: Mapped[str] = mapped_column(Text)
    start_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    policy_rule_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    context_exception: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    rights_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    rights_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis: Mapped[Analysis] = relationship(back_populates="findings")


class PlatformConnection(Base):
    """An account connected through official OAuth. Tokens are stored encrypted."""

    __tablename__ = "platform_connections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    platform: Mapped[str] = mapped_column(String(16))  # instagram | youtube
    external_id: Mapped[str] = mapped_column(String(64))  # IG user id / YT channel id
    display_name: Mapped[str] = mapped_column(String(200))
    account_meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    access_token_enc: Mapped[str] = mapped_column(Text)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    token_issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RightsRecord(Base):
    """One entry in the rights ledger: something the creator owns, licensed or agreed.

    ``match_terms`` are the handles, names, labels or domains that identify the
    counterparty in content (e.g. "@studio_x", "Epidemic Sound", "Star Sports").
    """

    __tablename__ = "rights_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    # own_channel | creator_permission | music_license | footage_license | brand_agreement
    kind: Mapped[str] = mapped_column(String(32), index=True)
    counterparty: Mapped[str] = mapped_column(String(200))
    match_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    platforms: Mapped[list[str]] = mapped_column(JSON, default=list)  # empty = all
    client_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    reference: Mapped[str] = mapped_column(String(300), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    proof_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proof_content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MediaFingerprint(Base):
    """Compact, non-reversible fingerprint of a video (no frames or audio are kept)."""

    __tablename__ = "media_fingerprints"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # analysis = fingerprint of a reviewed video; catalogue = indexed past post
    source: Mapped[str] = mapped_column(String(16))
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("platform_connections.id", ondelete="CASCADE"), nullable=True
    )
    owner_label: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    frame_step: Mapped[float] = mapped_column(Float)
    # 64-bit difference hashes (None = blank/low-detail frame)
    frame_hashes: Mapped[list[str | None]] = mapped_column(JSON, default=list)
    audio_step: Mapped[float] = mapped_column(Float, default=0.0)
    audio_fp: Mapped[list[int]] = mapped_column(JSON, default=list)  # Chromaprint raw


class PaidLookup(Base):
    """Every paid third-party call (or cache hit) - drives the monthly budget cap."""

    __tablename__ = "paid_lookups"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    service: Mapped[str] = mapped_column(String(32))  # music_id | web_detection
    provider: Mapped[str] = mapped_column(String(32))
    units: Mapped[int] = mapped_column(Integer, default=1)
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
