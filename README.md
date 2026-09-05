# AI RSS Feeds

This project generates RSS 2.0 feeds for AI news/blog sites that do not publish feeds directly.

You can import all of these feeds into your RSS reader with this [feeds.opml](https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main/feeds.opml) file.

Or you can import selected feeds by copying the URL of the XML files in the below table.

## Feeds

| Name | File |
|---|---|
| [Ai2 News (Allen Institute for AI)](https://allenai.org/news) | [feeds/allenai-news.xml](https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main/feeds/allenai-news.xml) |
| [AISI Blog (AI Security Institute)](https://www.aisi.gov.uk/blog) | [feeds/aisi-blog.xml](https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main/feeds/aisi-blog.xml) |
| [Anthropic News](https://www.anthropic.com/news) | [feeds/anthropic-news.xml](https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main/feeds/anthropic-news.xml) |
| [Anthropic Research](https://www.anthropic.com/research) | [feeds/anthropic-research.xml](https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main/feeds/anthropic-research.xml) |
| [Claude Blog](https://claude.com/blog) | [feeds/claude-blog.xml](https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main/feeds/claude-blog.xml) |
| [HBR AI and Machine Learning](https://hbr.org/topic/subject/ai-and-machine-learning) | [feeds/hbr-ai.xml](https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main/feeds/hbr-ai.xml) |
| [Mila News (Quebec AI Institute)](https://mila.quebec/en/news) | [feeds/mila-news.xml](https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main/feeds/mila-news.xml) |
| [Mistral News](https://mistral.ai/news) | [feeds/mistral-news.xml](https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main/feeds/mistral-news.xml) |
| [The AI Minute](https://www.theaiminute.blog) | [feeds/theaiminute-blog.xml](https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main/feeds/theaiminute-blog.xml) |
| \* [Turing Blog (Alan Turing Institute)](https://www.turing.ac.uk/blog) | [feeds/turing-blog.xml](https://raw.githubusercontent.com/13Stephane/ai-rss-feeds/refs/heads/main/feeds/turing-blog.xml) |

\* These feeds come from a source that intermittently blocks automated access, so they update only when it is reachable.

### External Feeds

These publishers already provide RSS, so this repo generates nothing for them.
They are carried in [feeds.opml](feeds.opml) so they arrive in your reader with
the rest, and the health check verifies them, but the URL points at the
publisher rather than at this repo.

| Name | Feed |
|---|---|
| [AI and Corporate Innovation (Google News)](https://news.google.com/search?hl=en-US&gl=US&ceid=US:en&q=AI%20corporate%20innovation%20OR%20enterprise%20innovation%20OR%20business%20innovation) | https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q=AI%20corporate%20innovation%20OR%20enterprise%20innovation%20OR%20business%20innovation |
| [AI, Culture and Workforce (Google News)](https://news.google.com/search?hl=en-US&gl=US&ceid=US:en&q=AI%20culture%20OR%20talent%20OR%20workforce) | https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q=AI%20culture%20OR%20talent%20OR%20workforce |
| [AI Productivity, Growth and Value (Google News)](https://news.google.com/search?hl=en-US&gl=US&ceid=US:en&q=AI%20productivity%20OR%20growth%20OR%20value) | https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q=AI%20productivity%20OR%20growth%20OR%20value |
| \*\* [Clouded Judgement](https://cloudedjudgement.substack.com/) | https://cloudedjudgement.substack.com/feed |
| \*\* [Deep Phenotype](https://deepphenotype.substack.com/) | https://deepphenotype.substack.com/feed |
| \*\* [Import AI (Jack Clark)](https://importai.substack.com/) | https://importai.substack.com/feed |
| [TechCrunch](https://techcrunch.com/) | https://techcrunch.com/feed/ |
| [The AI Minute (beehiiv)](https://www.theaiminute.blog) | https://rss.beehiiv.com/feeds/QsjeB9GXym.xml |
| [The Rundown AI](https://www.therundown.ai/) | https://rss.beehiiv.com/feeds/2R3C6Bt5wj.xml |

\*\* Substack refuses GitHub's runner IPs, so the health check cannot verify these
feeds even though they work in a reader. Marked `flaky = true`, so they warn
instead of failing the run.

## Weekly Newsletter via beehiiv

beehiiv's RSS-to-Send turns one feed into a scheduled email issue by *importing*
an outside feed — for example, pointing it at a feed from the table above so
beehiiv drafts and sends an issue whenever that source publishes.

Both of beehiiv's automated-send routes are gated well above the free Launch
plan, so neither is usable here:

| Route | Plan required |
|---|---|
| RSS-to-Send (import a feed, beehiiv drafts and sends) | Max or Enterprise |
| Send API / `POST /posts` (create a post programmatically) | Enterprise only (beta) |

The free Launch plan does include API access, but explicitly *excluding* the
Send API — so a script cannot create or send a post either. What this repo does
instead is the [weekly digest](#weekly-digest-email) below: it assembles the
issue and emails it to you, leaving one paste and one click in beehiiv.

If you are on Max or above:

1. In your beehiiv dashboard, go to **Settings → RSS-to-Send**.
2. Paste the source feed's raw URL (the link in the **File** column above) —
   not `feeds.opml`, which lists every feed for an RSS reader and isn't a
   single feed beehiiv can poll.
3. Customize the email layout, set the schedule to weekly, and check the
   preview.
4. Enable the automation. beehiiv polls the feed on that schedule and sends
   an issue when it finds items published since the last send.

Feeds regenerate every 3 hours via `.github/workflows/generate-feeds.yml`, so
new posts reach beehiiv well within a weekly cycle. Each row above is a
separate feed for one source — to cover several sources in one weekly issue
you'd need a combined feed merging their items, which this repo does not
generate today.

Separately, and free on any plan: every beehiiv publication has its own
outbound RSS feed of what it has already sent (e.g. `rss.beehiiv.com/feeds/...`,
listed as an [external feed](#external-feeds) above for The AI Minute and The
Rundown AI). That feed carries *out* of beehiiv into any RSS reader — it does
not import an outside source *into* beehiiv, so it doesn't substitute for
RSS-to-Send if the goal is auto-sending posts written elsewhere.

### Weekly Digest Email

`build_digest.py` collects the posts a feed published in a recent window and
renders them as plain semantic HTML — headings, dates, links, post bodies, no
styling of its own — so it pastes into a beehiiv (or Substack) editor and picks
up that publication's template.

```bash
uv run --no-project python build_digest.py                    # last 7 days of theaiminute-blog
uv run --no-project python build_digest.py --days 14          # a wider window
uv run --no-project python build_digest.py --feed mistral-news --out mistral.html
```

It writes nothing when no posts fall in the window, so a quiet week produces no
output rather than an empty issue.

The `.github/workflows/weekly-digest.yml` workflow runs this every Monday at
07:00 UTC and emails the result to one address — `ALERT_EMAIL_TO`, the same
repo variable the health check uses. It refreshes the feed first (best effort),
builds the digest, and sends it only if there is something to send, using the
same `MAIL_USERNAME`/`MAIL_PASSWORD` secrets as the other workflows.

The email is the digest itself, with the HTML also attached. To publish: copy
the email body, paste it into a new beehiiv post on your template, and send.

**To test it end to end, only to yourself:** the workflow already sends to that
single address and nothing reaches subscribers, since beehiiv is not in the
loop until you paste. Run it on demand from the repository's **Actions** tab →
**Weekly newsletter digest** → **Run workflow**, setting **days** wide enough to
catch a recent post (e.g. `30`) so the run has something to send. Then, before
publishing in beehiiv, use beehiiv's own **Send test email** on the draft to
check how the pasted content renders in your template.

## Developer Guide

### Generate Feeds

Use the generator script:

```bash
uv run python generate_feeds.py
```

Generated feed files are written to `./feeds`.

By default all feeds are generated, but you can specify which to generate:

```bash
uv run python generate_feeds.py aisi-blog allenai-news
```

Options:

- `--no-cache`: disable Scrapy HTTP cache for that run
- `--skip-unchanged`: skip writing a feed file if its only change would be `lastBuildDate`

The scheduled GitHub Actions workflow uses `--skip-unchanged`, so it does not create a commit when feeds are otherwise unchanged.

### Validation and Failure Behavior

Feed generation is fail-fast.

- If the source URL does not return HTTP 200, that spider raises an error.
- If `item_container_selector` matches nothing, that spider raises an error.
- If too few items are extracted, that spider raises an error.

By default, each spider enforces:

- `min_item_count = 1`
- `min_item_ratio_vs_previous = 0.6` when an existing `feeds/<name>.xml` file is present

This prevents silently writing empty or unexpectedly tiny feeds when page markup changes.
`uv run python generate_feeds.py` exits with a non-zero status if any spider errors.

### Feed Health Monitoring

Generation is fail-fast, but a feed can still go bad silently: sources marked
`broken` or `flaky` only warn, and `--skip-unchanged` means a source that stops
publishing produces no commit and no signal. The health check covers that gap by
testing the *published* feeds.

```bash
uv run --no-project python check_feeds.py            # check published feeds
uv run --no-project python check_feeds.py --local    # check the files in ./feeds
```

`check_feeds.py` uses only the standard library, so `--no-project` skips
installing the scraping dependencies. Feed keys are read from `feeds.toml`.
Each feed fails on one of:

| Failure | Meaning |
|---|---|
| `UNREACHABLE` | connection failed or timed out after retries |
| `HTTP_<code>` | the URL returned a non-200 status. 4xx fails at once; 5xx and 429 are retried first, since those mean "not now" rather than "no" |
| `MALFORMED` | not well-formed XML, not RSS 2.0, or fewer items than the minimum |
| `STALE` | no new item within the age limit (newest `pubDate`, falling back to `lastBuildDate`) |

Feeds marked `broken = true` are skipped unless `--include-broken` is passed.
Feeds marked `flaky = true` are checked, but an error is reported as a warning
and does not fail the run — for sources that refuse the runner while serving
readers normally. Run `uv run --no-project python check_feeds.py --help` for all
options.

The `.github/workflows/feed-health.yml` workflow runs this daily and can also be
triggered manually. On failure it writes a report to the job summary and emails
it via Gmail SMTP.

#### Alert Email Setup

Email alerting is optional. Without the secrets below, the email step skips with
a notice and the workflow still fails, so GitHub's own failure notification
remains the fallback. Both this workflow and `generate-feeds.yml` use the same
secrets and variables.

Repository **secrets**:

| Secret | Value |
|---|---|
| `MAIL_USERNAME` | the sending Gmail address |
| `MAIL_PASSWORD` | a Gmail [App Password](https://support.google.com/accounts/answer/185833) (requires 2-Step Verification), not the account password |

Repository **variables**, all optional:

| Variable | Default | Purpose |
|---|---|---|
| `ALERT_EMAIL_TO` | `guerraz.stephane@gmail.com` | alert recipient(s) |
| `MAIL_SERVER` | `smtp.gmail.com` | SMTP host |
| `MAIL_PORT` | `465` | SMTP port (TLS) |
| `FEED_HEALTH_BASE_URL` | this repo's raw default branch | where the feeds are published |
| `FEED_HEALTH_MAX_AGE_DAYS` | `21` | staleness limit in days |
| `FEED_HEALTH_MIN_ITEMS` | `1` | minimum items per feed |
| `FEED_HEALTH_AGE_OVERRIDES` | none | JSON per-feed age limits, e.g. `{"turing-blog": 90}` |
| `FEED_HEALTH_SKIP` | none | comma-separated feed keys to exclude |

Use `FEED_HEALTH_AGE_OVERRIDES` for sources that genuinely publish rarely, so
their quiet periods do not drown out real breakage. The same thing can be set
per feed in `feeds.toml`, which keeps it in version control next to the feed it
describes:

```toml
[feeds.claude-blog]
max_age_days = 90
```

`FEED_HEALTH_AGE_OVERRIDES` (and `--age-overrides`) still win over the value in
`feeds.toml`, which in turn wins over the global default.

### HTTP Cache

Scrapy HTTP cache is enabled by default in `src/settings.py`.
Use `uv run python generate_feeds.py --no-cache` to disable cache for a single run.

To refresh cached source pages, delete:

```bash
rm -rf .scrapy/httpcache
```

### Add A New Feed

1. Add a new `[feeds.<feed-key>]` table in `feeds.toml`.
2. Set required fields for HTML feeds:
	- `feed_title`
	- `source_url`
	- `item_container_selector`
	- `item_title_selector`
	- `item_link_selector`
3. For Next.js feeds, set:
	- `format = "nextjs"`
	- `item_container_selector` as a jq query that returns item objects (for example `.page.sections[] | select(._type == "publicationList") | .posts[]`)
	- `item_title_selector`, `item_link_selector`, and optional `item_date_selector` / `item_description_selector` as jq queries scoped to each item
3a. For sites whose posts load from a plain JSON API (e.g. a Supabase/PostgREST
    backend) rather than being present in the page HTML, set:
	- `format = "json"`
	- `source_url` as the API endpoint itself (with any query params, e.g. `?select=*&order=published_at.desc`)
	- `request_headers` as an inline TOML table if the API needs an API key or auth header, e.g. `{ apikey = "...", Authorization = "Bearer ..." }`
	- `item_container_selector` as a jq query returning each item (usually `.[]` for a plain JSON array)
	- `item_title_selector`, `item_link_selector`, and optional `item_date_selector` / `item_description_selector` as jq queries scoped to each item — `item_link_selector` can build an absolute URL directly, e.g. `"https://example.com/#post-" + .id`
4. Set optional fields as needed:
	- `item_date_selector`, `item_date_regex`, `item_description_selector`, `feed_description`, `language`
	- `item_guid_is_permalink`, `min_item_count`, `min_item_ratio_vs_previous`
	- save a local source snapshot in `snapshots/` and develop selectors against that copy
	- comments above the feed table to keep source/structure notes alongside selectors
5. Add the new feed entry to the table above, keeping it sorted by name.
6. Run `uv run python generate_feeds.py` and verify output in `feeds/`.
7. Run `uv run python generate_opml.py` to regenerate the OPML.

### Add An External Feed

When a source already publishes its own RSS there is nothing to scrape. Add it
as an external feed instead, so it reaches your reader through the OPML without
this repo generating a duplicate copy:

```toml
[feeds.techcrunch]
feed_title = "TechCrunch"
external_feed_url = "https://techcrunch.com/feed/"
site_url = "https://techcrunch.com/"
```

`external_feed_url` is the RSS URL and `site_url` is the human-readable page
(optional; it defaults to the feed URL). No selectors apply — setting any
scraping field on an external feed is rejected, rather than silently ignored.
External feeds are skipped by `generate_feeds.py` and by
`check_feeds.py --local`, since neither has anything to act on.

Then add it to the External Feeds table above and run
`uv run python generate_opml.py`.
