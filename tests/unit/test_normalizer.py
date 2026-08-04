import json
from pathlib import Path

from speaksport_pipeline.crawling import normalize_raw_pages
from speaksport_pipeline.hashing import sha256_text
from speaksport_pipeline.models import CrawledPage


def test_normalizer_deduplicates_without_modifying_raw_records(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    normalized = tmp_path / "normalized"
    raw.mkdir()
    page = CrawledPage(
        source_url="https://example.com",
        markdown="# Home\n\nFacts.\n\n\n",
        content_hash=sha256_text("# Home\n\nFacts.\n\n\n"),
        crawl_job_id="job",
        request_options_hash="a" * 64,
    )
    original = json.dumps(page.model_dump(mode="json"), indent=2)
    (raw / "one.json").write_text(original, encoding="utf-8")
    (raw / "two.json").write_text(original, encoding="utf-8")

    pages = normalize_raw_pages(raw, normalized)

    assert len(pages) == 1
    assert pages[0].source_identifier == "WEB-001"
    assert "source-url" in (normalized / "web-001.md").read_text(encoding="utf-8")
    assert (raw / "one.json").read_text(encoding="utf-8") == original
