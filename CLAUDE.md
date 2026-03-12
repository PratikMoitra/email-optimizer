# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Email Optimizer — Autonomous Cold Email A/B Testing

An autonomous cold email optimization system inspired by Karpathy's autoresearch pattern. Runs headless on GitHub Actions cron — no human input needed after setup.

**How it works:** Every 4 hours: harvest reply rates from 48hr-old experiments → Claude generates a challenger (mutated copy) → scrape leads via Apify → deploy baseline + challenger on Instantly → commit results → repeat. The baseline ratchets upward over time as winning challengers get promoted.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full 3-phase loop (harvest → generate → deploy)
python orchestrator.py

# Dry-run: generate challenger only, don't deploy (writes to config/challenger_preview.md)
python orchestrator.py --dry-run

# Harvest results only (skip generate/deploy)
python orchestrator.py --harvest-only

# Bootstrap multiple experiments at once
python deploy_batch.py --count N

# Validate config parsers against baseline.md and challenger_preview.md
python test_parsers.py

# Archive all campaigns to JSON + CSV
python export_campaigns.py

# Free contact slots: export then delete old campaign leads
python purge_old_leads.py
```

## Architecture

The system runs a 3-phase loop in `orchestrator.py`:

1. **HARVEST** — Queries Instantly API for campaigns deployed 48+ hours ago. Compares baseline vs challenger reply rates. If challenger wins (and has `MIN_REPLIES_FOR_WINNER = 1` minimum replies), promotes it by overwriting `config/baseline.md`. Logs results to `results/results.log` (append-only JSONL) and `results/experiments/{id}.json`.

2. **GENERATE** — Reads `config/baseline.md`, `data/resource.md`, `data/cold-email-course.md`, and the last 50 entries from `results/results.log`. Samples leads from `lead_pool.db` for niche context. Calls OpenAI GPT-4o (with function calling) to produce a copy-only mutation — same lead filters, new subject/body/CTA.

3. **DEPLOY** — Parses the baseline and challenger configs (extracting email steps as HTML, lead filters as structured dicts, campaign settings). Creates two Instantly campaigns via `instantly_client.py`, draws `LEADS_PER_ARM = 250` leads per arm from `lead_pool.db` (marking them `assigned`), adds leads to campaigns, activates them, and appends to `data/active_experiments.json`.

### Config format (`config/baseline.md`)

The baseline is a Markdown file with three labeled sections parsed by regex in `orchestrator.py`:
- `## Lead Filter` — job titles, industries, company keywords, size ranges, geography
- `## Email Sequence` — one email step with `Subject:` and body (supports `{{first_name}}`, `{{company_name}}` merge tags)
- `## Campaign Settings` — `daily_limit`, `email_gap`, timezone, sending account preferences

### Data files

```
config/baseline.md           — Current best email (the file being evolved)
config/challenger_preview.md — Dry-run output before deployment
data/resource.md             — Product/business context fed to Claude (read-only)
data/cold-email-course.md    — Optional cold email strategy docs fed to Claude
data/active_experiments.json — Running experiments (baseline_id, challenger_id, deploy_time)
data/lead_pool.db            — Pre-scraped leads (SQLite); schema: leads(email, first_name,
                               last_name, company_name, job_title, industry, city, state,
                               status DEFAULT 'available', experiment_id)
data/contacted.db            — Dedup DB: prevents re-emailing anyone across experiments
results/results.log          — Append-only JSONL experiment history
results/experiments/         — Full experiment records (copy + configs + final stats)
```

`lead_pool.db` is not committed to git (too large) — use Git LFS or upload separately to CI.

## First-Time Setup

**When this project is opened for the first time, walk the user through setup before doing anything else.** Ask for the following:

### 1. API Keys
Create a `.env` file from `.env.example` and collect:
- **INSTANTLY_API_KEY** — Instantly.ai API v2 bearer token (required)
- **APIFY_API_TOKEN** — Apify API token for lead scraping (required)
- **OPENAI_API_KEY** — OpenAI API key for GPT-4o challenger generation (required)
- **WEBHOOK_URL** — Slack webhook URL for notifications (optional)

### 2. Product/Service Description
Update `data/resource.md` — the "What We Sell" section. Ask the user:
- What product or service are you selling?
- Who is your target customer? (industry, company size, job titles)
- What's your core offer / value proposition?
- Any social proof? (revenue, clients, case studies)

### 3. Baseline Email Copy
Update `config/baseline.md` — the initial email that gets A/B tested. Ask the user:
- What subject line do you want to start with?
- Write the email body (or describe what you want and generate it for them)
- What lead filters? (job titles, industries, company keywords, company size, location)

### 4. Cold Email Knowledge (optional)
If the user has cold email course notes, playbooks, or strategy docs, paste them into `data/cold-email-course.md`. This gives Claude richer context for generating challengers.

### 5. Lead Pool Database
The system draws leads from a pre-scraped SQLite database at `data/lead_pool.db`. This must be created before running experiments. Help the user:
- Run `deploy_batch.py` to populate the pool, OR
- Create the pool manually with the schema: `leads(email, first_name, last_name, company_name, job_title, industry, city, state, status DEFAULT 'available', experiment_id)`

### 6. GitHub Actions (for autonomous operation)
The workflow at `.github/workflows/optimize.yml` runs every 4 hours. The user needs to:
- Push this repo to GitHub
- Add secrets: `INSTANTLY_API_KEY`, `APIFY_API_TOKEN`, `OPENAI_API_KEY`, `WEBHOOK_URL`
- Enable GitHub Actions
- Ensure `lead_pool.db` is available on the runner (it's too large for git — use LFS or upload separately)

## Safety Rules

- **NEVER delete Instantly campaigns** without explicit user confirmation. The API sometimes returns stale analytics — that doesn't mean campaigns are broken.
- **NEVER overwrite** `active_experiments.json`, `results/results.log`, or `data/contacted.db` — these are irreplaceable experiment data.
- **NEVER pause active campaigns** unless there's a validated safety issue.
- **Copy-only mutations:** Lead filters and campaign settings must stay constant between baseline and challenger — only email copy changes, to maintain experimental control.
