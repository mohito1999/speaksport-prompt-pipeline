from __future__ import annotations

import json
import re
from pathlib import Path

from ..hashing import sha256_text
from ..models import CrawledPage, NormalizedPage


def _clean_markdown(value: str) -> str:
    lines = [line.rstrip() for line in value.replace("\r\n", "\n").splitlines()]
    cleaned = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def normalize_raw_pages(raw_directory: Path, normalized_directory: Path) -> list[NormalizedPage]:
    normalized_directory.mkdir(parents=True, exist_ok=True)
    pages: list[NormalizedPage] = []
    seen_hashes: set[str] = set()
    raw_paths = sorted(raw_directory.glob("*.json"))
    for raw_path in raw_paths:
        raw_value = json.loads(raw_path.read_text(encoding="utf-8"))
        crawled = CrawledPage.model_validate(raw_value)
        markdown = _clean_markdown(crawled.markdown)
        content_hash = sha256_text(markdown)
        if not markdown or content_hash in seen_hashes:
            continue
        seen_hashes.add(content_hash)
        identifier = f"WEB-{len(pages) + 1:03d}"
        page = NormalizedPage(
            source_identifier=identifier,
            source_url=crawled.canonical_url or crawled.source_url,
            title=crawled.title,
            markdown=markdown,
            content_hash=content_hash,
        )
        rendered = (
            f"<!-- source-id: {identifier} -->\n"
            f"<!-- source-url: {page.source_url} -->\n\n"
            f"{markdown}\n"
        )
        (normalized_directory / f"{identifier.lower()}.md").write_text(rendered, encoding="utf-8")
        pages.append(page)
    return pages
