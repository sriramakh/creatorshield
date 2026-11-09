"""Anthropic Claude provider (vision + structured outputs)."""

from __future__ import annotations

import logging
from typing import Any, Literal

import anthropic
from pydantic import ValidationError

from app.analysis.prompt import ImagePart, PromptPayload
from app.analysis.providers.base import MissingCredentialsError, ProviderError, ProviderResult
from app.schemas import AIAnalysisOutput

log = logging.getLogger(__name__)

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        api_key: str | None,
        model: str,
        *,
        effort: Effort = "medium",
        max_tokens: int = 16000,
        timeout: float = 300.0,
    ) -> None:
        if not api_key:
            raise MissingCredentialsError(
                "ANTHROPIC_API_KEY is not configured. Add it to backend/.env and restart."
            )
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)

    @staticmethod
    def _content(payload: PromptPayload) -> list[Any]:
        blocks: list[Any] = []
        for part in payload.parts:
            if isinstance(part, ImagePart):
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": part.media_type,
                            "data": part.data_b64,
                        },
                    }
                )
            else:
                blocks.append({"type": "text", "text": part.text})
        return blocks

    def analyze(self, payload: PromptPayload) -> ProviderResult:
        try:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                system=payload.system,
                messages=[{"role": "user", "content": self._content(payload)}],
                output_format=AIAnalysisOutput,
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
                # Server-side fallback if a safety classifier declines (e.g. a
                # video legitimately discussing a sensitive topic).
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as exc:
            raise ProviderError("Anthropic rejected the API key (authentication failed).") from exc
        except anthropic.PermissionDeniedError as exc:
            raise ProviderError("The Anthropic API key lacks permission for this model.") from exc
        except anthropic.NotFoundError as exc:
            raise ProviderError(f"Model '{self.model}' was not found.") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError(
                "Anthropic rate limit reached; retry shortly.", retryable=True
            ) from exc
        except anthropic.BadRequestError as exc:
            log.warning("anthropic bad request: %s", exc.message)
            raise ProviderError(f"Anthropic rejected the request: {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(
                f"Anthropic API error (HTTP {exc.status_code}).", retryable=exc.status_code >= 500
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("Could not reach the Anthropic API.", retryable=True) from exc
        except ValidationError as exc:
            raise ProviderError("The model response did not match the expected schema.") from exc

        log.info(
            "anthropic request_id=%s stop_reason=%s", response._request_id, response.stop_reason
        )
        if response.stop_reason == "refusal":
            raise ProviderError("The model declined to analyse this content.")
        if response.stop_reason == "max_tokens":
            raise ProviderError("The model response was truncated (max_tokens).", retryable=True)
        parsed = response.parsed_output
        if parsed is None:
            raise ProviderError("The model returned no structured output.")
        usage = response.usage
        return ProviderResult(
            output=parsed,
            provider=self.name,
            model=response.model,
            usage={
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "request_id": response._request_id,
            },
        )
