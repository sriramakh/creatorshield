"""Provider-agnostic AI inference interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.analysis.prompt import PromptPayload
from app.schemas import AIAnalysisOutput


class ProviderError(Exception):
    """Inference failed. ``user_message`` is safe to show; never contains secrets."""

    def __init__(self, user_message: str, *, retryable: bool = False) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.retryable = retryable


class MissingCredentialsError(ProviderError):
    pass


@dataclass
class ProviderResult:
    output: AIAnalysisOutput
    provider: str
    model: str
    is_mock: bool = False
    usage: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class AnalysisProvider(Protocol):
    name: str
    model: str

    def analyze(self, payload: PromptPayload) -> ProviderResult: ...
