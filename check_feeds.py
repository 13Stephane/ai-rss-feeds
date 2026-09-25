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
from typing import NamedTuple

from src.feed_config import is_external, load_all_feeds


DEFAULT_BASE_URL = (
    "https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main"
)
DEFAULT_MAX_AGE_DAYS = 21
DEFAULT_MIN_ITEMS = 1
DEFAULT_TIMEOUT_SECONDS = 30
# 5 rather than 3: Google News answered 503 to all three of its feeds at once on
# 2026-09-09 and exhausted 3 attempts (~6s of backoff). The backoff doubles per
# attempt, so 5 spans ~30s - long enough to ride out that kind of blip.
DEFAULT_RETRIES = 5

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
            # 4xx is a definite answer from the server, so don't retry it. 5xx
            # and 429 are the server saying "not now": Google News serves an
            # occasional 503 to a request that succeeds moments later, and
            # failing the whole run on one of those reports breakage that isn't
            # there.
            if exc.code < 500 and exc.code != 429:
                raise FeedFailure(
                    f"HTTP_{exc.code}", f"returned HTTP {exc.code} {exc.reason}"
                )
            if attempt == retries:
                raise FeedFailure(
                    f"HTTP_{exc.code}",
                    f"returned HTTP {exc.code} {exc.reason} on {retries} attempts",
                )
            time.sleep(2**attempt)
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


ATOM = "{http://www.w3.org/2005/Atom}"


class ParsedFeed(NamedTuple):
    """A feed reduced to what the checks need, whatever format it arrived in."""

    kind: str  # "rss" or "atom"
    entries: list[ET.Element]
    container: ET.Element  # <channel> for RSS, <feed> for Atom


def parse_feed(body: bytes) -> ParsedFeed:
    """Parse RSS 2.0 or Atom 1.0, raising FeedFailure if malformed.

    Atom is here for publishers that offer nothing else - HBR's only feed is
    Atom - not because this repo generates it. Everything it generates is RSS.
    """
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise FeedFailure("MALFORMED", f"is not well-formed XML: {exc}")

    if root.tag == "rss":
        channel = root.find("channel")
        if channel is None:
            raise FeedFailure("MALFORMED", "has no <channel> element")
        if not (channel.findtext("title") or "").strip():
            raise FeedFailure("MALFORMED", "has no channel <title>")
        return ParsedFeed("rss", channel.findall("item"), channel)

    if root.tag == f"{ATOM}feed":
        if not (root.findtext(f"{ATOM}title") or "").strip():
            raise FeedFailure("MALFORMED", "has no feed <title>")
        return ParsedFeed("atom", root.findall(f"{ATOM}entry"), root)

    raise FeedFailure(
        "MALFORMED",
        f"root element is <{root.tag}>, expected <rss> or an Atom <feed>",
    )


def parse_timestamp(kind: str, raw: str) -> datetime | None:
    """RSS dates are RFC 822; Atom dates are RFC 3339. Return None if unparseable."""
    try:
        if kind == "rss":
            return parsedate_to_datetime(raw)
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def newest_entry_date(feed: ParsedFeed) -> tuple[datetime | None, str]:
    """Return the newest entry date, falling back to the feed-level date."""
    if feed.kind == "rss":
        entry_tags = ("pubDate",)
        feed_tag, feed_label = "lastBuildDate", "lastBuildDate"
    else:
        # published is the real publication date; updated is the fallback an
        # entry always carries.
        entry_tags = (f"{ATOM}published", f"{ATOM}updated")
        feed_tag, feed_label = f"{ATOM}updated", "feed updated"

    entry_dates = []
    for entry in feed.entries:
        for tag in entry_tags:
            raw_date = entry.findtext(tag)
            if not raw_date:
                continue
            parsed = parse_timestamp(feed.kind, raw_date)
            if parsed is not None:
                entry_dates.append(parsed)
                break

    if entry_dates:
        return max(entry_dates), "newest item"

    # findtext matches direct children only, so this cannot pick up an entry's
    # own date by accident.
    raw_feed_date = feed.container.findtext(feed_tag)
    if raw_feed_date:
        parsed = parse_timestamp(feed.kind, raw_feed_date)
        if parsed is not None:
            return parsed, feed_label

    return None, "no date"


