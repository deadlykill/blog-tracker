"""
Dynamic test suite for Blog Tracker.

Reads sites.json at runtime so tests automatically adapt
when you add, remove, or disable sources.

Usage:
    python test_tracker.py              # run all tests
    python test_tracker.py --quick      # skip live network tests
    python test_tracker.py --verbose    # show detailed output per site
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.storage import load_state, save_state, get_known_urls, update_known_urls
from src.checker import load_sites, check_all_sites, _fetch_posts, _find_new_posts
from src.notifier import _format_plain, _format_html
from src.rss_checker import check_rss_feed
from src.scrape_checker import check_scraped_site


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class TestRunner:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors: list[str] = []

    def ok(self, label: str, detail: str = ""):
        self.passed += 1
        msg = f"  {Colors.GREEN}PASS{Colors.RESET}  {label}"
        if detail and self.verbose:
            msg += f"  ({detail})"
        print(msg)

    def fail(self, label: str, reason: str = ""):
        self.failed += 1
        full = f"{label}: {reason}" if reason else label
        self.errors.append(full)
        print(f"  {Colors.RED}FAIL{Colors.RESET}  {label}")
        if reason:
            print(f"        └─ {reason}")

    def skip(self, label: str, reason: str = ""):
        self.skipped += 1
        msg = f"  {Colors.YELLOW}SKIP{Colors.RESET}  {label}"
        if reason:
            msg += f"  ({reason})"
        print(msg)

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print()
        print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.BOLD}  Results: {total} tests{Colors.RESET}")
        print(f"    {Colors.GREEN}{self.passed} passed{Colors.RESET}  "
              f"{Colors.RED}{self.failed} failed{Colors.RESET}  "
              f"{Colors.YELLOW}{self.skipped} skipped{Colors.RESET}")
        print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")

        if self.errors:
            print(f"\n{Colors.RED}Failures:{Colors.RESET}")
            for err in self.errors:
                print(f"  - {err}")

        return 0 if self.failed == 0 else 1


def section(title: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}[{title}]{Colors.RESET}")


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------
def test_storage(runner: TestRunner):
    section("Storage")

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test_state.json")

        empty = load_state(path)
        if empty == {}:
            runner.ok("load_state returns {} for missing file")
        else:
            runner.fail("load_state missing file", f"got {empty!r}")

        sample = {"site_a": ["https://a.com/1", "https://a.com/2"]}
        save_state(sample, path)
        loaded = load_state(path)
        if loaded == sample:
            runner.ok("save_state → load_state round-trip")
        else:
            runner.fail("save_state round-trip", f"got {loaded!r}")

        urls = get_known_urls(loaded, "site_a")
        if urls == {"https://a.com/1", "https://a.com/2"}:
            runner.ok("get_known_urls returns correct set")
        else:
            runner.fail("get_known_urls", f"got {urls!r}")

        if get_known_urls(loaded, "nonexistent") == set():
            runner.ok("get_known_urls returns empty set for unknown site")
        else:
            runner.fail("get_known_urls unknown site")

        updated = update_known_urls(loaded, "site_a", ["https://a.com/3"])
        expected_urls = {"https://a.com/1", "https://a.com/2", "https://a.com/3"}
        if set(updated["site_a"]) == expected_urls:
            runner.ok("update_known_urls merges new URLs")
        else:
            runner.fail("update_known_urls", f"got {updated['site_a']}")

        new_state = update_known_urls({}, "brand_new", ["https://x.com/1"])
        if set(new_state["brand_new"]) == {"https://x.com/1"}:
            runner.ok("update_known_urls creates new site entry")
        else:
            runner.fail("update_known_urls new site")

        corrupt_path = os.path.join(tmp, "bad.json")
        with open(corrupt_path, "w") as f:
            f.write("{bad json!!")
        if load_state(corrupt_path) == {}:
            runner.ok("load_state handles corrupt JSON gracefully")
        else:
            runner.fail("load_state corrupt JSON")


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------
def test_config(runner: TestRunner):
    section("Configuration")

    try:
        sites = load_sites()
    except Exception as e:
        runner.fail("load_sites()", str(e))
        return

    if isinstance(sites, list) and len(sites) > 0:
        runner.ok("load_sites returns non-empty list", f"{len(sites)} sites")
    else:
        runner.fail("load_sites", "empty or not a list")
        return

    required_keys = {"id", "name", "type", "url"}
    for site in sites:
        missing = required_keys - set(site.keys())
        if missing:
            runner.fail(f"site '{site.get('name', '?')}' config", f"missing keys: {missing}")
        else:
            runner.ok(f"site '{site['name']}' has required keys")

    ids = [s["id"] for s in sites]
    if len(ids) == len(set(ids)):
        runner.ok("all site IDs are unique")
    else:
        dupes = [x for x in ids if ids.count(x) > 1]
        runner.fail("duplicate site IDs", str(set(dupes)))

    enabled = [s for s in sites if s.get("enabled", True)]
    disabled = len(sites) - len(enabled)
    runner.ok(f"{len(enabled)} enabled, {disabled} disabled sites found")


# ---------------------------------------------------------------------------
# State file tests
# ---------------------------------------------------------------------------
def test_state_file(runner: TestRunner):
    section("State File")

    state_path = BASE_DIR / "data" / "state.json"
    if not state_path.exists():
        runner.skip("state.json existence", "file not created yet (first run pending)")
        return

    state = load_state(str(state_path))
    if isinstance(state, dict):
        runner.ok("state.json is a valid dict", f"{len(state)} sites tracked")
    else:
        runner.fail("state.json", "not a dict")
        return

    sites = load_sites()
    site_ids = {s["id"] for s in sites}
    tracked_ids = set(state.keys())

    in_config = tracked_ids & site_ids
    orphaned = tracked_ids - site_ids
    untracked = site_ids - tracked_ids

    runner.ok(f"{len(in_config)} sites tracked and in config")

    if orphaned:
        runner.skip(f"{len(orphaned)} orphaned state entries", ", ".join(sorted(orphaned)))

    if untracked:
        runner.ok(f"{len(untracked)} sites not yet tracked (first-run pending)")

    for site_id, urls in state.items():
        if not isinstance(urls, list):
            runner.fail(f"state['{site_id}'] type", f"expected list, got {type(urls).__name__}")
        elif len(urls) == 0:
            runner.skip(f"state['{site_id}']", "empty URL list")
        else:
            runner.ok(f"state['{site_id}']", f"{len(urls)} URLs stored")


# ---------------------------------------------------------------------------
# Notifier formatting tests
# ---------------------------------------------------------------------------
def test_notifier(runner: TestRunner):
    section("Notifier Formatting")

    sample_updates = {
        "Test Blog": [
            {"title": "Post One", "url": "https://example.com/1", "date": "2026-04-11"},
            {"title": "Post Two", "url": "https://example.com/2"},
        ],
        "Another Blog": [
            {"title": "Hello World", "url": "https://other.com/hello", "date": "2026-04-10"},
        ],
    }

    plain = _format_plain(sample_updates)
    if "Test Blog" in plain and "Post One" in plain and "https://example.com/1" in plain:
        runner.ok("plain-text format contains expected content")
    else:
        runner.fail("plain-text format", "missing expected fields")

    html = _format_html(sample_updates)
    if "<html>" in html and "Test Blog" in html and 'href="https://example.com/1"' in html:
        runner.ok("HTML format contains expected markup")
    else:
        runner.fail("HTML format", "missing expected elements")

    if "(2026-04-11)" in plain:
        runner.ok("plain-text includes date when available")
    else:
        runner.fail("plain-text date", "date not shown")

    if "Post Two" in plain and "()" not in plain:
        runner.ok("plain-text omits date gracefully when missing")
    else:
        runner.fail("plain-text missing date handling")


# ---------------------------------------------------------------------------
# Checker logic tests (offline)
# ---------------------------------------------------------------------------
def test_checker_logic(runner: TestRunner):
    section("Checker Logic (offline)")

    posts = [
        {"title": "A", "url": "https://example.com/a"},
        {"title": "B", "url": "https://example.com/b"},
        {"title": "C", "url": "https://example.com/c"},
    ]

    state_empty = {}
    new = _find_new_posts(posts, state_empty, "test_site")
    if new == []:
        runner.ok("first run returns no new posts (baseline)")
    else:
        runner.fail("first-run baseline", f"expected [], got {len(new)} posts")

    state_partial = {"test_site": ["https://example.com/a"]}
    new = _find_new_posts(posts, state_partial, "test_site")
    expected_new = [p for p in posts if p["url"] != "https://example.com/a"]
    if len(new) == 2 and all(p["url"] != "https://example.com/a" for p in new):
        runner.ok("detects 2 new posts correctly")
    else:
        runner.fail("new post detection", f"got {[p['url'] for p in new]}")

    state_full = {"test_site": ["https://example.com/a", "https://example.com/b", "https://example.com/c"]}
    new = _find_new_posts(posts, state_full, "test_site")
    if new == []:
        runner.ok("no new posts when all are known")
    else:
        runner.fail("all-known check", f"got {len(new)} posts")


# ---------------------------------------------------------------------------
# Live network tests (dynamic per config)
# ---------------------------------------------------------------------------
def test_live_sites(runner: TestRunner):
    section("Live Site Checks (network)")

    sites = load_sites()
    enabled = [s for s in sites if s.get("enabled", True)]

    if not enabled:
        runner.skip("no enabled sites to test")
        return

    for site in enabled:
        label = f"{site['name']} ({site['type']})"
        start = time.time()

        try:
            posts = _fetch_posts(site)
            elapsed = time.time() - start

            if posts is None:
                runner.fail(label, "returned None")
            elif isinstance(posts, list) and len(posts) > 0:
                sample = posts[0]
                has_title = "title" in sample
                has_url = "url" in sample
                if has_title and has_url:
                    runner.ok(label, f"{len(posts)} posts in {elapsed:.1f}s")
                else:
                    runner.fail(label, f"post missing title/url keys: {sample.keys()}")
            elif isinstance(posts, list) and len(posts) == 0:
                runner.skip(label, f"0 posts returned in {elapsed:.1f}s (site may be down)")
            else:
                runner.fail(label, f"unexpected type: {type(posts).__name__}")

        except Exception as e:
            runner.fail(label, str(e))


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------
def test_integration(runner: TestRunner):
    section("Integration (full pipeline)")

    with tempfile.TemporaryDirectory() as tmp:
        state_path = os.path.join(tmp, "state.json")
        save_state({}, state_path)

        state = load_state(state_path)
        if state == {}:
            runner.ok("clean state initialized")
        else:
            runner.fail("clean state", f"got {state!r}")
            return

        sites = load_sites()
        enabled = [s for s in sites if s.get("enabled", True)]
        if not enabled:
            runner.skip("integration", "no enabled sites")
            return

        test_site = enabled[0]
        label = test_site["name"]

        try:
            posts = _fetch_posts(test_site)
        except Exception as e:
            runner.fail(f"integration fetch ({label})", str(e))
            return

        if not posts:
            runner.skip(f"integration ({label})", "no posts fetched")
            return

        new = _find_new_posts(posts, state, test_site["id"])
        if new == []:
            runner.ok(f"first-run baseline set for '{label}'")
        else:
            runner.fail(f"integration first-run ({label})", f"expected baseline, got {len(new)} new")
            return

        urls = [p["url"] for p in posts]
        state = update_known_urls(state, test_site["id"], urls)
        save_state(state, state_path)

        state2 = load_state(state_path)
        if set(state2.get(test_site["id"], [])) == set(urls):
            runner.ok(f"state persisted correctly for '{label}'", f"{len(urls)} URLs")
        else:
            runner.fail(f"state persistence ({label})")

        new2 = _find_new_posts(posts, state2, test_site["id"])
        if new2 == []:
            runner.ok(f"second run finds 0 new posts for '{label}'")
        else:
            runner.fail(f"second-run check ({label})", f"got {len(new2)} new")

        fake_post = {"title": "Brand New", "url": "https://fakeblog.test/new-post"}
        new3 = _find_new_posts(posts + [fake_post], state2, test_site["id"])
        if len(new3) == 1 and new3[0]["url"] == fake_post["url"]:
            runner.ok(f"synthetic new post detected for '{label}'")
        else:
            runner.fail(f"synthetic post detection ({label})", f"got {new3}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Blog Tracker Test Suite")
    parser.add_argument("--quick", action="store_true", help="Skip live network tests")
    parser.add_argument("--verbose", action="store_true", help="Show extra detail")
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}Blog Tracker — Dynamic Test Suite{Colors.RESET}")
    print(f"{'=' * 60}")

    runner = TestRunner(verbose=args.verbose)

    test_storage(runner)
    test_config(runner)
    test_state_file(runner)
    test_notifier(runner)
    test_checker_logic(runner)

    if args.quick:
        section("Live Site Checks (network)")
        runner.skip("live checks", "--quick flag set")
        section("Integration (full pipeline)")
        runner.skip("integration", "--quick flag set")
    else:
        test_live_sites(runner)
        test_integration(runner)

    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())
