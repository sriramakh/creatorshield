"""Pydantic schemas: the AI structured-output contract and API responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Platform = Literal["youtube_shorts", "youtube_video", "instagram_reels", "tiktok"]
Market = Literal["IN", "US", "UK"]
Language = Literal["en", "hi"]

# Categories the AI review may use.
AICategory = Literal[
    "community_guidelines",
    "harmful_content",  # hate, harassment, violence, sexual, dangerous
    "spam_deception",
    "monetization",
    "disclosure",
    "originality",
    "licensing",
    "context_exception",
]
# brand_brief: the content against a sponsor's brief (app.analysis.brief). A
# contract check, not a policy check, so the AI contract does not offer it.
Category = Literal[
    "community_guidelines",
    "harmful_content",
    "spam_deception",
    "monetization",
    "disclosure",
    "originality",
    "licensing",
    "context_exception",
    "brand_brief",
]

CATEGORY_LABELS: dict[str, str] = {
    "community_guidelines": "Community guidelines",
    "harmful_content": "Hate, harassment, violence, sexual or dangerous content",
    "spam_deception": "Spam, deceptive claims & misleading promotion",
    "monetization": "Monetization & advertiser suitability",
    "disclosure": "Sponsored-content disclosure",
    "originality": "Reused / non-original content",
    "licensing": "Music & third-party licensing",
    "context_exception": "Context (news, education, satire, commentary)",
    "brand_brief": "Brand brief",
}

# observed_evidence: the content itself shows the issue (quote/frame).
# suspected_violation: a judgement that something may breach a rule.
# licensing_uncertainty: rights status cannot be determined from the content.
# cannot_check: a check this system is not able to perform.
FindingType = Literal[
    "observed_evidence", "suspected_violation", "licensing_uncertainty", "cannot_check"
]
AIFindingType = Literal["observed_evidence", "suspected_violation", "licensing_uncertainty"]
Severity = Literal["info", "low", "medium", "high", "critical"]
Confidence = Literal["low", "medium", "high"]
EvidenceSource = Literal["transcript", "frame", "ocr", "caption", "hashtags", "metadata", "audio"]

SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


# ---------------------------------------------------------------------------
# AI structured output contract. Kept free of numeric/length constraints so it
# maps cleanly to provider JSON-schema modes; semantic checks happen afterwards
# in app.analysis.validation.
# ---------------------------------------------------------------------------


class AIEvidence(BaseModel):
    source: EvidenceSource
    ref_id: str = Field(description="ID of the referenced item, e.g. T3, F5, O2, CAPTION, HASHTAGS")
    detail: str = Field(description="Short quote or description of what is observed")


class AIFinding(BaseModel):
    category: AICategory
    finding_type: AIFindingType
    severity: Severity
    confidence: Confidence
    title: str
    explanation: str
    evidence: list[AIEvidence]
    start_seconds: float | None
    end_seconds: float | None
    policy_rule_ids: list[str] = Field(
        description="Rule IDs copied exactly from the provided policy knowledge base"
    )
    suggested_action: str
    context_exception: str | None = Field(
        description="If news/education/documentary/satire/commentary context may apply, explain"
    )
    requires_human_review: bool


class AIAnalysisOutput(BaseModel):
    summary: str
    context_assessment: str
    findings: list[AIFinding]
    unassessable: list[str] = Field(
        description="Aspects that could not be assessed from the provided material"
    )
    embedded_instructions_detected: bool = Field(
        description="True if the untrusted content contained text addressed to an AI reviewer"
    )


# ---------------------------------------------------------------------------
# Internal finding representation (deterministic + validated AI findings)
# ---------------------------------------------------------------------------


class FindingDraft(BaseModel):
    # provenance = catalogue / rights-ledger / music / web lookups (app.provenance)
    source: Literal["deterministic", "ai", "combined", "provenance"]
    category: Category
    finding_type: FindingType
    severity: Severity
    confidence: Confidence
    title: str
    explanation: str
    suggested_action: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    policy_rule_ids: list[str] = Field(default_factory=list)
    context_exception: str | None = None
    requires_human_review: bool = True
    validation_notes: list[str] = Field(default_factory=list)
    # covered = the rights ledger covers it; duplicate = a provenance finding reports
    # the same gap. Either way it stays visible but is not counted in the risk score.
    rights_status: Literal["covered", "duplicate"] | None = None
    rights_note: str | None = None


# ---------------------------------------------------------------------------
# API responses
# ---------------------------------------------------------------------------


class PolicyRef(BaseModel):
    id: str
    platform: str
    title: str
    official_title: str
    official_url: str
    verified_on: str


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    category: str
    category_label: str = ""
    finding_type: str
    severity: str
    confidence: str
    title: str
    explanation: str
    suggested_action: str
    start_seconds: float | None
    end_seconds: float | None
    evidence: list[dict[str, Any]]
    policy_rule_ids: list[str]
    policies: list[PolicyRef] = Field(default_factory=list)
    context_exception: str | None
    requires_human_review: bool
    validation_notes: list[str]
    rights_status: str | None = None
    rights_note: str | None = None
    # Derived at serialisation. Not stored. disclosure stays separate from community flags.
    report_section: Literal["community", "disclosure", "brief", "other"] = "other"


class AnalysisSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    status: str
    stage: str
    progress: int
    platform: str
    language: str
    caption: str
    duration_seconds: float | None
    risk_level: str | None
    risk_score: int | None
    mock_mode: bool
    finding_count: int = 0
    source: str = "upload"
    analysis_mode: str = "full_video"
    source_title: str | None = None
    client_label: str | None = None
    # Audience markets whose advertising guidance was applied.
    markets: list[str] = Field(default_factory=list)
    # ready | review | fix_first, once the review has completed.
    readiness_verdict: str | None = None

    @field_validator("markets", mode="before")
    @classmethod
    def _markets(cls, value: Any) -> Any:
        return value or []


class AnalysisOut(AnalysisSummaryOut):
    sponsorship: dict[str, Any] | None = None
    # The sponsor's brief this review was checked against, and the result.
    brief: dict[str, Any] | None = None
    brief_check: dict[str, Any] | None = None
    # Derived when the review is read (app.analysis.readiness / caption_fix /
    # market_disclosure); never stored.
    readiness: dict[str, Any] | None = None
    caption_fix: dict[str, Any] | None = None
    market_disclosure: dict[str, Any] | None = None
    updated_at: datetime
    source_url: str | None = None
    source_media_id: str | None = None
    connection_id: uuid.UUID | None = None
    owner_supplied_media: bool = False
    error_message: str | None
    hashtags: list[str]
    file_ext: str
    content_type: str
    size_bytes: int
    media_deleted: bool
    media_info: dict[str, Any] | None
    extraction: dict[str, Any] | None
    provenance: dict[str, Any] | None = None
    ai_provider: str | None
    ai_model: str | None
    ai_status: str | None
    ai_status_detail: str | None
    policy_kb_version: str | None
    summary: str | None
    context_assessment: str | None
    limitations: list[str]
    findings: list[FindingOut] = Field(default_factory=list)


class CreateAnalysisOut(BaseModel):
    id: uuid.UUID
    status: str


class ConnectionOut(BaseModel):
    """A connected account. Never includes tokens."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: str
    display_name: str
    external_id: str
    account_meta: dict[str, Any]
    scopes: list[str]
    token_expires_at: datetime | None
    created_at: datetime
    captions_enabled: bool = False


