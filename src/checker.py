import json
import logging
import os

from .rss_checker import check_rss_feed
from .scrape_checker import check_scraped_site
from .storage import get_known_urls, update_known_urls

logger = logging.getLogger(__name__)

SITES_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "sites.json",
)


def load_sites(path: str = SITES_CONFIG_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_all_sites(state: dict) -> tuple[dict, dict[str, list[dict]]]:
    """Check every enabled site for new content.

    Returns:
        (updated_state, updates) where updates maps site_name -> list of new posts.
    """
    sites = load_sites()
    all_updates: dict[str, list[dict]] = {}

    for site in sites:
        if not site.get("enabled", True):
            logger.info("Skipping disabled site: %s", site["name"])
            continue

        try:
            posts = _fetch_posts(site)
        except Exception as exc:
            logger.error("Error checking %s: %s", site["name"], exc)
            continue

        if not posts:
            continue

        new_posts = _find_new_posts(posts, state, site["id"])

        if new_posts:
            logger.info(
                "%d new post(s) from %s", len(new_posts), site["name"]
            )
            all_updates[site["name"]] = new_posts
            new_urls = [p["url"] for p in new_posts]
            state = update_known_urls(state, site["id"], new_urls)
        else:
            all_urls = [p["url"] for p in posts]
            state = update_known_urls(state, site["id"], all_urls)

    return state, all_updates


def _fetch_posts(site: dict) -> list[dict]:
    site_type = site.get("type", "scrape")

    if site_type == "rss":
        return check_rss_feed(site)
    elif site_type == "scrape":
        return check_scraped_site(site)
    else:
        logger.warning("Unknown site type '%s' for %s", site_type, site["name"])
        return []


def _find_new_posts(posts: list[dict], state: dict, site_id: str) -> list[dict]:
    """Return only posts whose URL is not already in the known set."""
    known = get_known_urls(state, site_id)

    if not known:
        logger.info(
            "First run for %s — storing %d posts as baseline (no notification)",
            site_id,
            len(posts),
        )
        return []

    return [p for p in posts if p["url"] not in known]
