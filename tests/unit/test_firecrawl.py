import json
from pathlib import Path

import httpx

from speaksport_pipeline.models import CrawlRequest, CrawlStatus
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
