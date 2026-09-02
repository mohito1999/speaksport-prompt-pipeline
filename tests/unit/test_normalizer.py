import json
from pathlib import Path

from speaksport_pipeline.crawling import assess_crawl_quality, normalize_raw_pages
from speaksport_pipeline.hashing import sha256_text
from speaksport_pipeline.models import CrawledPage, NormalizedPage


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


def test_crawl_quality_detects_pages_that_are_only_repeated_boilerplate() -> None:
    pages = []
    shared = "\n".join(["# Site", "Menu", "- Golf", "- Weddings", "Footer address"])
    for index in range(10):
        body = (
            f"# Empty Page {index}"
            if index < 5
            else (
                f"# Useful Page {index}\n"
                f"Page {index} has detailed rates, operating policies, amenities, event "
                "packages, and caller "
                "information that is distinct to this page and long enough to be useful. "
                f"Additional exact details for section {index} make this genuine body content."
            )
        )
        pages.append(
            NormalizedPage(
                source_identifier=f"WEB-{index:03d}",
                source_url=f"https://example.com/page-{index}",
                markdown=f"{shared}\n{body}",
                content_hash=sha256_text(f"{shared}\n{body}"),
            )
        )

    quality = assess_crawl_quality(pages)

    assert quality.examined_page_count == 10
    assert len(quality.hollow_page_urls) == 5
    assert quality.hollow_ratio == 0.5
