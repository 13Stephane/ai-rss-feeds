"""Health-check the published RSS feeds and report any that have failed.

Fetches each feed from its published URL (or from ./feeds with --local) and
checks that it is reachable, returns HTTP 200, parses as RSS 2.0 with enough
items, and is fresh. Feed keys come from feeds.toml so this never drifts from
the generator's configuration.

Only the standard library is used, so this runs without the scraping deps.

Usage:
    uv run python check_feeds.py
    uv run python check_feeds.py --local
    uv run python check_feeds.py --max-age-days 30 --report report.md
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from src.feed_config import is_external, load_all_feeds


DEFAULT_BASE_URL = (
    "https://raw.githubusercontent.com/alan-turing-institute/ai-rss-feeds/refs/heads/main"
)
DEFAULT_MAX_AGE_DAYS = 21
DEFAULT_MIN_ITEMS = 1
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRIES = 3

FEEDS_DIR = Path(__file__).resolve().parent / "feeds"

# Some CDNs reject requests without a User-Agent, which would look like a feed
# failure rather than a client problem.
USER_AGENT = "ai-rss-feeds-health-check (+https://github.com/alan-turing-institute/ai-rss-feeds)"


class FeedFailure(Exception):
    """A feed check failed. `kind` is the short failure class for reporting."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that published RSS feeds are reachable, valid, and fresh."
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("FEED_HEALTH_BASE_URL") or DEFAULT_BASE_URL,
        help="Base URL the feeds are published under (the parent of /feeds).",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Check files in ./feeds instead of fetching published URLs.",
    )
    parser.add_argument(
        "--max-age-days",
        type=float,
        default=DEFAULT_MAX_AGE_DAYS,
        help=f"Fail a feed with no new item in this many days (default: {DEFAULT_MAX_AGE_DAYS}).",
    )
    parser.add_argument(
        "--age-overrides",
        default="",
        help='JSON map of per-feed age limits in days, e.g. \'{"turing-news": 90}\'.',
    )
    parser.add_argument(
        "--min-items",
        type=int,
        default=DEFAULT_MIN_ITEMS,
        help=f"Fail a feed with fewer than this many items (default: {DEFAULT_MIN_ITEMS}).",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated feed keys to check. Defaults to all configured feeds.",
    )
    parser.add_argument(
        "--skip",
        default="",
        help="Comma-separated feed keys to exclude from the check.",
    )
    parser.add_argument(
        "--include-broken",
        action="store_true",
        help="Also check feeds marked broken=true in feeds.toml (skipped by default).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-request timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Attempts per feed before reporting it unreachable (default: {DEFAULT_RETRIES}).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Write a Markdown report of the results to this path.",
    )
    return parser.parse_args()


def parse_key_list(raw: str) -> set[str]:
    return {key.strip() for key in raw.replace("\n", ",").split(",") if key.strip()}


def parse_age_overrides(raw: str) -> dict[str, float]:
    if not raw.strip():
        return {}

    try:
        overrides = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--age-overrides is not valid JSON: {exc}")

    if not isinstance(overrides, dict):
        raise SystemExit("--age-overrides must be a JSON object mapping feed keys to days")

    parsed = {}
    for feed_key, days in overrides.items():
        if not isinstance(days, (int, float)) or isinstance(days, bool):
            raise SystemExit(f"--age-overrides value for '{feed_key}' must be a number")
        parsed[feed_key] = float(days)
    return parsed


def fetch_feed(url: str, timeout: float, retries: int) -> bytes:
    """Return the feed body, raising FeedFailure if it can't be fetched."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    # urlopen raises for most non-200s; this covers the rest.
                    raise FeedFailure(
                        f"HTTP_{response.status}", f"returned HTTP {response.status}"
                    )
                return response.read()
        except urllib.error.HTTPError as exc:
            # A non-200 is a definite answer from the server, so don't retry it.
            raise FeedFailure(f"HTTP_{exc.code}", f"returned HTTP {exc.code} {exc.reason}")
        except (urllib.error.URLError, ssl.SSLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2**attempt)

    raise FeedFailure("UNREACHABLE", f"could not be fetched after {retries} attempts: {last_error}")


def read_local_feed(feed_key: str) -> bytes:
    path = FEEDS_DIR / f"{feed_key}.xml"
    try:
        return path.read_bytes()
    except FileNotFoundError:
        raise FeedFailure("MISSING", f"no feed file at {path}")


def parse_channel(body: bytes) -> ET.Element:
    """Return the RSS <channel> element, raising FeedFailure if malformed."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise FeedFailure("MALFORMED", f"is not well-formed XML: {exc}")

    if root.tag != "rss":
        raise FeedFailure("MALFORMED", f"root element is <{root.tag}>, expected <rss>")

    channel = root.find("channel")
    if channel is None:
        raise FeedFailure("MALFORMED", "has no <channel> element")

    if not (channel.findtext("title") or "").strip():
        raise FeedFailure("MALFORMED", "has no channel <title>")

    return channel


def newest_entry_date(channel: ET.Element) -> tuple[datetime | None, str]:
    """Return the newest item pubDate, falling back to lastBuildDate."""
    item_dates = []
    for item in channel.findall("item"):
        raw_date = item.findtext("pubDate")
        if not raw_date:
            continue
        try:
            item_dates.append(parsedate_to_datetime(raw_date))
        except (TypeError, ValueError):
            continue

    if item_dates:
        return max(item_dates), "newest item"

    raw_build_date = channel.findtext("lastBuildDate")
    if raw_build_date:
        try:
            return parsedate_to_datetime(raw_build_date), "lastBuildDate"
        except (TypeError, ValueError):
            pass

    return None, "no date"


