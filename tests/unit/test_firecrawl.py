import json
from pathlib import Path

import httpx

from speaksport_pipeline.hashing import sha256_text, stable_hash
from speaksport_pipeline.models import CrawledPage, CrawlRequest, CrawlState, CrawlStatus
from speaksport_pipeline.providers.firecrawl import FirecrawlClient, normalize_crawl_url


def test_normalize_crawl_url_adds_https() -> None:
    assert normalize_crawl_url("example.com/") == "https://example.com"


def test_crawl_persists_job_pages_pagination_and_no_secret(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    status_polls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal status_polls
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"success": True, "id": "job-123"})
        if request.url.path == "/v2/crawl/job-123":
            status_polls += 1
            if status_polls == 1:
                return httpx.Response(200, json={"status": "scraping", "completed": 1, "total": 2})
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "completed": 2,
                    "total": 2,
                    "creditsUsed": 2,
                    "data": [
                        {
                            "markdown": "# Home\nFacility facts.",
                            "metadata": {
                                "sourceURL": "https://example.com",
                                "title": "Home",
                                "statusCode": 200,
                            },
                        }
                    ],
                    "next": "https://firecrawl.test/next-page",
                },
            )
        if request.url.path == "/next-page":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "markdown": "# Policies\nWalking is permitted.",
                            "metadata": {"sourceURL": "https://example.com/policies"},
                        }
                    ],
                    "next": None,
                },
            )
        raise AssertionError(request.url)

    secret = "firecrawl-secret-value"
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = FirecrawlClient(
        secret,
        client=http,
        base_url="https://firecrawl.test",
        sleeper=lambda _: None,
        jitter=lambda: 0,
    )
    state_path = tmp_path / "state.json"
    raw_directory = tmp_path / "raw"
    request = CrawlRequest(url="example.com")

    started = client.start_crawl(request, state_path)
    completed = client.resume_until_complete(state_path, raw_directory, poll_interval_seconds=0)

    assert started.job_id == "job-123"
    assert completed.status == CrawlStatus.COMPLETED
    assert len(completed.page_hashes) == 2
    assert len(list(raw_directory.glob("*.json"))) == 2
    assert secret not in state_path.read_text(encoding="utf-8")
    posted = json.loads(requests[0].content)
    assert posted["limit"] == 50
    assert posted["scrapeOptions"]["parsers"] == ["pdf"]
    assert posted["scrapeOptions"]["onlyMainContent"] is False
    assert posted["scrapeOptions"]["maxAge"] == 0
    assert posted["allowExternalLinks"] is False
    assert all(request.headers["Authorization"] == f"Bearer {secret}" for request in requests)


def test_firecrawl_retries_429_with_retry_after(tmp_path: Path) -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, json={"error": "slow"})
        return httpx.Response(200, json={"id": "job-456"})

    client = FirecrawlClient(
        "secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        base_url="https://firecrawl.test",
        sleeper=sleeps.append,
        jitter=lambda: 0,
    )
    client.start_crawl(CrawlRequest(url="https://example.com"), tmp_path / "state.json")

    assert attempts == 2
    assert sleeps == [2]


def test_recover_missing_navigation_pages_scrapes_prominent_uncrawled_target(
    tmp_path: Path,
) -> None:
    target = "https://example.com/rates"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v2/scrape":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "markdown": "# Rates\nCurrent detailed rates.",
                        "metadata": {"sourceURL": target, "statusCode": 200},
                    },
                },
            )
        raise AssertionError(request.url)

    client = FirecrawlClient(
        "secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        base_url="https://firecrawl.test",
    )
    state_path = tmp_path / "state.json"
    raw = tmp_path / "raw"
    raw.mkdir()
    request = CrawlRequest(url="https://example.com")
    payload = client.request_payload(request)
    state = CrawlState(
        job_id="job-123",
        status_url="https://firecrawl.test/v2/crawl/job-123",
        status=CrawlStatus.COMPLETED,
        request=request,
        request_hash=stable_hash(payload),
    )
    client._save_state(state_path, state)
    for index in range(4):
        markdown = f"# Page {index}\n[Rates]({target})\nDistinct body {index}."
        page = CrawledPage(
            source_url=f"https://example.com/page-{index}",
            markdown=markdown,
            content_hash=sha256_text(markdown),
            crawl_job_id=state.job_id,
            request_options_hash=state.request_hash,
        )
        (raw / f"page-{index}.json").write_text(
            page.model_dump_json(), encoding="utf-8"
        )

    recovered = client.recover_missing_navigation_pages(state_path, raw)

    assert recovered == [target]
    assert any("Current detailed rates" in path.read_text() for path in raw.glob("*.json"))
