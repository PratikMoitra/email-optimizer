"""
orchestrator.py — Autonomous cold email A/B optimization loop.

Runs every 4 hours via GitHub Actions cron. Each run:
  1. HARVEST  — collect results from experiments deployed 48+ hours ago
  2. GENERATE — Claude generates a challenger (copy-only mutation, no filter changes)
  3. DEPLOY   — create campaigns, draw leads from pool DB, activate

Lead sourcing: pre-scraped lead pool in data/lead_pool.db (SQLite).
  - Leads are scraped in bulk offline (not during orchestrator runs).
  - Each deploy draws 250 fresh leads per arm, marks them as 'assigned'.
  - No Apify calls during orchestrator runs — zero scraping failures.
  - Pool must be replenished manually when running low.

Usage:
  python orchestrator.py                # full run
  python orchestrator.py --dry-run      # generate challenger, don't deploy
  python orchestrator.py --harvest-only # just pull results, don't generate or deploy
"""

import os
import sys
import json
import random
import logging
import argparse
import re
import sqlite3
from datetime import datetime, date, timezone
from pathlib import Path

import requests as _requests
from openai import OpenAI
from dotenv import load_dotenv

import instantly_client as ic

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("orchestrator")

ROOT = Path(__file__).parent
ACTIVE_EXPERIMENTS_FILE = ROOT / "data" / "active_experiments.json"
BASELINE_FILE = ROOT / "config" / "baseline.md"
RESULTS_LOG = ROOT / "results" / "results.log"
RESOURCE_FILE = ROOT / "data" / "resource.md"
COLD_EMAIL_COURSE = ROOT / "data" / "cold-email-course.md"

MIN_REPLIES_FOR_WINNER = 1
LEADS_PER_ARM = 250
HARVEST_WINDOW_HOURS = 48
LEAD_POOL_DB = ROOT / "data" / "lead_pool.db"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")


# ─────────────────────────────────────────────
# SLACK NOTIFICATIONS
# ─────────────────────────────────────────────

def _slack_notify(text: str, blocks: list = None):
    """Send a Slack notification via webhook. Fails silently."""
    if not WEBHOOK_URL:
        return
    payload = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    try:
        r = _requests.post(WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code not in (200, 204):
            log.warning("Slack webhook %d: %s", r.status_code, r.text[:200])
    except Exception as e:
        log.warning("Slack webhook failed: %s", e)


def _fmt_date():
    """Format today as 'March 10, 2026'."""
    return datetime.now(timezone.utc).strftime("%B %-d, %Y")


def _extract_challenger_summary(challenger_config: str) -> str:
    """Pull subject line and hypothesis snippet from challenger config."""
    # Extract subject
    subject = ""
    for line in challenger_config.split("\n"):
        if line.strip().startswith("subject:"):
            subject = line.split(":", 1)[1].strip().strip('"').strip("'")
            break

    # Extract what changed vs baseline
    changes = []
    if subject:
        changes.append(f"Subject: `{subject}`")

    # Detect filter changes by looking for keywords not in baseline
    baseline_text = (ROOT / "config" / "baseline.md").read_text() if (ROOT / "config" / "baseline.md").exists() else ""
    for line in challenger_config.split("\n"):
        stripped = line.strip().strip("-").strip().strip('"')
        if stripped and stripped not in baseline_text and any(
            field in challenger_config.split(line)[0].split("\n")[-5:]
            for field in ["contact_job_title", "company_keywords"]
        ):
            # Too noisy — skip individual filter diffs
            pass

    # Count filter additions
    b_titles = [l.strip().strip('-" ') for l in baseline_text.split("\n") if l.strip().startswith('- "') and baseline_text.split(l)[0].count("contact_job_title") > 0]
    c_titles = [l.strip().strip('-" ') for l in challenger_config.split("\n") if l.strip().startswith('- "') and challenger_config.split(l)[0].count("contact_job_title") > 0]
    new_titles = [t for t in c_titles if t and t not in baseline_text]
    if new_titles:
        changes.append(f"+{len(new_titles)} titles ({', '.join(new_titles[:3])})")

    new_kw = []
    in_kw = False
    for line in challenger_config.split("\n"):
        if "company_keywords:" in line:
            in_kw = True
            continue
        if in_kw and line.strip().startswith("- "):
            kw = line.strip().strip('-" ').strip()
            if kw and kw not in baseline_text:
                new_kw.append(kw)
        elif in_kw and not line.strip().startswith("- "):
            in_kw = False
    if new_kw:
        changes.append(f"+{len(new_kw)} keywords ({', '.join(new_kw[:3])})")

    return " | ".join(changes) if changes else "Minor copy variation"


def slack_run_summary(harvest_results: list = None, deploy_info: dict = None):
    """Single combined notification for a full cron run (harvest + deploy)."""
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{_fmt_date()}*"}},
        {"type": "divider"},
    ]

    # Harvest section
    if harvest_results:
        best = max(harvest_results, key=lambda r: max(
            r.get("baseline", {}).get("rate", 0),
            r.get("challenger", {}).get("rate", 0),
        ))
        best_rate = max(best.get("baseline", {}).get("rate", 0), best.get("challenger", {}).get("rate", 0))
        winners = sum(1 for r in harvest_results if r.get("winner") not in ("pending", None))

        lines = [f"*Harvest* ({len(harvest_results)} experiments, {winners} decided, best *{best_rate:.1%}*)\n"]
        for i, r in enumerate(harvest_results, 1):
            eid = r.get("experiment_id", "?")
            winner = r.get("winner", "pending")
            b = r.get("baseline", {})
            c = r.get("challenger", {})
            b_rate = f'{b.get("rate", 0):.1%}' if b.get("sent") else "-"
            c_rate = f'{c.get("rate", 0):.1%}' if c.get("sent") else "-"
            lines.append(
                f"{i}. `{eid}` — B {b.get('replies', 0)}/{b.get('sent', 0)} ({b_rate}) "
                f"vs C {c.get('replies', 0)}/{c.get('sent', 0)} ({c_rate}) — *{winner}*"
            )
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})
    else:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Harvest* — no mature experiments"}})

    # Deploy section
    if deploy_info:
        summary = _extract_challenger_summary(deploy_info.get("challenger_config", ""))
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text":
            f"*Deployed* — {summary}\n\n"
            f"1. Baseline `{deploy_info['baseline_id'][:8]}` — {deploy_info['b_leads']} leads\n"
            f"2. Challenger `{deploy_info['challenger_id'][:8]}` — {deploy_info['c_leads']} leads"}})

    _slack_notify("Email Optimizer run complete", blocks)


