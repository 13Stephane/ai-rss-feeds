"""Load and validate feed definitions from feeds.toml."""

from pathlib import Path
import tomllib


FEEDS_TOML_PATH = Path(__file__).resolve().parents[1] / "feeds.toml"


# Fields that only make sense for a feed this repo scrapes and generates.
# An external feed is published by someone else, so none of these apply.
SCRAPED_ONLY_FIELDS = {
    "source_url",
    "feed_link",
    "feed_description",
    "language",
    "item_container_selector",
    "item_title_selector",
    "item_link_selector",
    "item_date_selector",
    "item_date_regex",
    "item_description_selector",
    "item_guid_is_permalink",
    "min_item_count",
    "min_item_ratio_vs_previous",
    "format",
    "broken",
}

KNOWN_FEED_FIELDS = {
    "feed_title",
    "external_feed_url",
    "site_url",
    "source_url",
    "feed_link",
    "feed_description",
    "language",
    "item_container_selector",
    "item_title_selector",
    "item_link_selector",
    "item_date_selector",
    "item_date_regex",
    "item_description_selector",
    "item_guid_is_permalink",
    "min_item_count",
    "min_item_ratio_vs_previous",
    "format",
    "broken",
    "flaky",
    "max_age_days",
}


def is_external(config: dict) -> bool:
    """True if the feed is published elsewhere and only passed through to OPML."""
    return bool(config.get("external_feed_url"))


def load_all_feeds() -> dict[str, dict]:
    with FEEDS_TOML_PATH.open("rb") as f:
        data = tomllib.load(f)

    feeds = data.get("feeds")
    if not isinstance(feeds, dict) or not feeds:
        raise RuntimeError("feeds.toml must contain a non-empty [feeds] table")

    for feed_key, config in feeds.items():
        if not isinstance(config, dict):
            raise RuntimeError(f"Feed '{feed_key}' must be a TOML table")

        unknown = sorted(set(config) - KNOWN_FEED_FIELDS)
        if unknown:
            unknown_str = ", ".join(unknown)
            raise RuntimeError(f"Feed '{feed_key}' has unknown fields: {unknown_str}")

        if not config.get("feed_title"):
            raise RuntimeError(f"Feed '{feed_key}' is missing required field: feed_title")

        if is_external(config):
            # Scraping fields on an external feed would be silently ignored,
            # which reads as configuration that works when it does nothing.
            conflicting = sorted(set(config) & SCRAPED_ONLY_FIELDS)
            if conflicting:
                conflicting_str = ", ".join(conflicting)
                raise RuntimeError(
                    f"External feed '{feed_key}' cannot set scraping fields: {conflicting_str}"
                )
        elif config.get("site_url"):
            # site_url only exists to give external feeds an htmlUrl; a scraped
            # feed already has source_url for that.
            raise RuntimeError(
                f"Feed '{feed_key}' sets site_url but is not external — use source_url"
            )

    return feeds


def load_feed(feed_key: str) -> dict:
    feeds = load_all_feeds()
    if feed_key not in feeds:
        known = ", ".join(sorted(feeds))
        raise RuntimeError(f"Unknown feed_key '{feed_key}'. Known feeds: {known}")
    return feeds[feed_key]


def list_feed_keys() -> list[str]:
    return sorted(load_all_feeds().keys())


def list_scraped_feed_keys() -> list[str]:
    """Feed keys this repo generates. External feeds are not scraped."""
    return sorted(key for key, config in load_all_feeds().items() if not is_external(config))