def check_feed(body: bytes, min_items: int, max_age_days: float, now: datetime) -> dict:
    """Validate a feed body, raising FeedFailure on the first problem found."""
    channel = parse_channel(body)

    item_count = len(channel.findall("item"))
    if item_count < min_items:
        raise FeedFailure("MALFORMED", f"has {item_count} items, expected at least {min_items}")

    newest, date_source = newest_entry_date(channel)
    if newest is None:
        raise FeedFailure("MALFORMED", "has no parseable pubDate or lastBuildDate")

    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)

    age_days = (now - newest).total_seconds() / 86400
    if age_days > max_age_days:
        raise FeedFailure(
            "STALE",
            f"has had no new content for {age_days:.1f} days "
            f"(limit {max_age_days:g}, from {date_source} {newest:%Y-%m-%d})",
        )

    return {"item_count": item_count, "age_days": age_days, "date_source": date_source}


def build_report(results: list[dict], failures: list[dict], context: dict) -> str:
    lines = ["# RSS feed health check", ""]

    if failures:
        lines.append(f"**{len(failures)} of {len(results)} feeds failed.**")
    else:
        lines.append(f"All {len(results)} feeds passed.")

    lines += [
        "",
        f"- Source: `{context['source']}`",
        f"- Staleness limit: {context['max_age_days']:g} days",
        f"- Minimum items: {context['min_items']}",
        f"- Checked at: {context['now']:%Y-%m-%d %H:%M} UTC",
        "",
    ]

    if failures:
        lines += ["## Failures", "", "| Feed | Problem | Detail |", "|---|---|---|"]
        for failure in failures:
            lines.append(f"| `{failure['feed_key']}` | {failure['kind']} | {failure['detail']} |")
        lines.append("")

    lines += ["## All feeds", "", "| Feed | Status | Items | Age (days) |", "|---|---|---|---|"]
    for result in results:
        if result["ok"]:
            lines.append(
                f"| `{result['feed_key']}` | OK | {result['item_count']} | {result['age_days']:.1f} |"
            )
        else:
            lines.append(f"| `{result['feed_key']}` | {result['kind']} | — | — |")
    lines.append("")

    if context["skipped"]:
        skipped = ", ".join(f"`{key}`" for key in context["skipped"])
        lines += [f"Skipped: {skipped}", ""]

    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc)

    all_feeds = load_all_feeds()
    only_keys = parse_key_list(args.only)
    skip_keys = parse_key_list(args.skip)
    age_overrides = parse_age_overrides(args.age_overrides)

    unknown = sorted((only_keys | skip_keys | set(age_overrides)) - set(all_feeds))
    if unknown:
        raise SystemExit(f"Unknown feed keys: {', '.join(unknown)}")

    selected_keys = sorted(only_keys or set(all_feeds))

    skipped = []
    feed_keys = []
    for feed_key in selected_keys:
        if feed_key in skip_keys:
            skipped.append(f"{feed_key} (skip list)")
        elif all_feeds[feed_key].get("broken") and not args.include_broken:
            skipped.append(f"{feed_key} (broken=true)")
        elif args.local and is_external(all_feeds[feed_key]):
            # Nothing is generated for an external feed, so there is no local
            # file to check — only the published URL means anything.
            skipped.append(f"{feed_key} (external, no local file)")
        else:
            feed_keys.append(feed_key)

    if not feed_keys:
        raise SystemExit("No feeds selected to check.")

    base_url = args.base_url.rstrip("/")
    source = "./feeds" if args.local else f"{base_url}/feeds"
    print(f"Checking {len(feed_keys)} feeds from {source}")

    results = []
    failures = []

    for feed_key in feed_keys:
        max_age_days = age_overrides.get(feed_key, args.max_age_days)
        config = all_feeds[feed_key]
        try:
            if args.local:
                body = read_local_feed(feed_key)
            else:
                # An external feed lives at the publisher's URL; a generated one
                # lives under the base URL this repo publishes to.
                if is_external(config):
                    feed_url = config["external_feed_url"]
                else:
                    feed_url = f"{base_url}/feeds/{feed_key}.xml"
                body = fetch_feed(feed_url, args.timeout, args.retries)
            checked = check_feed(body, args.min_items, max_age_days, now)
        except FeedFailure as failure:
            print(f"FAIL: {feed_key}: {failure.kind}: {failure.detail}")
            record = {
                "feed_key": feed_key,
                "ok": False,
                "kind": failure.kind,
                "detail": failure.detail,
            }
            results.append(record)
            failures.append(record)
            continue

        print(
            f"OK: {feed_key}: {checked['item_count']} items, "
            f"newest {checked['age_days']:.1f} days old"
        )
        results.append({"feed_key": feed_key, "ok": True, **checked})

    for note in skipped:
        print(f"SKIP: {note}")

    context = {
        "source": source,
        "max_age_days": args.max_age_days,
        "min_items": args.min_items,
        "now": now,
        "skipped": skipped,
    }

    if args.report:
        args.report.write_text(build_report(results, failures, context), encoding="utf-8")

    if os.environ.get("GITHUB_ACTIONS") == "true":
        for failure in failures:
            print(f"::error::{failure['feed_key']}: {failure['kind']}: {failure['detail']}")

    if failures:
        print(f"\n{len(failures)} of {len(results)} feeds failed.", file=sys.stderr)
        raise SystemExit(1)

    print(f"\nAll {len(results)} feeds passed.")


if __name__ == "__main__":
    main()