def slack_error(phase: str, error: str):
    """Notify on error."""
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{_fmt_date()}*"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text":
            f"*Error* — {phase}\n```{error[:500]}```"}},
    ]
    _slack_notify(f"Error in {phase}", blocks)


# ─────────────────────────────────────────────
# STATE MANAGEMENT
# ─────────────────────────────────────────────

def load_active_experiments() -> list:
    if not ACTIVE_EXPERIMENTS_FILE.exists():
        return []
    return json.loads(ACTIVE_EXPERIMENTS_FILE.read_text())


def save_active_experiments(experiments: list):
    ACTIVE_EXPERIMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_EXPERIMENTS_FILE.write_text(json.dumps(experiments, indent=2))


# ─────────────────────────────────────────────
# LEAD POOL DATABASE
# ─────────────────────────────────────────────

def _get_pool_db():
    """Get SQLite connection to lead pool."""
    if not LEAD_POOL_DB.exists():
        raise RuntimeError(
            f"Lead pool DB not found at {LEAD_POOL_DB}. "
            f"The pool DB is too large for git — it must be present on the runner. "
            f"Run deploy_batch.py locally or upload the DB to the runner."
        )
    conn = sqlite3.connect(str(LEAD_POOL_DB))
    return conn


def pool_stats() -> dict:
    """Return lead pool statistics."""
    conn = _get_pool_db()
    total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    available = conn.execute("SELECT COUNT(*) FROM leads WHERE status = 'available'").fetchone()[0]
    assigned = conn.execute("SELECT COUNT(*) FROM leads WHERE status = 'assigned'").fetchone()[0]
    conn.close()
    return {"total": total, "available": available, "assigned": assigned}


