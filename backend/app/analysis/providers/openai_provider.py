"""OpenAI provider (vision + structured outputs).

Implemented against the OpenAI Python SDK's ``chat.completions.parse`` helper.
Not exercised against the live API in this MVP (no key configured) - see
TEST_RESULTS.md.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.analysis.prompt import ImagePart, PromptPayload
from app.analysis.providers.base import MissingCredentialsError, ProviderError, ProviderResult
from app.schemas import AIAnalysisOutput

# Frames are sent at "high" detail so on-screen handles, watermarks and logos
# stay legible ("low" downsamples every image to 512 px). Cost note: frames are
# at most 768 px wide (config.frame_width), i.e. about 6 tiles = ~1.1k input
# tokens per vertical frame; 64 frames (the max) is roughly 70k tokens. Frames
# beyond HIGH_DETAIL_MAX_FRAMES fall back to "low" (85 tokens each).
HIGH_DETAIL_MAX_FRAMES = 64
# Reasoning tokens count toward max_completion_tokens; keep room for the answer.
OUTPUT_TOKEN_FLOOR = 32000
# Non-streaming request: allow long reviews to finish before the client gives up.
MIN_TIMEOUT_SECONDS = 600.0
MAX_RETRIES = 2


class OpenAIProvider:
    name = "openai"

    def __init__(
        self, api_key: str | None, model: str, *, max_tokens: int = 16000, timeout: float = 300.0
    ) -> None:
        if not api_key:
            raise MissingCredentialsError(
                "OPENAI_API_KEY is not configured. Add it to backend/.env and restart."
            )
        import openai

        self._openai = openai
        self.model = model
        self.max_tokens = max(max_tokens, OUTPUT_TOKEN_FLOOR)
        self.client = openai.OpenAI(
            api_key=api_key, timeout=max(timeout, MIN_TIMEOUT_SECONDS), max_retries=MAX_RETRIES
        )

    @staticmethod
    def _content(payload: PromptPayload) -> list[Any]:
        content: list[Any] = []
        images = 0
        for part in payload.parts:
            if isinstance(part, ImagePart):
                images += 1
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{part.media_type};base64,{part.data_b64}",
                            "detail": "high" if images <= HIGH_DETAIL_MAX_FRAMES else "low",
                        },
                    }
                )
            else:
                content.append({"type": "text", "text": part.text})
        return content

    def analyze(self, payload: PromptPayload) -> ProviderResult:
        openai = self._openai
        try:
            completion = self.client.chat.completions.parse(
                model=self.model,
                max_completion_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": payload.system},
                    {"role": "user", "content": self._content(payload)},
                ],
                response_format=AIAnalysisOutput,
            )
        except openai.AuthenticationError as exc:
            raise ProviderError("OpenAI rejected the API key.") from exc
        except openai.NotFoundError as exc:
            raise ProviderError(f"OpenAI model '{self.model}' was not found for this key.") from exc
        except openai.RateLimitError as exc:
            raise ProviderError(
                "OpenAI rate limit or quota reached; check billing/limits.", retryable=True
            ) from exc
        except openai.BadRequestError as exc:
            raise ProviderError(f"OpenAI rejected the request: {exc.message}") from exc
        except openai.APIStatusError as exc:
            raise ProviderError(
                f"OpenAI API error (HTTP {exc.status_code}).", retryable=exc.status_code >= 500
            ) from exc
        except openai.APIConnectionError as exc:
            raise ProviderError("Could not reach the OpenAI API.", retryable=True) from exc
        except openai.LengthFinishReasonError as exc:
            raise ProviderError("The model response was truncated (max tokens).") from exc
        except openai.ContentFilterFinishReasonError as exc:
            raise ProviderError("The model declined to analyse this content.") from exc
        except ValidationError as exc:
            raise ProviderError("The model response did not match the expected schema.") from exc
        except openai.OpenAIError as exc:
            raise ProviderError("The OpenAI API returned an unexpected response.") from exc

        message = completion.choices[0].message
        if getattr(message, "refusal", None):
            raise ProviderError("The model declined to analyse this content.")
        if message.parsed is None:
            raise ProviderError("The model returned no structured output.")
        usage = completion.usage
        return ProviderResult(
            output=message.parsed,
            provider=self.name,
            model=completion.model,
            usage={
                "input_tokens": usage.prompt_tokens if usage else None,
                "output_tokens": usage.completion_tokens if usage else None,
            },
        )
