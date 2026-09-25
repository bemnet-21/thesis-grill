"""ScholarXIV Papers API client."""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def fetch_related_papers(query: str, limit: int = 3) -> list[dict]:
    """Search ScholarXIV for papers related to the query.

    Returns a list of dicts with keys: id, title, snippet.
    Returns an empty list on any error or missing API key.
    """
    if not settings.SCHOLARXIV_API_KEY:
        logger.warning("SCHOLARXIV_API_KEY not set — skipping paper lookup")
        return []

    url = f"{settings.SCHOLARXIV_API_URL}/api/v1/papers/search"
    headers = {"Authorization": f"Bearer {settings.SCHOLARXIV_API_KEY}"}
    params = {"q": query, "limit": limit}

    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
    except httpx.HTTPError:
        logger.exception("ScholarXIV API request failed")
        return []

    papers = resp.json().get("data", [])
    return [
        {
            "id": p.get("extractedID", ""),
            "title": p.get("title", ""),
            "snippet": (p.get("summary", "") or "")[:300],
        }
        for p in papers[:limit]
    ]
