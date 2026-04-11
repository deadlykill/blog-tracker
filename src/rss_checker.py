import logging
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
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

REQUEST_TIMEOUT = 30


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
    """Fetch feed with browser headers, then parse with feedparser.

    Some feeds (e.g. Medium/TDS) return 403 status but still include valid
    XML in the response body, so we check the body content regardless of
    status code.  If the response is a non-XML error page (e.g. Cloudflare
    challenge), we skip the useless feedparser fallback.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)

        body = resp.text.strip()
        is_xml = body.startswith(("<?xml", "<rss", "<feed", "<atom"))

        if resp.status_code == 200 or is_xml:
            feed = feedparser.parse(resp.text)
            if feed.entries:
                return feed

        if resp.status_code != 200:
            logger.warning(
                "HTTP %d fetching %s — site may block datacenter IPs",
                resp.status_code,
                url,
            )
            if not is_xml:
                return feedparser.FeedParserDict(
                    bozo=True,
                    bozo_exception=Exception(
                        f"HTTP {resp.status_code} with non-XML body (likely Cloudflare)"
                    ),
                    entries=[],
                )
    except requests.RequestException as exc:
        logger.warning("Request failed for %s: %s — falling back to feedparser", url, exc)

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
