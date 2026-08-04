from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .models import LLMResult


class StageCache:
    def __init__(self, root: Path):
        self.root = root

    def load(
        self, namespace: str, key: str, output_model: type[BaseModel]
    ) -> tuple[BaseModel, LLMResult] | None:
        path = self.root / namespace / f"{key}.json"
        if not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return output_model.model_validate(value["output"]), LLMResult.model_validate(
            value["result"]
        )

    def save(self, namespace: str, key: str, output: BaseModel, result: LLMResult) -> Path:
        path = self.root / namespace / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        value = {
            "output": output.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
        return path
