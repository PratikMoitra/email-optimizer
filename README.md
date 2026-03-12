<![CDATA[# 📧 Email Optimizer

**Autonomous cold email A/B testing, powered by AI.**

An autonomous cold email optimization system inspired by [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) pattern. It runs headless on a GitHub Actions cron — zero human input needed after initial setup. The system continuously evolves email copy through automated A/B experiments, using reply rate as the sole objective metric.

---

## How It Works

Every **4 hours**, the system runs a tight optimization loop:

```
┌──────────────────────────────────────────────────────────────────┐
│                     Email Optimizer Loop                        │
│                                                                  │
│   ┌───────────┐    ┌───────────┐    ┌───────────┐               │
│   │  HARVEST  │───▶│ GENERATE  │───▶│  DEPLOY   │               │
│   │           │    │           │    │           │               │
│   │ Pull 48hr │    │ Claude    │    │ Instantly │               │
│   │ reply     │    │ mutates   │    │ campaigns │               │
│   │ rates     │    │ copy      │    │ go live   │               │
│   └───────────┘    └───────────┘    └───────────┘               │
│         │                                   │                    │
│         ▼                                   ▼                    │
│   Winner promoted                    250 leads/arm              │
│   to baseline                        48hr measurement           │
└──────────────────────────────────────────────────────────────────┘
```

1. **HARVEST** — Queries Instantly API for experiments deployed 48+ hours ago. Compares baseline vs challenger reply rates. If the challenger wins (minimum 1 reply), it gets promoted to the new baseline.

2. **GENERATE** — Reads the current baseline, product context, cold email strategy docs, and experiment history. Calls Claude (`claude-opus-4-6` with extended thinking + web search) to produce a **copy-only mutation** — same lead filters, new subject/body/CTA.

3. **DEPLOY** — Parses baseline and challenger configs, creates two Instantly campaigns, draws 250 leads per arm from the pre-scraped pool, activates both, and records the experiment.

> The baseline **ratchets upward** over time as winning challengers get promoted — this is gradient descent on cold email copy.

---

## Tech Stack

| Component | Technology |
|---|---|
| **AI Engine** | OpenAI GPT-4o with function calling |
| **Email Platform** | [Instantly.ai](https://instantly.ai) via API v2 |
| **Lead Scraping** | [Apify](https://apify.com) (offline pool replenishment) |
| **Lead Storage** | SQLite (`lead_pool.db`) |
| **Notifications** | Slack webhooks |
| **Automation** | GitHub Actions (cron every 4 hours) |
| **Language** | Python 3.12 |

---

## Project Structure

```
email-optimizer/
├── orchestrator.py            # Core 3-phase loop (harvest → generate → deploy)
├── instantly_client.py        # Thin wrapper around Instantly API v2
├── deploy_batch.py            # Bootstrap multiple experiments at once
├── export_campaigns.py        # Archive all campaigns to JSON + CSV
├── purge_old_leads.py         # Free contact slots by exporting & deleting old leads
├── test_parsers.py            # Validate config parsers
├── requirements.txt           # Python dependencies
│
├── config/
│   ├── baseline.md            # Current best email (the file being evolved)
│   └── challenger_preview.md  # Dry-run output before deployment
│
├── data/
│   ├── resource.md            # Product/business context fed to Claude
│   ├── cold-email-course.md   # Cold email strategy docs fed to Claude
│   ├── active_experiments.json # Running experiments tracker
│   ├── lead_pool.db           # Pre-scraped leads (SQLite, not committed)
│   └── contacted.db           # Dedup DB: prevents re-emailing anyone
│
├── results/
│   ├── results.log            # Append-only JSONL experiment history
│   └── experiments/           # Full experiment records (copy + configs + stats)
│
├── .github/workflows/
│   └── optimize.yml           # GitHub Actions cron (every 4 hours)
│
├── .env.example               # Template for required environment variables
└── .gitignore
```

---

## Quick Start

### 1. Clone & Install

```bash
git clone git@github.com:PratikMoitra/email-optimizer.git
cd email-optimizer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Fill in your API keys:

| Variable | Required | Description |
|---|---|---|
| `INSTANTLY_API_KEY` | ✅ | Instantly.ai API v2 bearer token |
| `APIFY_API_TOKEN` | ✅ | Apify API token for lead scraping |
| `OPENAI_API_KEY` | ✅ | OpenAI API key for GPT-4o |
| `WEBHOOK_URL` | ❌ | Slack webhook URL for notifications |

### 3. Set Up Your Baseline

Edit `config/baseline.md` with your initial email copy:

- **Lead Filter** — Job titles, industries, company keywords, size, geography
- **Email Sequence** — Subject line + body (supports `{{firstName}}`, `{{companyName}}` merge tags)
- **Campaign Settings** — Daily limit, email gap, timezone, schedule

### 4. Update Product Context

Edit `data/resource.md` with:
- What product/service you're selling
- Target customer profile
- Core value proposition
- Social proof (revenue, clients, case studies)

### 5. Populate Lead Pool

The system draws leads from a pre-scraped SQLite database. Create `data/lead_pool.db` with schema:

```sql
CREATE TABLE leads (
    email TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    company_name TEXT,
    job_title TEXT,
    industry TEXT,
    city TEXT,
    state TEXT,
    status TEXT DEFAULT 'available',
    experiment_id TEXT
);
```

---

## Usage

```bash
# Run the full 3-phase loop (harvest → generate → deploy)
python orchestrator.py

# Dry-run: generate challenger only, don't deploy
python orchestrator.py --dry-run

# Harvest results only (skip generate/deploy)
python orchestrator.py --harvest-only

# Bootstrap multiple experiments at once
python deploy_batch.py --count 10

# Validate config parsers
python test_parsers.py

# Archive all campaigns to JSON + CSV
python export_campaigns.py

# Free contact slots: export then delete old campaign leads
python purge_old_leads.py
python purge_old_leads.py --dry-run  # preview without deleting
```

---

## GitHub Actions (Autonomous Mode)

The workflow at `.github/workflows/optimize.yml` runs every 4 hours automatically. To enable:

1. Push this repo to GitHub
2. Add repository secrets: `INSTANTLY_API_KEY`, `APIFY_API_TOKEN`, `OPENAI_API_KEY`, `WEBHOOK_URL`
3. Enable GitHub Actions
4. Ensure `lead_pool.db` is available on the runner (use Git LFS or upload as artifact — it's too large for regular git)

The workflow commits results back to the repo after each run:
```
exp 2026-03-12-14: auto-optimize
```

---

## Config Format

The baseline (`config/baseline.md`) is a Markdown file with three sections parsed by regex:

```markdown
## Lead Filter
contact_job_title:
  - "CEO"
  - "Founder"
company_keywords:
  - "saas"

## Email Sequence
### Step 1 (Day 0)
subject: quick question
body: |
  Hey {{firstName}}, ...

## Campaign Settings
daily_limit: 125
email_gap: 10
timezone: America/Chicago
```

**Copy-only mutations**: Lead filters and campaign settings stay constant between baseline and challenger. Only email copy changes, maintaining experimental control.

---

## Safety Rules

- **NEVER delete Instantly campaigns** without explicit confirmation
- **NEVER overwrite** `active_experiments.json`, `results/results.log`, or `contacted.db` — these are irreplaceable experiment data
- **NEVER pause active campaigns** unless there's a validated safety issue
- **Copy-only mutations**: Lead filters and campaign settings are held constant

---

## License

MIT
]]>
