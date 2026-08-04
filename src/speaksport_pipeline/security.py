from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SecretFinding:
    kind: str
    line: int
    excerpt: str


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OpenRouter-style key", re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{16,}\b")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    (
        "assigned API key",
        re.compile(
            r"(?i)\b(?:FIRECRAWL_API_KEY|OPENROUTER_API_KEY|api[_-]?key)\s*[:=]\s*"
            r"(?:['\"])?(?!\s*$)[A-Za-z0-9._~+/=-]{12,}"
        ),
    ),
)


def configured_secret_values(environment: Mapping[str, str] | None = None) -> list[str]:
    source = environment or os.environ
    return [
        value
        for name in ("FIRECRAWL_API_KEY", "OPENROUTER_API_KEY")
        if len(value := source.get(name, "")) >= 8
    ]


def redact_text(text: str, extra_secrets: Iterable[str] = ()) -> str:
    redacted = text
    for secret in (*configured_secret_values(), *extra_secrets):
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    for _, pattern in SECRET_PATTERNS:
        redacted = pattern.sub("<redacted>", redacted)
    return redacted


def scan_text(text: str, extra_secrets: Iterable[str] = ()) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    lines = text.splitlines() or [text]
    secret_values = [secret for secret in (*configured_secret_values(), *extra_secrets) if secret]
    for line_number, line in enumerate(lines, start=1):
        for secret in secret_values:
            if secret in line:
                findings.append(
                    SecretFinding(
                        "configured secret", line_number, redact_text(line, secret_values)[:160]
                    )
                )
        for kind, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(SecretFinding(kind, line_number, redact_text(line)[:160]))
    return findings


def scan_file(path: Path, extra_secrets: Iterable[str] = ()) -> list[SecretFinding]:
    return scan_text(path.read_text(encoding="utf-8"), extra_secrets=extra_secrets)
