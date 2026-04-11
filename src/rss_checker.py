import logging
from datetime import datetime

import feedparser

logger = logging.getLogger(__name__)


def check_rss_feed(site: dict) -> list[dict]:
    """Fetch an RSS/Atom feed and return a list of post entries.

    Each entry is a dict with keys: title, url, date.
    """
    url = site["url"]
    logger.info("Fetching RSS feed: %s", url)

    feed = feedparser.parse(url)

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
