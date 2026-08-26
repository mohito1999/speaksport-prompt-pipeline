from __future__ import annotations

import json
import math
import random
import re
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from ..exceptions import ConfigurationError, ProviderError
from ..hashing import sha256_text, stable_hash
from ..models import CrawledPage, CrawlRequest, CrawlState, CrawlStatus
from ..security import redact_text

ProgressCallback = Callable[[int, int, str], None]


def normalize_crawl_url(value: str) -> str:
    normalized = value.strip()
    if "://" not in normalized:
        normalized = f"https://{normalized}"
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigurationError(f"Invalid website URL: {value}")
    return normalized.rstrip("/")


class FirecrawlClient:
    """Small v2 HTTP adapter with persisted crawl state and immutable raw pages."""

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.Client | None = None,
        base_url: str = "https://api.firecrawl.dev",
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
        max_retries: int = 4,
    ) -> None:
        if not api_key:
            raise ConfigurationError("FIRECRAWL_API_KEY is required for a live crawl")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=60)
        self.sleeper = sleeper
        self.jitter = jitter
        self.max_retries = max_retries

    @staticmethod
    def request_payload(request: CrawlRequest) -> dict[str, object]:
        payload: dict[str, object] = {
            "url": normalize_crawl_url(request.url),
            "sitemap": request.sitemap,
            "crawlEntireDomain": request.crawl_entire_domain,
            "limit": request.limit,
            "allowExternalLinks": request.allow_external_links,
            "allowSubdomains": request.allow_subdomains,
            "ignoreRobotsTxt": request.ignore_robots_txt,
            "scrapeOptions": {
                "onlyMainContent": request.only_main_content,
                "maxAge": request.max_age,
                "parsers": request.parsers,
                "formats": request.formats,
            },
        }
        if request.exclude_paths:
            payload["excludePaths"] = request.exclude_paths
        if request.include_paths:
            payload["includePaths"] = request.include_paths
        return payload

    def start_crawl(self, request: CrawlRequest, state_path: Path) -> CrawlState:
        normalized_request = request.model_copy(update={"url": normalize_crawl_url(request.url)})
        payload = self.request_payload(normalized_request)
        response = self._request_json("POST", f"{self.base_url}/v2/crawl", json_body=payload)
        job_id = str(response.get("id", ""))
        if not job_id:
            raise ProviderError("Firecrawl start response did not contain a crawl job ID")
        state = CrawlState(
            job_id=job_id,
            status_url=f"{self.base_url}/v2/crawl/{job_id}",
            status=CrawlStatus.SCRAPING,
            request=normalized_request,
            request_hash=stable_hash(payload),
        )
        self._save_state(state_path, state)
        return state

    def resume_until_complete(
        self,
        state_path: Path,
        raw_directory: Path,
        *,
        poll_interval_seconds: float = 3,
        max_polls: int = 200,
        progress: ProgressCallback | None = None,
    ) -> CrawlState:
        state = self._load_state(state_path)
        for poll_number in range(max_polls):
            response = self._request_json("GET", state.status_url)
            status_value = str(response.get("status", "scraping"))
            try:
                state.status = CrawlStatus(status_value)
            except ValueError as exc:
                raise ProviderError(f"Unknown Firecrawl crawl status: {status_value}") from exc
            state.total = int(response.get("total") or 0)
            state.completed = int(response.get("completed") or 0)
            state.credits_used = int(response.get("creditsUsed") or 0)
            state.next_url = response.get("next")
            state.updated_at = datetime.now(UTC)
            if progress:
                progress(state.completed, state.total, state.status.value)
            if state.status == CrawlStatus.FAILED:
                state.error = str(response.get("error") or "Firecrawl crawl failed")
                self._save_state(state_path, state)
                raise ProviderError(state.error)
            if state.status == CrawlStatus.COMPLETED:
                self._store_response_pages(response, state, raw_directory)
                next_url = response.get("next")
                while next_url:
                    page_response = self._request_json("GET", str(next_url))
                    self._store_response_pages(page_response, state, raw_directory)
                    next_url = page_response.get("next")
                state.next_url = None
                state.updated_at = datetime.now(UTC)
                self._save_state(state_path, state)
                return state
            self._save_state(state_path, state)
            if poll_number < max_polls - 1:
                self.sleeper(poll_interval_seconds)
        raise ProviderError(
            f"Crawl {state.job_id} is still running; resume with `speaksport crawl "
            f"{state.request.url} --resume`"
        )

    def recover_missing_navigation_pages(
        self,
        state_path: Path,
        raw_directory: Path,
        *,
        max_pages: int = 20,
    ) -> list[str]:
        """Scrape prominent same-domain navigation targets omitted by the bounded crawl."""
        state = self._load_state(state_path)
        raw_pages = [
            CrawledPage.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(raw_directory.glob("*.json"))
        ]
        if len(raw_pages) < 3:
            return []

        crawled_urls = {
            self._comparable_url(page.canonical_url or page.source_url) for page in raw_pages
        }
        root_host = urlparse(state.request.url).hostname
        occurrence: Counter[str] = Counter()
        for page in raw_pages:
            page_links: set[str] = set()
            for raw_link in re.findall(r"\]\(([^)]+)\)", page.markdown):
                candidate = urljoin(page.source_url, raw_link.strip())
                parsed = urlparse(candidate)
                if parsed.scheme not in {"http", "https"} or parsed.hostname != root_host:
                    continue
                if re.search(
                    r"\.(?:png|jpe?g|gif|webp|svg|ico|mp4|mov|avi|zip)(?:$|[?#])",
                    parsed.path,
                    flags=re.IGNORECASE,
                ):
                    continue
                page_links.add(self._comparable_url(candidate))
            occurrence.update(page_links)

        prominence = max(3, math.ceil(len(raw_pages) * 0.30))
        missing = [
            url
            for url, count in occurrence.most_common()
            if count >= prominence and url not in crawled_urls
        ][:max_pages]
        recovered: list[str] = []
        for url in missing:
            payload: dict[str, object] = {
                "url": url,
                "formats": state.request.formats,
                "onlyMainContent": False,
                "maxAge": 0,
                "parsers": state.request.parsers,
            }
            response = self._request_json(
                "POST", f"{self.base_url}/v2/scrape", json_body=payload
            )
            item = response.get("data")
            if not isinstance(item, dict):
                continue
            markdown = str(item.get("markdown") or "").strip()
            if not markdown:
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            content_hash = sha256_text(markdown)
            page = CrawledPage(
                source_url=str(metadata.get("sourceURL") or url),
                canonical_url=str(metadata.get("url")) if metadata.get("url") else url,
                title=str(metadata.get("title")) if metadata.get("title") else None,
                status_code=(
                    int(metadata["statusCode"])
                    if metadata.get("statusCode") is not None
                    else None
                ),
                markdown=markdown,
                content_hash=content_hash,
                crawl_job_id=state.job_id,
                request_options_hash=stable_hash(payload),
            )
            path = raw_directory / f"{content_hash}.json"
            if not path.exists():
                path.write_text(
                    json.dumps(page.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            if content_hash not in state.page_hashes:
                state.page_hashes.append(content_hash)
            recovered.append(url)
        if recovered:
            state.updated_at = datetime.now(UTC)
            self._save_state(state_path, state)
        return recovered

    @staticmethod
    def _comparable_url(value: str) -> str:
        parsed = urlparse(value)
        path = parsed.path.rstrip("/") or "/"
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))

    def _store_response_pages(
        self, response: dict[str, object], state: CrawlState, raw_directory: Path
    ) -> None:
        raw_directory.mkdir(parents=True, exist_ok=True)
        data = response.get("data") or []
        if not isinstance(data, list):
            raise ProviderError("Firecrawl status response contained invalid page data")
        for item in data:
            if not isinstance(item, dict):
                continue
            markdown = str(item.get("markdown") or "").strip()
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            source_url = str(metadata.get("sourceURL") or metadata.get("url") or state.request.url)
            content_hash = sha256_text(markdown)
            page = CrawledPage(
                source_url=source_url,
                canonical_url=str(metadata.get("url")) if metadata.get("url") else None,
                title=str(metadata.get("title")) if metadata.get("title") else None,
                status_code=(
                    int(metadata["statusCode"]) if metadata.get("statusCode") is not None else None
                ),
                markdown=markdown,
                content_hash=content_hash,
                crawl_job_id=state.job_id,
                request_options_hash=state.request_hash,
            )
            path = raw_directory / f"{content_hash}.json"
            if not path.exists():
                path.write_text(
                    json.dumps(page.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            if content_hash not in state.page_hashes:
                state.page_hashes.append(content_hash)

    def _request_json(
        self, method: str, url: str, *, json_body: dict[str, object] | None = None
    ) -> dict[str, object]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(method, url, headers=headers, json=json_body)
            except httpx.RequestError as exc:
                if attempt == self.max_retries:
                    raise ProviderError(
                        redact_text(f"Firecrawl network error: {exc}", [self.api_key])
                    ) from exc
                self.sleeper(min(2**attempt + self.jitter(), 30))
                continue
            if response.status_code < 400:
                value = response.json()
                if not isinstance(value, dict):
                    raise ProviderError("Firecrawl returned a non-object JSON response")
                return value
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                self.sleeper(min(delay + self.jitter(), 60))
                continue
            try:
                detail = response.json().get("error")
            except (ValueError, AttributeError):
                detail = response.text
            raise ProviderError(
                redact_text(
                    f"Firecrawl request failed ({response.status_code}): {detail}",
                    [self.api_key],
                )
            )
        raise ProviderError("Firecrawl request failed after retries")

    @staticmethod
    def _save_state(path: Path, state: CrawlState) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _load_state(path: Path) -> CrawlState:
        if not path.is_file():
            raise ConfigurationError(f"Crawl state does not exist: {path}")
        return CrawlState.model_validate_json(path.read_text(encoding="utf-8"))
