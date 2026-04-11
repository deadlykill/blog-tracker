import logging
import re
from datetime import datetime

import feedparser
import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}

_INVALID_XML_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f"
    r"\ud800-\udfff\ufffe\uffff]"
)


def _sanitize_xml(text: str) -> str:
    """Strip characters that are illegal in XML 1.0."""
    return _INVALID_XML_RE.sub("", text)


def check_rss_feed(site: dict) -> list[dict]:
    """Fetch an RSS/Atom feed and return a list of post entries.

    Each entry is a dict with keys: title, url, date.
    """
    url = site["url"]
    logger.info("Fetching RSS feed: %s", url)

    feed = _fetch_and_parse(url)

    if feed.bozo and not feed.entries:
        logger.warning("Feed parse error for %s: %s", url, feed.bozo_exception)
        return []

    posts = []
    for entry in feed.entries:
        title = entry.get("title", "Untitled")
        link = entry.get("link", "")
        if not link:
            continue

        date_str = _extract_date(entry)
        posts.append({"title": title, "url": link, "date": date_str})

    logger.info("Found %d entries in %s", len(posts), site["name"])
    return posts


def _fetch_and_parse(url: str):
    """Download feed content, sanitize invalid XML chars, then parse."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        clean = _sanitize_xml(resp.text)
        return feedparser.parse(clean)
    except requests.RequestException as exc:
        logger.warning("HTTP error fetching feed %s: %s", url, exc)
        return feedparser.parse(url)


def _extract_date(entry) -> str:
    """Try to pull a human-readable date from an RSS entry."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6]).strftime("%Y-%m-%d")
            except Exception:
                pass

    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            return raw[:10]

    return ""
