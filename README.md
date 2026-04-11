# Blog Update Tracker

A Python tool that monitors AI/ML blogs and websites for new content, then sends email notifications. Runs for free on GitHub Actions.

## Tracked Sources

### RSS/Atom Feeds
| Source | Feed URL |
|--------|----------|
| Sebastian Raschka - Ahead of AI | sebastianraschka.substack.com/feed |
| Maarten Grootendorst | newsletter.maartengrootendorst.com/feed |
| Jay Alammar - Substack | jayalammar.substack.com/feed |
| Ahmad Osman | ahmadosman.substack.com/feed |
| Ai2 Blog (Medium) | medium.com/feed/ai2-blog |
| Towards Data Science | towardsdatascience.com/feed |
| Andrej Karpathy - Substack | karpathy.substack.com/feed |
| Andrej Karpathy - GitHub | github.com/karpathy.atom |

### HTML Scraped
| Source | URL |
|--------|-----|
| Chris Olah | colah.github.io |
| Sebastian Raschka - Blog | sebastianraschka.com/blog |
| Andrej Karpathy - Blog | karpathy.ai/blog |
| Lilian Weng - Lil'Log | lilianweng.github.io/posts/ |
| Jay Alammar - Blog | jalammar.github.io |
| Ai2 - Allen Institute | allenai.org/blog |
| nn.labml.ai | nn.labml.ai |
| LessWrong | lesswrong.com |
| Transformer Circuits | transformer-circuits.pub |
| NVIDIA Newsroom | nvidianews.nvidia.com |
| LunarTech | lunartech.ai/blog/ |
| Anthropic Research | anthropic.com/research |
| Anthropic News | anthropic.com/news |

## How It Works

1. Every 6 hours, GitHub Actions runs `main.py`
2. Each site is checked via its RSS feed or by scraping its HTML
3. New post URLs are compared against `data/state.json` (the stored baseline)
4. If new posts are found, an email is sent with titles and links
5. The updated state is committed back to the repository

On the **first run**, all existing posts are stored as a baseline without sending notifications.

## Setup

### 1. Create a GitHub Repository

Push this project to a **public** GitHub repository (public repos get unlimited free Actions minutes).

### 2. Configure Gmail App Password

1. Enable **2-Step Verification** on your Google Account at [myaccount.google.com/security](https://myaccount.google.com/security)
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Generate an app password (select "Mail" as the app)
4. Copy the 16-character password

### 3. Add GitHub Secrets

Go to your repo's **Settings > Secrets and variables > Actions** and add:

| Secret Name | Value |
|-------------|-------|
| `EMAIL_ADDRESS` | Your Gmail address (e.g. `you@gmail.com`) |
| `EMAIL_PASSWORD` | The 16-character app password from step 2 |
| `NOTIFY_EMAIL` | Email address to receive notifications (can be the same as `EMAIL_ADDRESS`) |

### 4. Enable GitHub Actions

The workflow runs automatically on the cron schedule. You can also trigger it manually from the **Actions** tab using the "Run workflow" button.

## Running Locally

```bash
cd blog-tracker
pip install -r requirements.txt

# Without email (prints to console):
python main.py

# With email:
EMAIL_ADDRESS="you@gmail.com" EMAIL_PASSWORD="your-app-password" NOTIFY_EMAIL="you@gmail.com" python main.py
```

## Adding a New Site

Edit `config/sites.json` and add an entry:

**For RSS/Atom feeds:**
```json
{
  "id": "unique_id",
  "name": "Display Name",
  "type": "rss",
  "url": "https://example.com/feed",
  "enabled": true
}
```

**For HTML-scraped sites:**
```json
{
  "id": "unique_id",
  "name": "Display Name",
  "type": "scrape",
  "url": "https://example.com/blog",
  "selector": "a[href*='/blog/']",
  "base_url": "https://example.com",
  "enabled": true
}
```

The `selector` field is a CSS selector that matches article links on the page. Use your browser's DevTools to find the right selector.

## Disabling a Site

Set `"enabled": false` in its entry in `config/sites.json`. The site will be skipped during checks.

## Project Structure

```
blog-tracker/
  config/
    sites.json            # Site definitions
  src/
    __init__.py
    checker.py            # Orchestrates all site checks
    rss_checker.py        # RSS/Atom feed parser
    scrape_checker.py     # HTML scraper
    notifier.py           # Email sender
    storage.py            # JSON state persistence
  data/
    state.json            # Known posts (auto-updated)
  main.py                 # Entry point
  requirements.txt
  .github/workflows/
    check.yml             # GitHub Actions cron workflow
```
