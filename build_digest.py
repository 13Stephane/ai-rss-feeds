"""Build a paste-ready newsletter digest from a generated feed.

Selects the items published in a recent window and renders them as plain
semantic HTML, so it can be pasted into a newsletter editor (beehiiv, Substack)
and pick up that publication's own template styling.

Standard-library only, so it can run with `uv run --no-project`.
"""

import argparse
import html
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


def load_items(feed_path):
    try:
        root = ET.parse(feed_path).getroot()
    except ET.ParseError as exc:
        raise SystemExit(f"{feed_path}: not well-formed XML: {exc}") from exc

    channel = root.find("channel")
    if channel is None:
        raise SystemExit(f"{feed_path}: not an RSS 2.0 feed (no <channel>)")

    items = []
    for item in channel.findall("item"):
        pub_date = item.findtext("pubDate")
        if not pub_date:
            continue
        try:
            date = parsedate_to_datetime(pub_date)
        except (TypeError, ValueError):
            continue
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)

        items.append(
            {
                "title": (item.findtext("title") or "").strip() or "(untitled)",
                "link": (item.findtext("link") or "").strip(),
                "body": item.findtext("description") or "",
                "date": date.astimezone(timezone.utc),
            }
        )

    items.sort(key=lambda item: item["date"], reverse=True)
    return channel.findtext("title") or feed_path.stem, items


def render(feed_title, items, since, until):
    def day(value):
        return value.strftime("%-d %B %Y")

    count = len(items)
    parts = [
        f"<p><strong>{count} new post{'' if count == 1 else 's'}</strong> "
        f"from {html.escape(feed_title)}, {day(since)} to {day(until)}.</p>",
    ]

    for item in items:
        title = html.escape(item["title"])
        heading = (
            f'<a href="{html.escape(item["link"], quote=True)}">{title}</a>'
            if item["link"]
            else title
        )
        parts.append("<hr>")
        parts.append(f"<h2>{heading}</h2>")
        parts.append(f"<p><em>{day(item['date'])}</em></p>")
        # The feed carries each post's own HTML body, already escaped as text
        # by the feed generator, so it goes back out as markup here.
        parts.append(item["body"])

    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--feed",
        default="theaiminute-blog",
        help="feed key to digest (default: theaiminute-blog)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="how many days back to include (default: 7)",
    )
    parser.add_argument(
        "--out",
        default="digest.html",
        help="where to write the digest (default: digest.html)",
    )
    args = parser.parse_args()

    feed_path = Path("feeds") / f"{args.feed}.xml"
    if not feed_path.exists():
        raise SystemExit(
            f"{feed_path} does not exist — generate it first with "
            f"`uv run python generate_feeds.py {args.feed}`"
        )

    feed_title, items = load_items(feed_path)

    until = datetime.now(timezone.utc)
    since = until - timedelta(days=args.days)
    recent = [item for item in items if item["date"] >= since]

    if not recent:
        # No file is written, so a caller can treat "no output" as "nothing to
        # send" rather than mailing an empty issue every week.
        print(f"No items in {feed_path} published in the last {args.days} days.")
        return 0

    Path(args.out).write_text(render(feed_title, recent, since, until), encoding="utf-8")
    print(f"Wrote {args.out}: {len(recent)} item(s) from the last {args.days} days.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
