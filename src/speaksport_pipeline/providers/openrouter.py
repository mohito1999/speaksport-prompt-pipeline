from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ..exceptions import BudgetExceededError, ConfigurationError, ProviderError
from ..models import LLMResult, ModelConfiguration
from ..security import redact_text

OutputT = TypeVar("OutputT", bound=BaseModel)


def _provider_safe_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize Pydantic JSON Schema to the strict subset shared by routed providers."""
    unsupported_constraints = {
        "default",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
    }

    def normalize(value: Any) -> Any:
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if not isinstance(value, dict):
            return value
        normalized = {
            key: normalize(item)
            for key, item in value.items()
            if key not in unsupported_constraints
        }
        properties = normalized.get("properties")
        if isinstance(properties, dict):
            normalized["required"] = list(properties)
            normalized["additionalProperties"] = False
        return normalized

    return normalize(schema)


class OpenRouterClient:
    """Strict structured-output adapter for OpenRouter chat completions."""

    def __init__(
        self,
        api_key: str,
        configuration: ModelConfiguration,
        *,
        client: httpx.Client | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ConfigurationError("OPENROUTER_API_KEY is required for generation")
        if not configuration.model_slug:
            raise ConfigurationError("A pinned OpenRouter model slug is required")
        self.api_key = api_key
        self.configuration = configuration
        self.client = client or httpx.Client(timeout=configuration.timeout_seconds)
        self.base_url = base_url.rstrip("/")
        self.sleeper = sleeper
        self.jitter = jitter
        self.max_retries = max_retries
        self.accumulated_cost_usd = 0.0

    def generate_structured(
        self,
        *,
        messages: list[dict[str, str]],
        output_model: type[OutputT],
        schema_name: str,
        audit_directory: Path | None = None,
    ) -> tuple[OutputT, LLMResult]:
        model_slug = self.configuration.model_slug
        assert model_slug is not None
        payload: dict[str, Any] = {
            "model": model_slug,
            "messages": messages,
            "max_tokens": self.configuration.max_output_tokens,
            "stream": False,
            "provider": {"require_parameters": True},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": _provider_safe_strict_schema(output_model.model_json_schema()),
                },
            },
        }
        if self.configuration.fallback_models:
            payload["models"] = self.configuration.fallback_models
        if audit_directory:
            audit_directory.mkdir(parents=True, exist_ok=True)
            (audit_directory / f"{schema_name}-request.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        response = self._request(payload)
        try:
            choice = response["choices"][0]
            content_value = choice["message"]["content"]
            parsed = json.loads(content_value) if isinstance(content_value, str) else content_value
            output = output_model.model_validate(parsed)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise ProviderError(
                f"OpenRouter returned invalid {schema_name} structured output"
            ) from exc
        usage_raw = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        cost = float(usage_raw.get("cost")) if usage_raw.get("cost") is not None else None
        if cost is not None:
            self.accumulated_cost_usd += cost
        ceiling = self.configuration.max_cost_usd
        if ceiling is not None and self.accumulated_cost_usd > ceiling:
            raise BudgetExceededError(
                f"OpenRouter run cost ${self.accumulated_cost_usd:.4f} "
                f"exceeded ${ceiling:.2f} ceiling"
            )
        usage = {
            key: int(value)
            for key, value in usage_raw.items()
            if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
            and isinstance(value, int)
        }
        result = LLMResult(
            request_id=str(response.get("id") or "unknown"),
            requested_model=model_slug,
            returned_model=str(response.get("model") or model_slug),
            content=output.model_dump(mode="json"),
            usage=usage,
            cost_usd=cost,
        )
        if audit_directory:
            (audit_directory / f"{schema_name}-response.json").write_text(
                json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return output, result

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": "SpeakSport Prompt Pipeline",
        }
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                )
            except httpx.RequestError as exc:
                if attempt == self.max_retries:
                    raise ProviderError(
                        redact_text(f"OpenRouter network error: {exc}", [self.api_key])
                    ) from exc
                self.sleeper(min(2**attempt + self.jitter(), 30))
                continue
            if response.status_code < 400:
                value = response.json()
                if not isinstance(value, dict):
                    raise ProviderError("OpenRouter returned a non-object JSON response")
                return value
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                self.sleeper(min(delay + self.jitter(), 60))
                continue
            try:
                error_value = response.json().get("error")
            except (ValueError, AttributeError):
                error_value = response.text
            raise ProviderError(
                redact_text(
                    f"OpenRouter request failed ({response.status_code}): {error_value}",
                    [self.api_key],
                )
            )
        raise ProviderError("OpenRouter request failed after retries")