def check_feed(body: bytes, min_items: int, max_age_days: float, now: datetime) -> dict:
    """Validate a feed body, raising FeedFailure on the first problem found."""
    feed = parse_feed(body)

    item_count = len(feed.entries)
    if item_count < min_items:
        raise FeedFailure("MALFORMED", f"has {item_count} items, expected at least {min_items}")

    newest, date_source = newest_entry_date(feed)
    if newest is None:
        raise FeedFailure("MALFORMED", "has no parseable item or feed-level date")

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


def build_report(
    results: list[dict], failures: list[dict], warnings: list[dict], context: dict
) -> str:
    lines = ["# RSS feed health check", ""]

    if failures:
        lines.append(f"**{len(failures)} of {len(results)} feeds failed.**")
    else:
        lines.append(f"All {len(results)} feeds passed.")

    if warnings:
        lines.append(f"{len(warnings)} flaky feed(s) errored without failing the run.")

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

    if warnings:
        lines += ["## Flaky (warned, did not fail)", "", "| Feed | Problem | Detail |", "|---|---|---|"]
        for warning in warnings:
            lines.append(f"| `{warning['feed_key']}` | {warning['kind']} | {warning['detail']} |")
        lines.append("")

    lines += ["## All feeds", "", "| Feed | Status | Items | Age (days) |", "|---|---|---|---|"]
    for result in results:
        if result["ok"]:
            lines.append(
                f"| `{result['feed_key']}` | OK | {result['item_count']} | {result['age_days']:.1f} |"
            )
        else:
            status = f"{result['kind']} (flaky)" if result["flaky"] else result["kind"]
            lines.append(f"| `{result['feed_key']}` | {status} | — | — |")
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
    # A flaky source blocks or stonewalls the runner while serving subscribers
    # normally, so its errors are reported but must not fail the run.
    warnings = []

    for feed_key in feed_keys:
        config = all_feeds[feed_key]
        # Precedence: --age-overrides (or the workflow variable) beats the
        # per-feed max_age_days in feeds.toml, which beats the global default.
        # The per-feed value is for sources that genuinely publish rarely, so
        # their quiet spells do not drown out real breakage.
        max_age_days = age_overrides.get(
            feed_key, config.get("max_age_days", args.max_age_days)
        )
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
            # `flaky` means the source refuses the runner while serving readers
            # normally, so it excuses a failure to *fetch* and nothing else. If
            # the feed came back and parsed, the runner was plainly not blocked,
            # and STALE or MALFORMED is a real finding. Downgrading those too is
            # how a flaky feed that quietly dies stays invisible: turing-blog sat
            # 26 days stale while the run reported "All 18 feeds passed".
            fetch_failed = failure.kind == "UNREACHABLE" or failure.kind.startswith("HTTP_")
            flaky = bool(config.get("flaky")) and fetch_failed
            print(f"{'WARN' if flaky else 'FAIL'}: {feed_key}: {failure.kind}: {failure.detail}")
            record = {
                "feed_key": feed_key,
                "ok": False,
                "flaky": flaky,
                "kind": failure.kind,
                "detail": failure.detail,
            }
            results.append(record)
            (warnings if flaky else failures).append(record)
            continue

        print(
            f"OK: {feed_key}: {checked['item_count']} items, "
            f"newest {checked['age_days']:.1f} days old"
        )
        results.append({"feed_key": feed_key, "ok": True, "flaky": False, **checked})

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
        args.report.write_text(
            build_report(results, failures, warnings, context), encoding="utf-8"
        )

    if os.environ.get("GITHUB_ACTIONS") == "true":
        for failure in failures:
            print(f"::error::{failure['feed_key']}: {failure['kind']}: {failure['detail']}")
        for warning in warnings:
            print(f"::warning::{warning['feed_key']}: {warning['kind']}: {warning['detail']}")

    if warnings:
        print(f"{len(warnings)} flaky feed(s) errored without failing the run.")

    if failures:
        print(f"\n{len(failures)} of {len(results)} feeds failed.", file=sys.stderr)
        raise SystemExit(1)

    print(f"\nAll {len(results)} feeds passed.")


if __name__ == "__main__":
    main()
