import json

import httpx
import pytest

from speaksport_pipeline.exceptions import BudgetExceededError, ProviderError
from speaksport_pipeline.models import FactInventory, ModelConfiguration
from speaksport_pipeline.providers.openrouter import (
    OpenRouterClient,
    _provider_safe_strict_schema,
)


def _configuration(max_cost: float = 1.5) -> ModelConfiguration:
    return ModelConfiguration(
        status="owner_confirmed",
        model_slug="openai/gpt-5.6-terra",
        max_cost_usd=max_cost,
        fallback_models=["anthropic/claude-sonnet-5"],
    )


def test_openrouter_uses_strict_schema_and_records_usage() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "gen-1",
                "model": "openai/gpt-5.6-terra",
                "choices": [{"message": {"content": '{"facts":[],"open_questions":[]}'}}],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                    "cost": 0.01,
                },
            },
        )

    client = OpenRouterClient(
        "openrouter-secret",
        _configuration(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    output, result = client.generate_structured(
        messages=[{"role": "user", "content": "Extract."}],
        output_model=FactInventory,
        schema_name="facts",
    )

    assert output.facts == []
    assert result.cost_usd == 0.01
    assert captured["provider"]["require_parameters"] is True
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert captured["models"] == ["anthropic/claude-sonnet-5"]


def test_provider_safe_schema_requires_all_fields_and_removes_numeric_limits() -> None:
    schema = _provider_safe_strict_schema(FactInventory.model_json_schema())
    fact_schema = schema["$defs"]["Fact"]

    assert set(fact_schema["required"]) == set(fact_schema["properties"])
    confidence = fact_schema["properties"]["confidence"]
    assert "minimum" not in confidence
    assert "maximum" not in confidence


def test_openrouter_enforces_run_budget_after_usage_is_returned() -> None:
    response = httpx.Response(
        200,
        json={
            "id": "gen-2",
            "model": "model",
            "choices": [{"message": {"content": '{"facts":[],"open_questions":[]}'}}],
            "usage": {"cost": 0.02},
        },
    )
    client = OpenRouterClient(
        "secret",
        _configuration(max_cost=0.01),
        client=httpx.Client(transport=httpx.MockTransport(lambda _: response)),
    )

    with pytest.raises(BudgetExceededError, match="exceeded"):
        client.generate_structured(
            messages=[{"role": "user", "content": "Extract."}],
            output_model=FactInventory,
            schema_name="facts",
        )


def test_openrouter_error_never_echoes_key() -> None:
    secret = "openrouter-secret-value"
    client = OpenRouterClient(
        secret,
        _configuration(),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(401, json={"error": f"bad key {secret}"})
            )
        ),
    )

    with pytest.raises(ProviderError) as error:
        client.generate_structured(
            messages=[{"role": "user", "content": "Extract."}],
            output_model=FactInventory,
            schema_name="facts",
        )
    assert secret not in str(error.value)
