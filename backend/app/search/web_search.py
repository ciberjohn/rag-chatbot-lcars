import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Dict, List

from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=1)


def _do_search(query: str, max_results: int) -> List[Dict]:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def search(query: str, max_results: int = 5, timeout: int = 8) -> List[Dict]:
    # Truncate query to avoid leaking large user inputs to DuckDuckGo
    truncated = query[:200]
    try:
        future = _executor.submit(_do_search, truncated, max_results)
        results = future.result(timeout=timeout)
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
    except FuturesTimeout:
        logger.warning("web search timed out")
        return []
    except Exception as exc:
        logger.error("web search failed: %s", exc)
        return []