class SponsorshipInput(BaseModel):
    relationship: Literal[
        "unknown", "none", "paid", "gifted", "affiliate", "employment", "other"
    ] = "unknown"
    sponsors: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("sponsors")
    @classmethod
    def clean_sponsors(cls, values: list[str]) -> list[str]:
        if any(not v.strip() or len(v) > 100 for v in values):
            raise ValueError("Sponsor names must contain 1–100 characters")
        return list(dict.fromkeys(v.strip() for v in values))


class ImportRequest(BaseModel):
    sponsorship: SponsorshipInput = Field(default_factory=SponsorshipInput)
    # Audience markets (IN, US, UK). Omitted = the workspace default.
    markets: list[str] | None = Field(default=None, max_length=3)
    # A brief to check against: inline (BriefSpec fields) or a saved one by ID.
    brief: dict[str, Any] | None = None
    brief_id: uuid.UUID | None = None
    connection_id: uuid.UUID
    url: str | None = Field(default=None, max_length=500)
    media_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    language: Language = "en"
    client_label: str | None = Field(default=None, max_length=100)
    # Create the analysis and wait for the creator's own video file before fetching.
    attach_owner_file: bool = False


# ---------------------------------------------------------------------------
# Creator tools: caption check, briefs, workspace settings
# ---------------------------------------------------------------------------


class QuickCheckRequest(BaseModel):
    """A caption to check before there is a video. Nothing is stored."""

    platform: Platform
    markets: list[str] | None = Field(default=None, max_length=3)
    caption: str = Field(default="", max_length=5000)
    hashtags: list[str] = Field(default_factory=list, max_length=100)
    sponsorship: SponsorshipInput = Field(default_factory=SponsorshipInput)
    brief: dict[str, Any] | None = None
    brief_id: uuid.UUID | None = None

    @field_validator("hashtags")
    @classmethod
    def clean_hashtags(cls, values: list[str]) -> list[str]:
        tags = [v.strip().lstrip("#").strip()[:100] for v in values]
        return list(dict.fromkeys(t for t in tags if t))


class BriefOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    name: str
    brand: str
    must_say: list[str]
    must_not_say: list[str]
    required_hashtags: list[str]
    required_mentions: list[str]
    competitors: list[str]
    required_disclosure: str | None
    notes: str


class WorkspaceSettingsIn(BaseModel):
    mode: Literal["creator", "agency"] | None = None
    display_name: str | None = Field(default=None, max_length=120)
    default_platform: Platform | None = None
    default_markets: list[str] | None = Field(default=None, min_length=1, max_length=3)
    default_language: Language | None = None
    onboarded: bool | None = None


class WorkspaceSettingsOut(BaseModel):
    mode: Literal["creator", "agency"]
    display_name: str
    default_platform: str
    default_markets: list[str]
    default_language: str
    onboarded: bool
