import json
import os

DEFAULT_STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "state.json",
)


def load_state(path: str = DEFAULT_STATE_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_state(state: dict, path: str = DEFAULT_STATE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_known_urls(state: dict, site_id: str) -> set:
    return set(state.get(site_id, []))


def update_known_urls(state: dict, site_id: str, urls: list) -> dict:
    existing = set(state.get(site_id, []))
    existing.update(urls)
    state[site_id] = sorted(existing)
    return state
