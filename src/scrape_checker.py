import logging
import warnings
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 30


def check_scraped_site(site: dict) -> list[dict]:
    """Scrape a webpage and extract post links using the configured CSS selector.

    Returns a list of dicts with keys: title, url.
    """
    url = site["url"]
    selector = site.get("selector", "a[href]")
    base_url = site.get("base_url", url)

    logger.info("Scraping: %s", url)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    links = soup.select(selector)

    posts_by_url: dict[str, dict] = {}

    for link in links:
        href = link.get("href", "").strip()
        if not href or href == "#" or href.startswith("javascript:"):
            continue

        full_url = urljoin(base_url + "/", href)

        if not _is_article_url(full_url, site):
            continue

        title = _extract_title(link)

        if full_url in posts_by_url:
            existing = posts_by_url[full_url]
            if _is_better_title(title, existing["title"]):
                existing["title"] = title
            continue
        posts_by_url[full_url] = {"title": title, "url": full_url}

    posts = list(posts_by_url.values())

    logger.info("Found %d links from %s", len(posts), site["name"])
    return posts


def _extract_title(link_tag) -> str:
    """Get a reasonable title from a link element, its children, or parent context."""
    text = link_tag.get_text(strip=True)
    if text and len(text) > 3:
        return text[:200]

    parent = link_tag.parent
    if parent:
        heading = parent.find(["h1", "h2", "h3", "h4"])
        if heading:
            ht = heading.get_text(strip=True)
            if ht and len(ht) > 3:
                return ht[:200]

    img = link_tag.find("img")
    if img and img.get("alt"):
        return img["alt"][:200]

    return link_tag.get("href", "Untitled")


def _is_better_title(new: str, old: str) -> bool:
    """Return True if the new title is more descriptive than the old one."""
    if not new or len(new) <= 3:
        return False
    old_looks_like_url = old.startswith(("http://", "https://", "/"))
    new_looks_like_url = new.startswith(("http://", "https://", "/"))
    if old_looks_like_url and not new_looks_like_url:
        return True
    if not old_looks_like_url and new_looks_like_url:
        return False
    return len(new) > len(old)


def _is_article_url(url: str, site: dict) -> bool:
    """Filter out navigation links, anchors, and other non-article URLs."""
    skip_patterns = [
        "/tag/", "/tags/", "/category/", "/about", "/contact",
        "/privacy", "/terms", "/login", "/signup", "/sign-in",
        "/feed", "/rss", ".xml", ".json", ".css", ".js",
        "/search", "mailto:", "javascript:",
        "/page/", "/team/",
    ]
    lower = url.lower()
    for pattern in skip_patterns:
        if pattern in lower:
            return False

    base = site.get("base_url", "")
    if base and not url.startswith(("http://", "https://")):
        return False

    return True
