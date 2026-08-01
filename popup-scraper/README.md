# Instagram Pop-up Scraper

Follows artists on Instagram, runs every new post image through a **Claude
vision model** to detect whether the artist is hosting a **pop-up** (and
*where*), and **text-blasts** subscribers when one is found — so subscribers
always know when an artist is popping up.

```
Instagram (instagrapi)  ->  Claude vision  ->  SQLite (dedup + state)  ->  Twilio SMS
   follow + read feeds        is this a          never analyze or           blast every
                              pop-up? where?      blast a post twice          subscriber
```

## ⚠️ Read this first

Instagram has **no supported API** for reading other artists' feeds or
auto-following them. This project drives a personal account through
Instagram's **private API** via [`instagrapi`](https://github.com/subzeroid/instagrapi).
That **violates Instagram's Terms of Service** and can get the account
rate-limited or banned.

- Use a **dedicated / burner account**, not your main one.
- Keep polling **gentle** (the default is every 30 min, a few posts per artist).
- The Instagram layer is deliberately isolated behind the `InstagramSource`
  interface (`popup_scraper/instagram.py`) so you can swap in the official
  Graph API or a manual feed later without touching the rest of the app.

For **SMS compliance**, only text people who opted in, always include a
"Reply STOP to unsubscribe" line (the app does), and honor opt-outs.

## Setup

```bash
cd popup-scraper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # fill in your credentials
cp artists.example.yaml artists.yaml   # list the artist handles to track
```

Fill in `.env`:

| Variable | What it is |
|---|---|
| `IG_USERNAME` / `IG_PASSWORD` | The (burner) Instagram account to log in as |
| `ANTHROPIC_API_KEY` | Claude API key for the vision model |
| `VISION_MODEL` | Vision-capable Claude model (default `claude-sonnet-5`) |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` | Twilio SMS creds + sending number |
| `CONFIDENCE_THRESHOLD` | Min vision confidence (0–1) before a blast goes out (default `0.7`) |
| `NOTIFIER` | `twilio` to send, or `console` for a safe dry run that prints texts |

## Usage

```bash
# 1. Log into Instagram once (caches the session so you don't re-login every run)
python -m popup_scraper.cli login

# 2. Follow every artist listed in artists.yaml
python -m popup_scraper.cli follow

# 3. Manage who gets the text blasts (E.164 format)
python -m popup_scraper.cli subscribers add +15551234567 --name "Ada"
python -m popup_scraper.cli subscribers list
python -m popup_scraper.cli subscribers remove +15551234567

# 4a. Do one poll -> analyze -> blast pass
python -m popup_scraper.cli run

# 4b. …or poll continuously on POLL_INTERVAL_SECONDS
python -m popup_scraper.cli watch
```

**Tip:** set `NOTIFIER=console` in `.env` for your first `run` — it prints the
exact texts it *would* send instead of sending them, so you can tune the
prompt and confidence threshold before spending on SMS.

## How it works

1. **Fetch** — `InstagrapiSource` reads each artist's recent posts. Posts
   already in the SQLite `seen_media` table are skipped, so each post is only
   ever processed once.
2. **Analyze** — `VisionAnalyzer` downloads the post's image(s), sends them
   plus the caption to Claude, and gets back strict JSON:
   `is_popup`, `confidence`, `venue`, `location`, `city`, `starts_at`,
   `ends_at`, `summary`.
3. **Decide** — a post triggers a blast only if `is_popup` **and**
   `confidence >= CONFIDENCE_THRESHOLD`. Every detection is recorded either way.
4. **Blast** — `TwilioNotifier` texts every active subscriber a formatted
   alert (artist, what/where/when, link, STOP line). The `notifications` table
   guarantees one post never blasts twice.

## Architecture

| File | Responsibility |
|---|---|
| `config.py` | Load + validate configuration from `.env` |
| `artists.py` | Parse `artists.yaml` into a list of handles |
| `instagram.py` | `InstagramSource` interface + `InstagrapiSource` (swappable) |
| `vision.py` | `VisionAnalyzer` — Claude pop-up detection + JSON parsing |
| `notifier.py` | `Notifier` interface + `TwilioNotifier` / `ConsoleNotifier` |
| `store.py` | SQLite: dedup, subscribers, detections, sent blasts |
| `pipeline.py` | Orchestration: poll -> analyze -> blast; message composition |
| `cli.py` | Command-line entrypoint |

The two external-service layers (`InstagramSource`, `Notifier`) are abstract
interfaces, so swapping Instagram access strategies or SMS providers is a
one-class change.

## Tests

```bash
pip install pytest
python -m pytest
```

The suite covers dedup/state, subscriber management, vision-response parsing,
message composition, and the full pipeline (with fakes — no network or
credentials needed).

## Running it continuously

`watch` runs in the foreground. To keep it alive on a server, run it under a
process manager (systemd, supervisor, `pm2`, a container restart policy, or a
`cron`-invoked `run`). Because state lives in SQLite, restarts never re-blast
posts that were already handled.
