from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..hashing import sha256_text
from ..models import CrawledPage, NormalizedPage


@dataclass(frozen=True)
class CrawlQualityAssessment:
    examined_page_count: int
    hollow_page_urls: tuple[str, ...]

    @property
    def hollow_ratio(self) -> float:
        if not self.examined_page_count:
            return 0.0
        return len(self.hollow_page_urls) / self.examined_page_count


def _clean_markdown(value: str) -> str:
    lines = [line.rstrip() for line in value.replace("\r\n", "\n").splitlines()]
    cleaned = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def normalize_raw_pages(raw_directory: Path, normalized_directory: Path) -> list[NormalizedPage]:
    normalized_directory.mkdir(parents=True, exist_ok=True)
    for stale_path in normalized_directory.glob("web-*.md"):
        stale_path.unlink()
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


def assess_crawl_quality(
    pages: list[NormalizedPage],
    *,
    minimum_unique_characters: int = 120,
) -> CrawlQualityAssessment:
    """Detect pages reduced to a title plus site-wide navigation/footer boilerplate."""
    html_pages = [
        page
        for page in pages
        if not re.search(
            r"\.(?:pdf|png|jpe?g|gif|webp|svg)(?:$|[?#])",
            page.source_url,
            flags=re.IGNORECASE,
        )
    ]
    if len(html_pages) < 8:
        return CrawlQualityAssessment(len(html_pages), ())

    line_sets: list[set[str]] = []
    line_frequency: Counter[str] = Counter()
    for page in html_pages:
        lines = {
            re.sub(r"\s+", " ", line.strip())
            for line in page.markdown.splitlines()
            if line.strip()
        }
        line_sets.append(lines)
        line_frequency.update(lines)

    boilerplate_frequency = max(3, math.ceil(len(html_pages) * 0.30))
    hollow_urls: list[str] = []
    for page, lines in zip(html_pages, line_sets, strict=True):
        unique_text = " ".join(
            line
            for line in lines
            if line_frequency[line] < boilerplate_frequency
            and not line.startswith("<!--")
        )
        unique_characters = len(re.sub(r"[^A-Za-z0-9]+", "", unique_text))
        if unique_characters < minimum_unique_characters:
            hollow_urls.append(page.source_url)

    return CrawlQualityAssessment(len(html_pages), tuple(sorted(hollow_urls)))
