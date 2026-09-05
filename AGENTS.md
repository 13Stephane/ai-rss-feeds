## Overview
- This is a collection of RSS 2.0 feeds for AI news and blog sites which don't provide RSS feeds themselves.
- Tech stack:
    - `uv` for project management - use it to manage packages and run commands in the project.
    - `scrapy` to scrape the sites.
    - `feedgen` to generate RSS feeds.
    - `dateparser` to parse dates.
- Document the feeds in a table in the README, giving the name (e.g. Anthropic News) and filename (e.g. `feeds/anthropic-news.xml`). Keep it sorted by name.
- The README should also document any commands `uv run ...` to generate feeds and instructions for adding new feeds.
- Refer to the README as well as this AGENTS file when you perform a task.

## Scraping with scrapy
- Enable HTTP caching unconditionally. I will delete the cache now and then to keep things fresh.
- Use a single configurable spider class, with per-feed configuration in `feeds.toml`.
- Each feed entry in TOML should define:
  - required fields like `feed_title`, `source_url`, `item_container_selector`, `item_title_selector`, and `item_link_selector`,
  - optional fields like `feed_link`, `feed_description`, and `language`
    (`feed_link` is the page a reader should land on, used for the feed's
    `<link>` and its OPML `htmlUrl`; it defaults to `source_url`, so set it
    only when the two differ),
  - fields like `item_container_selector` (CSS selector for the container for each item)
  - fields like `item_title_selector`, `item_link_selector` (CSS selectors for the title or link for a specific item, scoped to the container for the item, these can be scrapy's extended selectors with the suffixes like `::text` and `::attr(href)`)
  - other supported fields like `item_date_selector`, `item_description_selector`, `item_guid_is_permalink`, `min_item_count`, and `min_item_ratio_vs_previous`.
- These mostly default to `None` and if left as `None` then the corresponding field in the feed or item is not set.
- Be lenient in what selectors can return. For example `item_link_selector` can return either text (the URL) or an HTML node (in which case its `href` attr is taken).
- Don't follow any links (to articles or to later pages of links), just use the information on the source page.
- Don't repeatedly curl a page when developing feeds - put a copy into `./snapshots` and refer to that.
- To refresh a snapshot directly, use e.g. `curl -f https://www.anthropic.com/news -o snapshots/anthropic-news.html`.
- If a new feed can't be scraped with the existing setup, suggest how to proceed and we can discuss before implementing new scraping methods.
- If the feed uses nextjs, you can extract the nextjs data like `uv run python extract_nextjs.py snapshots/cohere-blog.html >snapshots/cohere-blog.nextjs.json`.
- You can find where items are in nextjs like `uv run python json_grep.py snapshots/cohere-blog.nextjs.json "Part of the title"` if the user gives example titles (ask for some).
- If a site's posts load from a plain JSON API (e.g. a Supabase/PostgREST backend) rather than being present in the HTML, use `format = "json"`: `source_url` is the API endpoint itself, `request_headers` (an inline TOML table) carries any required API key/auth header, and the item selectors are jq queries against each returned object, same as nextjs. See README's "Add A New Feed" for the full field list.

## Feed generation
- Each site will correspond to one feed, e.g. the Anthropic News site will become a `anthropic-news.xml` feed.
- Feeds are put into `./feeds`.
- Look at existing feeds (`feeds.toml`) for consistency.
- Use selectors that are likely to be stable over time.
- When you add a new feed, run `uv run python generate_opml.py` to regenerate the OPML list.

## External feeds
- Some sources already publish their own RSS. This repo exists for sites that don't, so those are *not* scraped.
- Add them to `feeds.toml` with `external_feed_url` (and optional `site_url`) instead. They are passed through to `feeds.opml` and checked by `check_feeds.py`, but nothing is generated for them.
- Setting a scraping field on an external feed is a hard error — see `src/feed_config.py`.
- `flaky = true` applies to external feeds too. Some publishers (Substack) refuse GitHub's runner IPs while serving readers normally, so the health check warns instead of failing. Confirm the feed really is fine before reaching for this.

## Broken feeds
- If a feed stops working, it can be marked `broken = true` in `feeds.toml`. This will stop a known problem from failing the whole run, and will flag when it starts working again.
- If a source is *flaky* (intermittently blocks the runner or serves no content, alternating between success and failure), mark it `flaky = true` instead. A flaky feed never fails the run — it warns when it errors and stays silent when it succeeds. Use this only for unreliable sources, not for genuinely-broken feeds (which should stay `broken = true` so they flag when fixed).
- To fix a feed:
  - Grab a new snapshot (as above).
  - If it uses nextjs, extract the data (as above).
  - Read the existing feed in `feeds.toml`.
  - Compare it to the new snapshots and fix the feed.
  - Remove `broken = true`.
- News pages sometimes have featured articles shown differently from the main list, ensure you get them all. It can help if the user supplies the titles for a selection of articles (featured and not), so you can find them more easily in the HTML.

## Regeneration
- There is a github workflow (`.github/workflows/generate-feeds.yml`) that runs every 3 hours.
- Can also trigger it manually.

## Health checks
- `check_feeds.py` checks the *published* feeds are reachable, valid RSS, and fresh. Keep it standard-library only so it can run with `uv run --no-project`.
- A github workflow (`.github/workflows/feed-health.yml`) runs it daily and emails a report on failure.
- Both workflows email via `dawidd6/action-send-mail` using the `MAIL_USERNAME`/`MAIL_PASSWORD` secrets, and skip the email step when those are absent so GitHub's own failure notification still fires.
- Thresholds, the recipient, and the published base URL are repo variables — see the README. Feeds that publish rarely belong in `FEED_HEALTH_AGE_OVERRIDES`, or in a per-feed `max_age_days` in `feeds.toml`, rather than having the global limit raised.
- A source that dates items by month only ("August 2026") resolves to the *first* of that month. Taking the last day would date the current month in the future, and a feed whose newest date is always ahead of now can never be reported stale.
- The flip side: such a feed's newest date is always the 1st of the current month, so its measured age crosses the default 21-day limit on the 22nd of every month whether or not the source published. Give month-only sources a `max_age_days` above ~31 (allenai-news uses 45) or they report stale for the last third of every month.

## Newsletter digest
- `build_digest.py` renders a feed's recent posts as paste-ready HTML for a newsletter editor. Keep it standard-library only, like `check_feeds.py`, so it runs with `uv run --no-project`.
- It emits no file when nothing falls in the window, which is what lets `.github/workflows/weekly-digest.yml` skip a quiet week rather than send an empty issue.
- Deliberately unstyled: the destination publication's template supplies the look, and styling here would fight it.
- beehiiv's automated sends are out of reach on the free plan (RSS-to-Send needs Max, the Send API is Enterprise-only), so the digest stops at the author's inbox and the last step is a manual paste. Don't add a beehiiv API send path without checking the plan actually has it.
