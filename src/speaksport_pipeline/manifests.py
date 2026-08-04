from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import __version__
from .hashing import sha256_file, stable_hash
from .models import (
    FacilityConfig,
    InputArtifact,
    ModelConfiguration,
    RunManifest,
    ToolContractRegistry,
)


def create_run_manifest(
    root: Path,
    facility: FacilityConfig,
    tool_registry: ToolContractRegistry,
    model_configuration: ModelConfiguration,
    input_paths: list[Path] | None = None,
) -> tuple[Path, RunManifest]:
    input_paths = input_paths or []
    artifacts = [
        InputArtifact(path=str(path.relative_to(root)), sha256=sha256_file(path))
        for path in sorted(input_paths)
    ]
    input_payload = {
        "facility": facility.model_dump(mode="json"),
        "tool_contract_version": tool_registry.version,
        "model_configuration": model_configuration.model_dump(mode="json"),
        "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
    }
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}-{uuid4().hex[:8]}"
    run_directory = root / "runs" / facility.slug / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    for relative in (
        "crawl/raw",
        "crawl/normalized",
        "facts",
        "drafts",
        "validation",
        "output",
    ):
        (run_directory / relative).mkdir(parents=True)
    manifest = RunManifest(
        run_id=run_id,
        facility_slug=facility.slug,
        application_version=__version__,
        input_hash=stable_hash(input_payload),
        inputs=artifacts,
        reference_versions={
            "prompt": facility.references.prompt,
            **(
                {"eligibility": facility.references.eligibility}
                if facility.references.eligibility
                else {}
            ),
        },
        tool_contract_version=tool_registry.version,
        requested_model=model_configuration.model_slug,
        fallback_models=model_configuration.fallback_models,
        max_cost_usd=model_configuration.max_cost_usd,
        timeout_seconds=model_configuration.timeout_seconds,
    )
    save_manifest(run_directory, manifest)
    return run_directory, manifest


def save_manifest(run_directory: Path, manifest: RunManifest) -> None:
    path = run_directory / "manifest.json"
    rendered = json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    path.write_text(rendered, encoding="utf-8")


def load_manifest(run_directory: Path) -> RunManifest:
    path = run_directory / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Run manifest not found: {path}")
    return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))


def latest_run_directory(root: Path, facility_slug: str) -> Path | None:
    facility_runs = root / "runs" / facility_slug
    if not facility_runs.is_dir():
        return None
    runs = sorted(path for path in facility_runs.iterdir() if path.is_dir())
    return runs[-1] if runs else None