def pool_sample(n: int = 10) -> list:
    """Return a random sample of available leads for Claude to see the niche."""
    conn = _get_pool_db()
    rows = conn.execute(
        "SELECT industry, job_title, company_name, city, state FROM leads "
        "WHERE status = 'available' ORDER BY RANDOM() LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    return [{"industry": r[0], "job_title": r[1], "company": r[2], "city": r[3], "state": r[4]} for r in rows]


def pool_industry_breakdown() -> list:
    """Return top industries in the available pool."""
    conn = _get_pool_db()
    rows = conn.execute(
        "SELECT industry, COUNT(*) as c FROM leads WHERE status = 'available' "
        "GROUP BY industry ORDER BY c DESC LIMIT 15"
    ).fetchall()
    conn.close()
    return rows


def draw_leads(experiment_id: str, count: int) -> list:
    """Draw `count` available leads from the pool, mark as assigned.

    Returns list of lead dicts ready for Instantly upload.
    Raises RuntimeError if not enough leads available.
    """
    conn = _get_pool_db()
    available = conn.execute("SELECT COUNT(*) FROM leads WHERE status = 'available'").fetchone()[0]
    if available < count:
        conn.close()
        raise RuntimeError(
            f"Lead pool exhausted: need {count}, only {available} available. "
            f"Replenish the pool before running more experiments."
        )

    rows = conn.execute(
        "SELECT email, first_name, last_name, company_name FROM leads "
        "WHERE status = 'available' ORDER BY RANDOM() LIMIT ?", (count,)
    ).fetchall()

    leads = []
    for r in rows:
        email = r[0]
        leads.append({
            "email": email,
            "first_name": r[1] or "",
            "last_name": r[2] or "",
            "company_name": r[3] or "",
        })
        conn.execute(
            "UPDATE leads SET status = 'assigned', experiment_id = ? WHERE email = ?",
            (experiment_id, email)
        )

    conn.commit()
    conn.close()
    log.info("Drew %d leads from pool for %s (%d remaining)", len(leads), experiment_id, available - len(leads))
    return leads


# ─────────────────────────────────────────────
# PARSING HELPERS
# ─────────────────────────────────────────────

def parse_lead_filter(config_md: str) -> dict:
    """Extract lead filter fields from baseline.md content."""
    LIST_FIELDS = {
        "contact_location", "contact_job_title", "company_keywords",
        "company_industry", "company_not_industry", "company_not_keywords",
        "size", "email_status",
    }
    SCALAR_FIELDS = {"fetch_count"}

    result = {f: [] for f in LIST_FIELDS}
    result.update({f: None for f in SCALAR_FIELDS})

    lines = config_md.split("\n")
    in_filter = False
    current_list = None

    for line in lines:
        stripped = line.strip()
        if stripped == "## Lead Filter":
            in_filter = True
            continue
        if stripped.startswith("## ") and in_filter:
            break

        if in_filter:
            key_match = stripped.rstrip(":").strip()
            if stripped.endswith(":") and key_match in LIST_FIELDS:
                current_list = key_match
            elif stripped.endswith(":") and key_match in SCALAR_FIELDS:
                current_list = None
            elif ":" in stripped and not stripped.startswith("-"):
                key, val = stripped.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"')
                if key in SCALAR_FIELDS and val:
                    result[key] = int(val) if val.isdigit() else val
                    current_list = None
                elif key in LIST_FIELDS and not val:
                    current_list = key
                elif key in LIST_FIELDS and val:
                    result[key] = [val]
                    current_list = None
            elif stripped.startswith("- ") and current_list:
                result[current_list].append(stripped[2:].strip().strip('"'))
            elif stripped == "":
                pass
            elif not stripped.startswith("-"):
                current_list = None

    return result


def parse_email_steps(config_md: str) -> list:
    """Parse email steps from config into Instantly sequence format."""
    steps = []
    step_pattern = r'### Step \d+ \(Day (\d+)\)\s*\n'
    parts = re.split(step_pattern, config_md)

    for i in range(1, len(parts), 2):
        delay = int(parts[i])
        content = parts[i + 1] if i + 1 < len(parts) else ""

        subject = ""
        body_lines = []
        in_body = False

        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("subject:"):
                subject = stripped.split(":", 1)[1].strip()
                continue
            if stripped == "body: |":
                in_body = True
                continue
            if stripped.startswith("## ") or stripped.startswith("### "):
                break
            if in_body:
                body_lines.append(line.rstrip())

        body_text = "\n".join(body_lines).strip()
        dedented = []
        for bl in body_text.split("\n"):
            dedented.append(bl[2:] if bl.startswith("  ") else bl)
        body_text = "\n".join(dedented).strip()

        paragraphs = body_text.split("\n\n")
        html_parts = []
        for p in paragraphs:
            p = p.replace("\n", "<br>")
            if p.strip():
                html_parts.append(f"<p>{p}</p>")
        html_body = "".join(html_parts)

        steps.append({
            "type": "email",
            "delay": delay,
            "variants": [{"subject": subject, "body": html_body}],
        })

    return steps


def parse_campaign_settings(config_md: str) -> dict:
    """Extract campaign settings from config."""
    settings = {
        "daily_limit": 125,
        "email_gap": 10,
        "timezone": "America/Chicago",
        "schedule_start": "09:00",
        "schedule_end": "17:00",
    }
    in_settings = False
    for line in config_md.split("\n"):
        stripped = line.strip()
        if stripped == "## Campaign Settings":
            in_settings = True
            continue
        if stripped.startswith("## ") and in_settings:
            break
        if in_settings and ":" in stripped:
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"')
            if key == "daily_limit":
                settings["daily_limit"] = int(val)
            elif key == "email_gap":
                settings["email_gap"] = int(val)
            elif key == "timezone":
                settings["timezone"] = val
            elif key == "schedule_start":
                settings["schedule_start"] = val
            elif key == "schedule_end":
                settings["schedule_end"] = val
    return settings


# ─────────────────────────────────────────────
# PHASE 1: HARVEST
# ─────────────────────────────────────────────

def harvest_single(exp: dict) -> dict:
    """Harvest a single experiment. Returns log entry dict."""
    baseline_id = exp["baseline_campaign_id"]
    challenger_id = exp["challenger_campaign_id"]
    challenger_config = exp.get("challenger_config", "")
    experiment_id = exp.get("experiment_id", "unknown")

    log.info("Harvesting experiment %s", experiment_id)

    b_analytics = ic.get_analytics(baseline_id)
    c_analytics = ic.get_analytics(challenger_id)

    b_sent = b_analytics.get("emails_sent_count", 0)
    c_sent = c_analytics.get("emails_sent_count", 0)
    b_replies = b_analytics.get("reply_count", 0)
    c_replies = c_analytics.get("reply_count", 0)

    b_rate = b_replies / b_sent if b_sent > 0 else 0
    c_rate = c_replies / c_sent if c_sent > 0 else 0

    if b_replies < MIN_REPLIES_FOR_WINNER and c_replies < MIN_REPLIES_FOR_WINNER:
        winner = "baseline"
        reason = f"insufficient data (baseline={b_replies}, challenger={c_replies} replies)"
        log.warning("Insufficient replies — keeping baseline.")
    elif c_rate > b_rate:
        winner = "challenger"
        reason = f"challenger won ({c_rate:.2%} vs {b_rate:.2%})"
    else:
        winner = "baseline"
        reason = f"baseline held ({b_rate:.2%} vs {c_rate:.2%})"

    # Extract lead filters for logging
    baseline_config_text = BASELINE_FILE.read_text()
    baseline_filter = parse_lead_filter(baseline_config_text)
    challenger_filter = parse_lead_filter(challenger_config) if challenger_config else {}
    lead_fields = ["contact_job_title", "company_keywords", "company_industry", "size"]

    # Summary for results.log (compact — no full copy, just rates + metadata)
    log_entry = {
        "date": str(date.today()),
        "experiment_id": experiment_id,
        "baseline": {"sent": b_sent, "replies": b_replies, "rate": round(b_rate, 4)},
        "challenger": {"sent": c_sent, "replies": c_replies, "rate": round(c_rate, 4)},
        "winner": winner,
        "reason": reason,
        "baseline_filter": {f: baseline_filter.get(f) for f in lead_fields},
        "challenger_filter": {f: challenger_filter.get(f) for f in lead_fields},
    }
    with open(RESULTS_LOG, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Full experiment record (includes complete copy + configs) for on-demand lookup
    experiments_dir = ROOT / "results" / "experiments"
    experiments_dir.mkdir(parents=True, exist_ok=True)
    full_record = {
        **log_entry,
        "baseline_config": baseline_config_text,
        "challenger_config": challenger_config,
    }
    (experiments_dir / f"{experiment_id}.json").write_text(
        json.dumps(full_record, indent=2, default=str)
    )

    log.info("Result: %s | %s", winner, reason)

    # Promote challenger if it won
    if winner == "challenger" and challenger_config:
        BASELINE_FILE.write_text(challenger_config)
        log.info("Challenger promoted to baseline.")

    # Clean up: pause, delete leads (free contact slots), then delete campaigns
    for cid in [baseline_id, challenger_id]:
        try:
            ic.pause_campaign(cid)
        except Exception:
            pass
        try:
            ic.delete_leads_from_campaign(cid)
        except Exception:
            pass
        try:
            ic.delete_campaign(cid)
        except Exception:
            pass
    log.info("Cleaned up campaigns for %s.", experiment_id)

    return log_entry


def phase_harvest():
    """
    Harvest all experiments that are >= HARVEST_WINDOW_HOURS old.
    Returns (harvested_count, summary_text).
    """
    experiments = load_active_experiments()
    if not experiments:
        log.info("No active experiments — first run.")
        return 0, "First run — no prior results.", []

    now = datetime.now(timezone.utc)
    mature = []
    still_active = []

    for exp in experiments:
        deploy_time = datetime.fromisoformat(exp["deploy_time"])
        age_hours = (now - deploy_time).total_seconds() / 3600
        if age_hours >= HARVEST_WINDOW_HOURS:
            mature.append(exp)
        else:
            still_active.append(exp)

    if not mature:
        log.info("No experiments ready for harvest (%d active, need %dh).",
                 len(experiments), HARVEST_WINDOW_HOURS)
        save_active_experiments(still_active)
        return 0, f"No mature experiments ({len(still_active)} still active).", []

    log.info("Harvesting %d mature experiments (%d still active).", len(mature), len(still_active))

    summaries = []
    # Process oldest first so promotions stack correctly
    mature.sort(key=lambda e: e["deploy_time"])
    for exp in mature:
        entry = harvest_single(exp)
        # Save state after each harvest so a mid-loop crash doesn't re-harvest
        still_active = [e for e in load_active_experiments()
                        if e["experiment_id"] != exp["experiment_id"]]
        save_active_experiments(still_active)

        b = entry["baseline"]
        c = entry["challenger"]
        summaries.append(entry)

    combined = "\n".join(
        f"{e['experiment_id']}: {e['reason']}. "
        f"B: {e['baseline']['sent']}sent/{e['baseline']['replies']}replies({e['baseline']['rate']:.2%}) "
        f"C: {e['challenger']['sent']}sent/{e['challenger']['replies']}replies({e['challenger']['rate']:.2%})"
        for e in summaries
    )
    return len(mature), combined, summaries


# ─────────────────────────────────────────────
# PHASE 2: GENERATE
# ─────────────────────────────────────────────

def phase_generate(last_summary: str):
    """
    Call Claude to generate a challenger config (copy-only mutation).
    Returns challenger_config string. Leads are drawn from pool in phase_deploy.
    """
    baseline_config = BASELINE_FILE.read_text()
    resource_context = RESOURCE_FILE.read_text()
    cold_email_course = COLD_EMAIL_COURSE.read_text() if COLD_EMAIL_COURSE.exists() else ""
    recent_history = ""
    if RESULTS_LOG.exists():
        lines = RESULTS_LOG.read_text().strip().split("\n")
        recent_history = "\n".join(lines[-50:])  # last 50 experiments

    has_history = bool(recent_history)

    # Gather pool context for Claude
    try:
        stats = pool_stats()
        pool_stats_str = f"{stats['available']} available, {stats['assigned']} assigned, {stats['total']} total"
        industries = pool_industry_breakdown()
        pool_industries_str = "\n".join(f"- {ind}: {cnt} leads" for ind, cnt in industries)
        samples = pool_sample(15)
        pool_sample_str = "\n".join(
            f"- {s['job_title']} at {s['company']} ({s['industry']}, {s['city']}, {s['state']})"
            for s in samples
        )
    except Exception as e:
        log.warning("Could not load pool context: %s", e)
        pool_stats_str = "(pool not available)"
        pool_industries_str = "(unknown)"
        pool_sample_str = "(unknown)"

    client = OpenAI()

    # Exploration vs exploitation strategy
    if has_history:
        experimentation_guidance = """You have experiment history. SHIFT TO EXPLOITATION:
- Study the history carefully. What patterns emerge? What's working?
- Make targeted improvements based on data, not guesses.
- If you see a clear winning direction (e.g., casual tone wins, specific CTAs win),
  double down on that direction with refinements.
- You CAN still make bold changes if the data suggests a fundamentally different approach,
  but ground your decisions in the results you've seen.
- Hone in on local maxima before exploring new regions of the search space."""
    else:
        experimentation_guidance = """No history yet — this is the first experiment. MAXIMIZE EXPLORATION:
- Go bold: completely rewrite the copy, try a radically different angle.
- Change the audience if you have a strong hypothesis from the provided context.
- Make BIG swings. The system is designed for aggressive iteration — failed experiments
  cost nothing. Playing it safe wastes the first experiment.
- Study the cold email course and product context deeply to find angles others miss."""

    prompt = f"""You are an autonomous cold email optimization agent in an autoresearch loop.

## HOW THIS SYSTEM WORKS (read carefully)

This system is inspired by Karpathy's autoresearch pattern. The core idea: an AI agent
runs experiments autonomously in a tight loop, using an objective metric as the sole
feedback signal. No human judges quality — the number goes up or it doesn't.

Architecture (three files, two roles):
- baseline.md = the single file being mutated (like train.py in autoresearch)
- resource.md + cold email course = strategy context (like program.md in autoresearch)
- results.log = append-only experiment history (like results.tsv in autoresearch)

The loop runs every 4 hours:
1. HARVEST: pull reply rates from experiments deployed 48+ hours ago
2. GENERATE: you (this prompt) produce a challenger variant of baseline.md
3. DEPLOY: both baseline and challenger go live with fresh leads, same volume
4. MEASURE: positive reply rate is the objective metric (lower = worse, higher = better)
5. PROMOTE OR REVERT: if challenger wins, it becomes the new baseline. If not, discarded.

At steady state, ~12 experiments run simultaneously (6/day × 2-day measurement window).
Each experiment: {LEADS_PER_ARM} leads per arm, single email step, 48hr measurement.

Volume math: each campaign gets {LEADS_PER_ARM} leads and sends at daily_limit=125/day.
Over the 48hr window, all {LEADS_PER_ARM} leads are contacted (125/day × 2 days = 250).
Total emails per experiment: 500 (250 baseline + 250 challenger).
After 48 hours we harvest reply rates and compare baseline vs challenger.

Your role: you are the mutation engine. You receive the current baseline, the experiment
history, and deep context on cold email strategy. You output a single challenger config
that tests a specific hypothesis. You have full freedom to make sweeping changes.

Key principles:
- ONE OBJECTIVE METRIC: positive reply rate. Not open rate, not click rate, not "sounds
  better." Reply rate is the only thing that matters. Everything else is noise.
- SINGLE FILE MUTATION: you only modify baseline.md. The deployment infrastructure,
  sending accounts, deliverability setup — all held constant. This isolates your changes.
- MONOTONIC IMPROVEMENT: each experiment either improves the baseline or gets discarded.
  Over time, the baseline ratchets upward. You are gradient descent on cold email copy.
- BOLD EXPERIMENTATION: you have full freedom to change multiple things at once — subject
  line, body copy, audience filters, tone, CTA, everything. Make BIG swings. The system
  is designed for aggressive iteration. If an experiment fails, it's discarded and costs
  nothing. If it wins, you've found a major improvement. Playing it safe is the real risk.
- THE HUMAN WRITES STRATEGY, YOU WRITE IMPLEMENTATION: the cold email course and resource
  file are your "program.md" — they define the search space and constraints. Your job is
  to explore within that space intelligently based on the data.

## EXPLORATION vs EXPLOITATION

{experimentation_guidance}

## COLD EMAIL COURSE (internalize these principles — they define your search space)

{cold_email_course}

## CURRENT BASELINE (the file you are mutating)

{baseline_config}

## PRODUCT & BUSINESS CONTEXT

{resource_context}

## EXPERIMENT HISTORY (what's been tried — learn from this)

The table below shows summary stats for each experiment. To see the FULL email copy
(subject + body) and complete configs, use the read_experiment tool with the experiment_id.
You are strongly encouraged to read the top performers and recent experiments before writing
your challenger. Understanding what specific copy won or lost is critical to making progress.

{recent_history if recent_history else "(No history yet)"}

## RECENT HARVEST RESULTS

{last_summary}

## LEAD POOL NICHE CONTEXT

Leads are drawn from a pre-scraped pool database. You do NOT control lead filters — the pool
is fixed. Here is context about the leads you'll be sending to, so you can tailor your copy:

**Pool stats:** {pool_stats_str}

**Industry breakdown (top industries in pool):**
{pool_industries_str}

**Sample leads (random selection from pool):**
{pool_sample_str}

Use this context to write copy that resonates with these specific people and industries.
Do NOT try to change lead filters — they are locked. Focus entirely on copy optimization.

## MUTATION INSTRUCTIONS

1. RESEARCH FIRST: study the cold email course, product context, lead pool data, and experiment
   history. What are the target audience's pain points? What language resonates? Use this context deeply.

2. Study the experiment history. Identify patterns: what improved reply rate? What didn't?
   If there's no history, use your research to make a strong, differentiated challenger.

3. Form a hypothesis. State it: "I believe changing X will improve reply rate because Y."
   You can change multiple things at once — subject, body, audience, all of it. Examples:
   - "The subject line is too generic AND the body is too long. Complete rewrite needed."
   - "We're targeting the wrong segment. Consultants reply more than agencies."
   - "The tone is too formal. Ultra-casual with a specific pain point will hit harder."

4. Apply the cold email course principles:
   - Keep emails under 100 words. 75 is better. Every character is an enemy.
   - Use "I" not "we." Sound like a person, not a company.
   - Personalization: short, informal, passes the "would a real person send this?" test.
   - No rhetorical questions except the CTA. No corporate jargon. No fake urgency.
   - NEVER use em dashes (—). Use hyphens (-) or commas instead. Em dashes are an AI tell.
   - CTA must be specific: "How's 3:30pm tomorrow?" not "Would you be interested?"
   - The offer should be too-good-to-be-true with full risk reversal on you.
   - Follow the four-part formula: Personalization → Who Am I → Offer → CTA.
   - Subject lines: under 4 words, lowercase, curiosity-driven. "quick question" is fine.

5. What you MAY change (any combination — go big):
   - Subject lines (different hook, different format)
   - Opening line / personalization angle
   - Body copy (different offer framing, different social proof, different CTA)
   - Tone and voice (casual vs professional, first person vs third)
   - Complete rewrites are encouraged if you have a strong thesis

6. What you MUST NOT change (held constant for experimental control):
   - The ## Lead Filter section (copy VERBATIM from baseline — leads come from a pre-scraped pool)
   - daily_limit, email_gap, schedule times, timezone
   - Number of steps (1 — single email, no follow-ups)
   - email_status, fetch_count
   - link_tracking, open_tracking settings
   - The ## Campaign Settings section (copy verbatim from baseline)

7. Increment the version number. Set experiment_id to exp-YYYY-MM-DD-HH (current UTC hour).

8. Preserve merge tags exactly: {{{{firstName}}}}, {{{{companyName}}}}, {{{{sendingAccountFirstName}}}}

## OUTPUT FORMAT (critical — malformed output will crash the system)

Output ONLY the complete config file. No explanation, no markdown fences, no commentary.

The file MUST follow this structure exactly:
- YAML front matter with version, last_updated, experiment_id
- "# Challenger Configuration" header
- "## Lead Filter" section using ONLY these field names (no aliases, no renaming):
  contact_location, contact_job_title, company_keywords, company_industry,
  company_not_industry, company_not_keywords, size, email_status, fetch_count
- Each list field uses "- " bullet items on separate lines under the field name
- Scalar fields (fetch_count) use inline values: "fetch_count: 250"
- "## Email Sequence" section with exactly ONE step: "### Step 1 (Day 0)"
- The step has "subject:" and "body: |" fields
- "## Campaign Settings" section copied VERBATIM from the baseline (never modify)
- Do NOT add fields not present in the baseline. Do NOT rename any field names."""

    # Tool: let Claude read full experiment records on demand
    read_experiment_tool = {
        "type": "function",
        "function": {
            "name": "read_experiment",
            "description": (
                "Read the full record of a past experiment, including complete email copy "
                "(subject + body) and configs for both baseline and challenger. "
                "Use this to study what copy was tested and learn from winners/losers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "experiment_id": {
                        "type": "string",
                        "description": "The experiment ID, e.g. 'exp-2026-03-10-14'"
                    }
                },
                "required": ["experiment_id"]
            }
        }
    }

    tools = [read_experiment_tool]

    log.info("Calling OpenAI to generate challenger (with experiment lookup)...")
    messages = [{"role": "user", "content": prompt}]

    # Tool-use loop: keep going until the model produces a final text response
    max_tool_rounds = 30
    response = None
    for tool_round in range(max_tool_rounds):
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=16384,
            tools=tools,
            messages=messages,
        )

        choice = response.choices[0]
        message = choice.message

        # Check if the model wants to call tools
        if not message.tool_calls:
            break  # No tool calls — model is done

        # Process tool calls
        messages.append(message)
        for tc in message.tool_calls:
            args = json.loads(tc.function.arguments)
            exp_id = args.get("experiment_id", "")
            exp_file = ROOT / "results" / "experiments" / f"{exp_id}.json"
            if exp_file.exists():
                result_text = exp_file.read_text()
                log.info("Model requested experiment %s — found.", exp_id)
            else:
                result_text = json.dumps({"error": f"Experiment {exp_id} not found."})
                log.info("Model requested experiment %s — not found.", exp_id)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_text,
            })

    # Extract text from response
    challenger_config = response.choices[0].message.content
    if not challenger_config:
        raise RuntimeError("OpenAI returned no text content in response")
    challenger_config = challenger_config.strip()
    log.info("OpenAI response: %d tool rounds, finish_reason=%s",
             tool_round + 1, response.choices[0].finish_reason)

    # Validate challenger has email steps
    challenger_steps = parse_email_steps(challenger_config)
    if len(challenger_steps) == 0:
        raise RuntimeError("Challenger generated 0 email steps — aborting")

    log.info("Challenger generated successfully (%d email steps).", len(challenger_steps))
    return challenger_config


