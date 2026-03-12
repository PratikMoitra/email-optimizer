---
version: 1
last_updated: 2026-01-01
experiment_id: exp-2026-01-01
---

# Baseline Configuration

## Lead Filter
contact_location:
  - "united states"
contact_job_title:
  - "CEO"
  - "Founder"
  - "Owner"
company_keywords:
  - "your-keyword-here"
company_industry:
  - "your-industry-here"
company_not_industry:
  - "government administration"
company_not_keywords:
  - "news"
  - "hospital"
  - "university"
size:
  - "1-10"
  - "11-20"
  - "21-50"
email_status:
  - "validated"
fetch_count: 250

## Email Sequence

### Step 1 (Day 0)
subject: quick question
body: |
  Hey {{firstName}},

  [Your opening line — reference something about THEM, not you.]

  [Your offer — what you do, social proof, why they should care. Keep under 100 words.]

  [Your CTA — specific time, low commitment. e.g. "How's a 15-min call Thursday at 3pm?"]

  Thanks,
  - {{sendingAccountFirstName}}

## Campaign Settings
daily_limit: 125
email_gap: 10
timezone: America/Chicago
schedule_start: "09:00"
schedule_end: "17:00"
