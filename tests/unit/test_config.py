from pathlib import Path

import pytest

from speaksport_pipeline.config import (
    ReferenceRegistry,
    load_effective_model_configuration,
    load_model_configuration,
    load_runtime_registry,
    load_tool_registry,
    load_yaml,
)
from speaksport_pipeline.exceptions import ConfigurationError
from speaksport_pipeline.models import ReferenceMode

ROOT = Path(__file__).resolve().parents[2]


def test_reference_registry_verifies_all_reference_hashes() -> None:
    records = ReferenceRegistry(ROOT).all()

    assert {(record.mode, record.metadata.version) for record in records} == {
        (ReferenceMode.INTEGRATED, "2026-07-10"),
        (ReferenceMode.NON_INTEGRATED, "2026-07-10"),
        (ReferenceMode.ELIGIBILITY, "2026-07-10"),
    }


def test_runtime_and_tool_registries_are_typed() -> None:
    runtime = load_runtime_registry(ROOT)
    tools = load_tool_registry(ROOT)
    model = load_model_configuration(ROOT)

    assert "phone_recognized" in {variable.name for variable in runtime.variables}
    capabilities = {tool.capability for tool in tools.tools}
    assert {"eligibility", "booking_lookup", "cancellation_eligibility", "cancellation"} <= (
        capabilities
    )
    assert tools.version == "2026-07-31"
    assert tools.status == "owner_confirmed_with_rich_availability_results"
    assert model.model_slug == "openai/gpt-5.6-terra"
    assert model.max_cost_usd == 1.5
    assert model.reproducibility_requires_pinned_model


def test_environment_overrides_model_configuration() -> None:
    model = load_effective_model_configuration(
        ROOT,
        {
            "OPENROUTER_MODEL": "model/primary",
            "OPENROUTER_FALLBACK_MODELS": "model/backup-one,model/backup-two",
            "OPENROUTER_MAX_COST_USD": "1.25",
            "OPENROUTER_TIMEOUT_SECONDS": "300",
        },
    )

    assert model.model_slug == "model/primary"
    assert model.fallback_models == ["model/backup-one", "model/backup-two"]
    assert model.max_cost_usd == 1.25
    assert model.timeout_seconds == 300


def test_yaml_loader_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text("value: one\nvalue: two\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="duplicate key"):
        load_yaml(path)