# ─────────────────────────────────────────────
# PHASE 3: DEPLOY
# ─────────────────────────────────────────────

def phase_deploy(challenger_config: str):
    """
    Create two campaigns, draw leads from pool, add leads, activate.
    Append to active experiments list for future harvesting.
    """
    now = datetime.now(timezone.utc)
    experiment_id = f"exp-{now.strftime('%Y-%m-%d-%H%M')}"

    baseline_config_text = BASELINE_FILE.read_text()
    baseline_steps = parse_email_steps(baseline_config_text)
    challenger_steps = parse_email_steps(challenger_config)
    settings = parse_campaign_settings(baseline_config_text)

    schedule = {
        "name": "AllDays",
        "days": {"0": True, "1": True, "2": True, "3": True, "4": True, "5": True, "6": True},
        "timing": {"from": settings["schedule_start"], "to": settings["schedule_end"]},
        "timezone": settings["timezone"],
    }

    log.info("Creating baseline campaign...")
    b_campaign = ic.create_campaign(
        name=f"B {experiment_id.replace('exp-2026-', '')}",
        sequences=[{"steps": baseline_steps}],
        schedule=schedule,
        daily_limit=settings["daily_limit"],
        email_gap=settings["email_gap"],
    )
    baseline_id = b_campaign["id"]
    log.info("Baseline campaign created: %s", baseline_id)

    log.info("Creating challenger campaign...")
    c_campaign = ic.create_campaign(
        name=f"C {experiment_id.replace('exp-2026-', '')}",
        sequences=[{"steps": challenger_steps}],
        schedule=schedule,
        daily_limit=settings["daily_limit"],
        email_gap=settings["email_gap"],
    )
    challenger_id = c_campaign["id"]
    log.info("Challenger campaign created: %s", challenger_id)

    # Draw leads from pool
    log.info("Drawing %d leads per arm from pool...", LEADS_PER_ARM)
    baseline_leads = draw_leads(f"{experiment_id}-baseline", LEADS_PER_ARM)
    challenger_leads = draw_leads(f"{experiment_id}-challenger", LEADS_PER_ARM)

    log.info("Adding leads to campaigns...")
    b_added = ic.add_leads(baseline_id, baseline_leads)
    c_added = ic.add_leads(challenger_id, challenger_leads)

    # Verify upload counts — at least 80% must succeed
    min_leads = int(LEADS_PER_ARM * 0.8)
    for label, added in [("Baseline", b_added), ("Challenger", c_added)]:
        if added < min_leads:
            log.warning("%s upload low: only %d/%d leads (min %d).",
                        label, added, LEADS_PER_ARM, min_leads)
    log.info("Lead upload verified: baseline=%d, challenger=%d", b_added, c_added)

    log.info("Activating campaigns...")
    ic.activate_campaign(baseline_id)
    ic.activate_campaign(challenger_id)

    # Verify activation
    import time as _time
    _time.sleep(2)  # brief settle
    for label, campaign_id in [("Baseline", baseline_id), ("Challenger", challenger_id)]:
        cdata = ic.get_campaign(campaign_id)
        status = cdata.get("status")
        if status != 1:
            log.error("%s campaign %s not active (status=%s). Pausing both.", label, campaign_id, status)
            ic.pause_campaign(baseline_id)
            ic.pause_campaign(challenger_id)
            raise RuntimeError(f"{label} campaign failed to activate (status={status}). Deploy aborted.")

    # Append to active experiments
    experiments = load_active_experiments()
    experiments.append({
        "experiment_id": experiment_id,
        "deploy_time": now.isoformat(),
        "baseline_campaign_id": baseline_id,
        "challenger_campaign_id": challenger_id,
        "challenger_config": challenger_config,
        "baseline_leads_count": b_added,
        "challenger_leads_count": c_added,
    })
    save_active_experiments(experiments)
    log.info("Experiment %s deployed. %d total active experiments.",
             experiment_id, len(experiments))
    return baseline_id, challenger_id, b_added, c_added, challenger_config


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cold email A/B optimization loop")
    parser.add_argument("--dry-run", action="store_true", help="Generate challenger but don't deploy")
    parser.add_argument("--harvest-only", action="store_true", help="Only pull results, don't generate or deploy")
    args = parser.parse_args()

    try:
        log.info("=" * 60)
        log.info("PHASE 1: HARVEST")
        log.info("=" * 60)
        harvested_count, summary, harvest_summaries = phase_harvest()
        log.info("Harvested %d experiments. Summary: %s", harvested_count, summary)

        if args.harvest_only:
            log.info("Harvest-only mode — stopping.")
            slack_run_summary(harvest_results=harvest_summaries or None)
            return

        log.info("=" * 60)
        log.info("PHASE 2: GENERATE")
        log.info("=" * 60)
        challenger_config = phase_generate(summary)

        if args.dry_run:
            log.info("Dry run — not deploying.")
            log.info("Challenger config preview:\n%s", challenger_config[:500])
            (ROOT / "config" / "challenger_preview.md").write_text(challenger_config)
            log.info("Challenger written to config/challenger_preview.md")
            return

        log.info("=" * 60)
        log.info("PHASE 3: DEPLOY")
        log.info("=" * 60)
        log.info("Pool stats: %s", pool_stats())
        baseline_id, challenger_id, b_added, c_added, challenger_config = phase_deploy(
            challenger_config
        )

        log.info("=" * 60)
        log.info("DONE — Campaigns live: baseline=%s, challenger=%s", baseline_id, challenger_id)
        log.info("=" * 60)

        # Single combined Slack notification
        slack_run_summary(
            harvest_results=harvest_summaries or None,
            deploy_info={
                "baseline_id": baseline_id,
                "challenger_id": challenger_id,
                "b_leads": b_added,
                "c_leads": c_added,
                "challenger_config": challenger_config,
            },
        )

    except Exception as e:
        log.exception("Fatal error in orchestrator")
        slack_error("orchestrator", str(e))
        raise


if __name__ == "__main__":
    main()
