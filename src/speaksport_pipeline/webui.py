from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from pydantic import ValidationError

from .config import (
    ReferenceRegistry,
    dump_yaml,
    load_facility,
    load_modification,
    load_modification_facility,
    load_tool_registry,
)
from .exceptions import SpeakSportError
from .models import (
    FacilityConfig,
    IntegrationType,
    PromptModificationConfig,
)

STATIC_ROOT = Path(__file__).with_name("ui_static")
MAX_BODY_BYTES = 10 * 1024 * 1024
SAFE_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
VIEWABLE_ROOTS = {"facilities", "modifications", "runs", "modification-runs"}
VIEWABLE_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".txt", ".diff", ".html"}
NOTE_FILES = {
    "client_notes": "client-notes.md",
    "booking_policies": "booking-policies.md",
    "transfer_notes": "transfer-notes.md",
    "known_exclusions": "known-exclusions.md",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _notes(directory: Path) -> dict[str, str]:
    return {key: _read_text(directory / filename) for key, filename in NOTE_FILES.items()}


def _validate_slug(slug: str) -> str:
    value = slug.strip()
    if not SAFE_SLUG.fullmatch(value):
        raise SpeakSportError("Use a lowercase slug containing only letters, numbers, and hyphens")
    return value


def _facility_payload(root: Path, slug: str) -> dict[str, Any]:
    facility = load_facility(root, slug)
    directory = root / "facilities" / slug
    return {
        "config": facility.model_dump(mode="json"),
        "notes": _notes(directory),
    }


def _modification_payload(root: Path, slug: str) -> dict[str, Any]:
    modification = load_modification(root, slug)
    facility = load_modification_facility(root, slug)
    directory = root / "modifications" / slug
    return {
        "config": modification.model_dump(mode="json"),
        "facility": facility.model_dump(mode="json"),
        "original_prompt": _read_text(directory / modification.original_prompt_file),
        "update_notes": _read_text(directory / modification.update_notes_file),
    }


def _write_facility(root: Path, payload: dict[str, Any], *, replace: bool = False) -> str:
    raw_config = payload.get("config")
    if not isinstance(raw_config, dict):
        raise SpeakSportError("Facility configuration is required")
    slug = _validate_slug(str(raw_config.get("slug", "")))
    directory = root / "facilities" / slug
    if directory.exists() and not replace:
        raise SpeakSportError(f"Facility already exists: {slug}")
    if replace and not directory.is_dir():
        raise SpeakSportError(f"Facility does not exist: {slug}")
    facility = FacilityConfig.model_validate(raw_config)
    notes = payload.get("notes") or {}
    if not isinstance(notes, dict):
        raise SpeakSportError("Facility notes must be text fields")
    directory.mkdir(parents=True, exist_ok=True)
    dump_yaml(directory / "facility.yaml", facility.model_dump(mode="json"))
    headings = {
        "client_notes": "# Client notes\n\n",
        "booking_policies": "# Booking policies\n\n",
        "transfer_notes": "# Transfer notes\n\n",
        "known_exclusions": "# Known exclusions\n\n",
    }
    for key, filename in NOTE_FILES.items():
        value = str(notes.get(key, "")).strip()
        if value and not value.lstrip().startswith("#"):
            rendered = headings[key] + value + "\n"
        else:
            rendered = value + "\n" if value else headings[key]
        (directory / filename).write_text(rendered, encoding="utf-8")
    return slug


def _write_modification(root: Path, payload: dict[str, Any], *, replace: bool = False) -> str:
    raw_modification = payload.get("config")
    raw_facility = payload.get("facility")
    if not isinstance(raw_modification, dict) or not isinstance(raw_facility, dict):
        raise SpeakSportError("Modification and facility configuration are required")
    slug = _validate_slug(str(raw_modification.get("slug", "")))
    if str(raw_facility.get("slug", "")) != slug:
        raise SpeakSportError("Modification and facility slugs must match")
    directory = root / "modifications" / slug
    if directory.exists() and not replace:
        raise SpeakSportError(f"Prompt modification already exists: {slug}")
    if replace and not directory.is_dir():
        raise SpeakSportError(f"Prompt modification does not exist: {slug}")
    modification = PromptModificationConfig.model_validate(raw_modification)
    facility = FacilityConfig.model_validate(raw_facility)
    if facility.integration_type != IntegrationType.INTEGRATED:
        raise SpeakSportError("Prompt modifications currently use the integrated runtime")
    original = str(payload.get("original_prompt", ""))
    if "<knowledge-base>" not in original or "</knowledge-base>" not in original:
        raise SpeakSportError("The original prompt must contain a <knowledge-base> block")
    update_notes = str(payload.get("update_notes", "")).strip()
    if not update_notes:
        raise SpeakSportError("Describe the requested prompt changes")
    directory.mkdir(parents=True, exist_ok=True)
    dump_yaml(directory / "modification.yaml", modification.model_dump(mode="json"))
    dump_yaml(directory / "facility.yaml", facility.model_dump(mode="json"))
    (directory / modification.original_prompt_file).write_text(
        original.strip() + "\n", encoding="utf-8"
    )
    (directory / modification.update_notes_file).write_text(update_notes + "\n", encoding="utf-8")
    return slug


def _manifest_summary(path: Path, *, kind: str) -> dict[str, Any]:
    data = _read_json(path)
    run_directory = path.parent
    output = run_directory / "output"
    qa_path = output / "qa-report.md"
    qa = _read_text(qa_path)
    qa_outcome = None
    if match := re.search(r"(?im)^Outcome:\s*(.+)$", qa):
        qa_outcome = match.group(1).strip()
    artifacts: list[dict[str, str]] = []
    preferred = [
        "unified-vapi-prompt.md",
        "eligibility-backoffice-policy.md",
        "cancellation-eligibility-backoffice-policy.md",
        "qa-report.md",
        "open-questions.md",
        "prompt-diff.md",
    ]
    for name in preferred:
        candidate = output / name
        if candidate.is_file():
            artifacts.append({"name": name, "path": str(candidate.relative_to(path.parents[3]))})
    return {
        "kind": kind,
        "run_id": data.get("run_id", run_directory.name),
        "slug": (
            data.get("facility_slug")
            or data.get("modification_slug")
            or run_directory.parent.name
        ),
        "status": data.get("status", "UNKNOWN"),
        "created_at": data.get("created_at"),
        "cost_usd": data.get("cost_usd"),
        "validation_outcome": data.get("validation_outcome") or qa_outcome,
        "returned_model": data.get("returned_model"),
        "artifacts": artifacts,
    }


def _scan_runs(root: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for directory_name, kind in (("runs", "facility"), ("modification-runs", "modification")):
        base = root / directory_name
        if not base.is_dir():
            continue
        for manifest in base.glob("*/*/manifest.json"):
            values.append(_manifest_summary(manifest, kind=kind))
    return sorted(values, key=lambda item: str(item.get("created_at") or ""), reverse=True)


def _scan_configs(root: Path, directory_name: str, loader: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    base = root / directory_name
    if not base.is_dir():
        return values
    for directory in sorted(base.iterdir()):
        if not directory.is_dir():
            continue
        try:
            config = loader(root, directory.name)
        except Exception:
            continue
        values.append(
            {
                "slug": config.slug,
                "display_name": config.display_name,
                "tee_sheet": getattr(config, "tee_sheet", None),
                "integration_type": getattr(config, "integration_type", None),
            }
        )
    return values


class JobManager:
    def __init__(self, root: Path):
        self.root = root
        self.directory = root / ".ui" / "jobs"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.jobs: dict[str, dict[str, Any]] = {}

    def start(self, kind: str, slug: str) -> dict[str, Any]:
        if kind not in {"facility", "modification"}:
            raise SpeakSportError("Unknown run type")
        command = [sys.executable, "-m", "speaksport_pipeline"]
        command.extend(["run", slug] if kind == "facility" else ["modify", "run", slug])
        job_id = uuid.uuid4().hex[:12]
        log_path = self.directory / f"{job_id}.log"
        environment = os.environ.copy()
        environment["PYTHONUNBUFFERED"] = "1"
        process = subprocess.Popen(
            command,
            cwd=self.root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        job = {
            "id": job_id,
            "kind": kind,
            "slug": slug,
            "status": "running",
            "started_at": _now(),
            "finished_at": None,
            "exit_code": None,
            "log_path": str(log_path),
            "pid": process.pid,
        }
        with self.lock:
            self.jobs[job_id] = job

        def consume() -> None:
            with log_path.open("w", encoding="utf-8") as log:
                assert process.stdout is not None
                for line in process.stdout:
                    log.write(line)
                    log.flush()
            exit_code = process.wait()
            with self.lock:
                job["exit_code"] = exit_code
                job["status"] = "completed" if exit_code == 0 else "failed"
                job["finished_at"] = _now()

        threading.Thread(target=consume, daemon=True).start()
        return self.public(job)

    def public(self, job: dict[str, Any]) -> dict[str, Any]:
        value = {key: item for key, item in job.items() if key != "log_path"}
        value["log"] = _read_text(Path(job["log_path"]))[-50000:]
        return value

    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            return [self.public(job) for job in reversed(list(self.jobs.values()))]

    def get(self, job_id: str) -> dict[str, Any]:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                raise SpeakSportError("Run job not found")
            return self.public(job)


class UIService:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.jobs = JobManager(self.root)

    def bootstrap(self) -> dict[str, Any]:
        registry = load_tool_registry(self.root)
        references = ReferenceRegistry(self.root).active_versions()
        return {
            "facilities": _scan_configs(self.root, "facilities", load_facility),
            "modifications": _scan_configs(self.root, "modifications", load_modification),
            "runs": _scan_runs(self.root),
            "jobs": self.jobs.list(),
            "tools": [tool.model_dump(mode="json") for tool in registry.tools],
            "tool_contract_version": registry.version,
            "references": references,
        }

    def safe_file(self, relative: str) -> Path:
        candidate = (self.root / unquote(relative)).resolve()
        try:
            relative_path = candidate.relative_to(self.root)
        except ValueError as exc:
            raise SpeakSportError("File is outside the project") from exc
        if not relative_path.parts or relative_path.parts[0] not in VIEWABLE_ROOTS:
            raise SpeakSportError("That file is not available in the control panel")
        if candidate.suffix.lower() not in VIEWABLE_SUFFIXES or not candidate.is_file():
            raise SpeakSportError("That file cannot be displayed")
        return candidate


class UIRequestHandler(BaseHTTPRequestHandler):
    server_version = "SpeakSportUI/1"

    @property
    def service(self) -> UIService:
        return self.server.service  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, value: Any, status: int = 200) -> None:
        payload = json.dumps(value, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_error(self, exc: Exception, status: int = 400) -> None:
        message = str(exc)
        if isinstance(exc, ValidationError):
            message = "\n".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
        self._send_json({"error": message}, status)

    def _body(self) -> dict[str, Any]:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise SpeakSportError("Invalid request size") from exc
        if size <= 0 or size > MAX_BODY_BYTES:
            raise SpeakSportError("Request body is empty or too large")
        try:
            value = json.loads(self.rfile.read(size))
        except json.JSONDecodeError as exc:
            raise SpeakSportError("Request body must be valid JSON") from exc
        if not isinstance(value, dict):
            raise SpeakSportError("Request body must be an object")
        return value

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/health":
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/bootstrap":
                self._send_json(self.service.bootstrap())
                return
            if parsed.path.startswith("/api/facilities/"):
                slug = _validate_slug(parsed.path.rsplit("/", 1)[-1])
                self._send_json(_facility_payload(self.service.root, slug))
                return
            if parsed.path.startswith("/api/modifications/"):
                slug = _validate_slug(parsed.path.rsplit("/", 1)[-1])
                self._send_json(_modification_payload(self.service.root, slug))
                return
            if parsed.path == "/api/jobs":
                self._send_json(self.service.jobs.list())
                return
            if parsed.path.startswith("/api/jobs/"):
                self._send_json(self.service.jobs.get(parsed.path.rsplit("/", 1)[-1]))
                return
            if parsed.path == "/api/file":
                relative = parse_qs(parsed.query).get("path", [""])[0]
                file_path = self.service.safe_file(relative)
                payload = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            self._serve_static(parsed.path)
        except (SpeakSportError, ValidationError, OSError) as exc:
            self._send_error(exc, 404 if isinstance(exc, FileNotFoundError) else 400)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._body()
            if parsed.path == "/api/facilities":
                slug = _write_facility(self.service.root, payload)
                self._send_json({"ok": True, "slug": slug}, HTTPStatus.CREATED)
                return
            if parsed.path == "/api/modifications":
                slug = _write_modification(self.service.root, payload)
                self._send_json({"ok": True, "slug": slug}, HTTPStatus.CREATED)
                return
            match = re.fullmatch(r"/api/(facilities|modifications)/([^/]+)/run", parsed.path)
            if match:
                if payload.get("approved_external_processing") is not True:
                    raise SpeakSportError(
                        "Confirm approval to send the selected materials to Firecrawl/OpenRouter"
                    )
                kind = "facility" if match.group(1) == "facilities" else "modification"
                slug = _validate_slug(match.group(2))
                if kind == "facility":
                    load_facility(self.service.root, slug)
                else:
                    load_modification(self.service.root, slug)
                self._send_json(self.service.jobs.start(kind, slug), HTTPStatus.ACCEPTED)
                return
            self._send_json({"error": "Not found"}, 404)
        except (SpeakSportError, ValidationError, OSError) as exc:
            self._send_error(exc)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._body()
            if match := re.fullmatch(r"/api/facilities/([^/]+)", parsed.path):
                slug = _validate_slug(match.group(1))
                if str((payload.get("config") or {}).get("slug")) != slug:
                    raise SpeakSportError("Facility slug cannot be changed while editing")
                _write_facility(self.service.root, payload, replace=True)
                self._send_json({"ok": True, "slug": slug})
                return
            if match := re.fullmatch(r"/api/modifications/([^/]+)", parsed.path):
                slug = _validate_slug(match.group(1))
                if str((payload.get("config") or {}).get("slug")) != slug:
                    raise SpeakSportError("Modification slug cannot be changed while editing")
                _write_modification(self.service.root, payload, replace=True)
                self._send_json({"ok": True, "slug": slug})
                return
            self._send_json({"error": "Not found"}, 404)
        except (SpeakSportError, ValidationError, OSError) as exc:
            self._send_error(exc)

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        candidate = (STATIC_ROOT / relative).resolve()
        try:
            candidate.relative_to(STATIC_ROOT.resolve())
        except ValueError as exc:
            raise FileNotFoundError(path) from exc
        if not candidate.is_file():
            candidate = STATIC_ROOT / "index.html"
        payload = candidate.read_bytes()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".png": "image/png",
        }.get(candidate.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class SpeakSportHTTPServer(ThreadingHTTPServer):
    service: UIService


def serve(root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    server = SpeakSportHTTPServer((host, port), UIRequestHandler)
    server.service = UIService(root)
    try:
        server.serve_forever()
    finally:
        server.server_close()
