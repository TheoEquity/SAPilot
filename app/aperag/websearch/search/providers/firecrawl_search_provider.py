"""
Firecrawl Search Provider

Web search provider using Firecrawl's search API.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

import aiohttp

from aperag.schema.view_models import WebSearchResultItem
from aperag.websearch.search.base_search import BaseSearchProvider
from aperag.websearch.utils.url_validator import URLValidator

logger = logging.getLogger(__name__)


class FirecrawlSearchProvider(BaseSearchProvider):
    """Firecrawl search provider implementation."""

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.api_key = self.config.get("api_key", "")
        self.base_url = (self.config.get("api_url") or "https://api.firecrawl.dev/v1").rstrip("/")
        self.supported_engines = ["firecrawl", "firecrawl_search"]

    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: int = 30,
        locale: str = "en-US",
        source: Optional[str] = None,
    ) -> List[WebSearchResultItem]:
        if not self.api_key:
            raise ValueError("Firecrawl API key is required")

        has_query = query and query.strip()
        has_source = source and source.strip()
        if not has_query and not has_source:
            raise ValueError("Either query or source must be provided")
        if max_results <= 0:
            raise ValueError("max_results must be positive")
        if max_results > 100:
            raise ValueError("max_results cannot exceed 100")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        final_query = (query or "").strip()
        include_domains: list[str] = []
        if has_source:
            target_domain = URLValidator.extract_domain_from_source(source)
            if target_domain:
                include_domains.append(target_domain)
                if has_query:
                    final_query = query.strip()
                else:
                    final_query = f"site:{target_domain}"
            elif not has_query:
                raise ValueError("Invalid source domain and no query provided")

        if not final_query:
            raise ValueError("Search query cannot be empty")

        return await self._search_remote(
            query=final_query,
            max_results=max_results,
            timeout=timeout,
            locale=locale,
            include_domains=include_domains,
        )

    async def _search_remote(
        self,
        query: str,
        max_results: int,
        timeout: int,
        locale: str,
        include_domains: list[str],
    ) -> List[WebSearchResultItem]:
        payload = {
            "query": query,
            "limit": max_results,
            "lang": self._locale_to_lang(locale),
        }
        if include_domains:
            payload["includeDomains"] = include_domains

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        search_url = f"{self.base_url}/search"
        logger.info("Firecrawl search request: %s", search_url)

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.post(search_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        raise ValueError(f"Firecrawl search failed: {response.status} {response_text}")
                    response_data = await response.json()
                    return self._parse_firecrawl_response(response_data, max_results)
        except asyncio.TimeoutError as e:
            raise ValueError(f"Firecrawl search timed out after {timeout} seconds") from e

    def _parse_firecrawl_response(self, response_data: dict, max_results: int) -> List[WebSearchResultItem]:
        data = (response_data or {}).get("data") or []
        if isinstance(data, dict):
            web_results = data.get("web") or []
        elif isinstance(data, list):
            web_results = data
        else:
            web_results = []
        results = []

        for i, item in enumerate(web_results[:max_results], start=1):
            url = item.get("url", "")
            if not URLValidator.is_valid_url(url):
                continue
            title = (item.get("title") or "No Title").strip()
            snippet = (item.get("description") or item.get("snippet") or "").strip()
            results.append(
                WebSearchResultItem(
                    rank=i,
                    title=title,
                    url=url,
                    snippet=snippet,
                    domain=URLValidator.extract_domain(url),
                    timestamp=datetime.now(),
                )
            )

        return results

    def _locale_to_lang(self, locale: str) -> str:
        if not locale:
            return "en"
        return locale.split("-")[0].split("_")[0].lower() or "en"

    def get_supported_engines(self) -> List[str]:
        return self.supported_engines.copy()
