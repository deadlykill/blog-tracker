import logging
import sys

from src.checker import check_all_sites
from src.notifier import send_notification
from src.storage import load_state, save_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("blog-tracker")


def main() -> int:
    logger.info("Starting blog tracker...")

    state = load_state()
    logger.info("Loaded state with %d tracked sites", len(state))

    state, updates = check_all_sites(state)

    save_state(state)
    logger.info("State saved")

    if updates:
        total = sum(len(posts) for posts in updates.values())
        logger.info("Found %d new post(s) across %d site(s)", total, len(updates))
        send_notification(updates)
    else:
        logger.info("No new posts found")

    logger.info("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
