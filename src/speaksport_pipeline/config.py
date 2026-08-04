from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError
from yaml.constructor import ConstructorError

from .exceptions import ConfigurationError, ReferenceError
from .hashing import sha256_file
from .models import (
    FacilityConfig,
    ModelConfiguration,
    PromptModificationConfig,
    ReferenceMetadata,
    ReferenceMode,
    ReferenceRecord,
    RuntimeVariableRegistry,
    ToolContractRegistry,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

REFERENCE_DIRECTORIES = {
    ReferenceMode.INTEGRATED: "integrated",
    ReferenceMode.NON_INTEGRATED: "non-integrated",
    ReferenceMode.ELIGIBILITY: "eligibility",
}
REFERENCE_CONTENT_FILES = {
    ReferenceMode.INTEGRATED: "reference-prompt.md",
    ReferenceMode.NON_INTEGRATED: "reference-prompt.md",
    ReferenceMode.ELIGIBILITY: "reference-policy.md",
}


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False):
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "config").is_dir():
            return candidate
    raise ConfigurationError("Could not find project root containing pyproject.toml and config/")


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigurationError(f"Required configuration file does not exist: {path}")
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"Expected a YAML mapping in {path}")
    return data


def dump_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(value, sort_keys=False, allow_unicode=True)
    path.write_text(rendered, encoding="utf-8")


def load_model(path: Path, model_type: type[ModelT]) -> ModelT:
    try:
        return model_type.model_validate(load_yaml(path))
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid configuration in {path}:\n{exc}") from exc


def load_facility(root: Path, slug: str) -> FacilityConfig:
    return load_model(root / "facilities" / slug / "facility.yaml", FacilityConfig)


def load_modification(root: Path, slug: str) -> PromptModificationConfig:
    return load_model(root / "modifications" / slug / "modification.yaml", PromptModificationConfig)


def load_modification_facility(root: Path, slug: str) -> FacilityConfig:
    return load_model(root / "modifications" / slug / "facility.yaml", FacilityConfig)


def load_runtime_registry(root: Path) -> RuntimeVariableRegistry:
    return load_model(root / "config" / "runtime-variables.yaml", RuntimeVariableRegistry)


def load_tool_registry(root: Path) -> ToolContractRegistry:
    return load_model(root / "config" / "tool-contracts" / "current.yaml", ToolContractRegistry)


def load_model_configuration(root: Path) -> ModelConfiguration:
    return load_model(root / "config" / "model.yaml", ModelConfiguration)


def load_effective_model_configuration(
    root: Path, environment: Mapping[str, str] | None = None
) -> ModelConfiguration:
    source = environment or os.environ
    values = load_model_configuration(root).model_dump(mode="json")
    if model := source.get("OPENROUTER_MODEL"):
        values["model_slug"] = model.strip()
    if fallbacks := source.get("OPENROUTER_FALLBACK_MODELS"):
        values["fallback_models"] = [
            value.strip() for value in fallbacks.split(",") if value.strip()
        ]
    try:
        if max_cost := source.get("OPENROUTER_MAX_COST_USD"):
            values["max_cost_usd"] = float(max_cost)
        if timeout := source.get("OPENROUTER_TIMEOUT_SECONDS"):
            values["timeout_seconds"] = int(timeout)
    except ValueError as exc:
        raise ConfigurationError("Invalid numeric OpenRouter environment configuration") from exc
    return ModelConfiguration.model_validate(values)


class ReferenceRegistry:
    def __init__(self, root: Path):
        self.root = root

    def _mode_root(self, mode: ReferenceMode) -> Path:
        return self.root / "references" / REFERENCE_DIRECTORIES[mode]

    def versions(self, mode: ReferenceMode) -> list[str]:
        mode_root = self._mode_root(mode)
        if not mode_root.is_dir():
            return []
        return sorted(
            path.name
            for path in mode_root.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        )

    def get(self, mode: ReferenceMode, version: str, verify_hash: bool = True) -> ReferenceRecord:
        directory = self._mode_root(mode) / version
        content_path = directory / REFERENCE_CONTENT_FILES[mode]
        metadata_path = directory / "metadata.yaml"
        if not directory.is_dir() or not content_path.is_file() or not metadata_path.is_file():
            raise ReferenceError(f"Reference {mode.value}/{version} is incomplete or missing")
        try:
            metadata = ReferenceMetadata.model_validate(load_yaml(metadata_path))
        except (ValidationError, ConfigurationError) as exc:
            raise ReferenceError(f"Invalid metadata for {mode.value}/{version}: {exc}") from exc
        if metadata.version != version:
            raise ReferenceError(
                f"Reference directory version {version} does not match metadata {metadata.version}"
            )
        actual_hash = sha256_file(content_path)
        if verify_hash and actual_hash != metadata.content_hash:
            raise ReferenceError(
                f"Reference hash mismatch for {content_path}; create a new version instead of "
                "editing an active reference in place"
            )
        instructions = directory / "generation-instructions.md"
        return ReferenceRecord(
            mode=mode,
            directory=str(directory.relative_to(self.root)),
            content_file=str(content_path.relative_to(self.root)),
            metadata=metadata,
            generation_instructions_file=(
                str(instructions.relative_to(self.root)) if instructions.is_file() else None
            ),
        )

    def all(self) -> list[ReferenceRecord]:
        records: list[ReferenceRecord] = []
        for mode in ReferenceMode:
            records.extend(self.get(mode, version) for version in self.versions(mode))
        return records

    def active_versions(self) -> dict[str, str]:
        data = load_yaml(self.root / "config" / "active-references.yaml")
        return {
            key: str(value)
            for key, value in data.items()
            if key in {mode.value for mode in ReferenceMode}
        }

    def activate(self, mode: ReferenceMode, version: str) -> None:
        self.get(mode, version)
        path = self.root / "config" / "active-references.yaml"
        data = load_yaml(path)
        data[mode.value] = version
        dump_yaml(path, data)
