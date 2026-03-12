"""
AI email generator — uses GPT-4o to create personalized 3-sequence × A/B email campaigns.
"""

import json
import logging
from openai import OpenAI

log = logging.getLogger("email_gen")

GENERATION_PROMPT = """You are an expert cold email copywriter. Your emails consistently achieve 5%+ reply rates.

## YOUR TASK
Write a 3-step email sequence with A/B variants for a cold outreach campaign targeting the {industry} industry.

## TARGET AUDIENCE
- Industry: {industry}
- Typical job titles: {job_titles}
- Their company summary: {company_summary}
- Their niche: {niche}
- Their pain points: {pain_points}
- Undeniable offer angle: {undeniable_offer}

## SEQUENCE STRUCTURE
- Step 1 (Day 0): Light intro — reference their niche, hint at how automating their sales pipeline creates impact
- Step 2 (Day 3): Value drop — address their #1 pain point with a specific "what if" scenario showing revenue impact
- Step 3 (Day 7): Soft close — the undeniable offer + discovery call CTA

Each step needs variant A and variant B with different:
- Subject lines (different hooks)
- Opening lines (different personalization angles)
- CTA styles

## RULES (MUST FOLLOW)
- Under 100 words per email body
- Use merge tags: {{{{firstName}}}}, {{{{companyName}}}}, {{{{sendingAccountFirstName}}}}
- CTA = always a discovery session call ("quick 15-min chat", "worth a call?", etc.)
- Angle = automating their sales pipeline → direct revenue impact
- NEVER mention any specific tool names (no "Antigravity", no "AI tool", etc.)
- NO corporate jargon, NO exclamation marks, NO em dashes
- NO "revolutionize", NO "game-changer", NO "unlock"
- Subject lines: lowercase, under 40 chars, personal > clever
- First line must be about THEM, not about you
- Line breaks between every 1-2 sentences (mobile reading)
- No link tracking, no images, plain text only

## COLD EMAIL BEST PRACTICES
{cold_email_rules}

## OUTPUT FORMAT (JSON)
{{
  "sequences": [
    {{
      "step": 1, "day": 0,
      "variant_a": {{ "subject": "...", "body": "..." }},
      "variant_b": {{ "subject": "...", "body": "..." }}
    }},
    {{
      "step": 2, "day": 3,
      "variant_a": {{ "subject": "...", "body": "..." }},
      "variant_b": {{ "subject": "...", "body": "..." }}
    }},
    {{
      "step": 3, "day": 7,
      "variant_a": {{ "subject": "...", "body": "..." }},
      "variant_b": {{ "subject": "...", "body": "..." }}
    }}
  ]
}}"""


def generate_sequences(
    industry: str,
    job_titles: list[str],
    company_summary: str,
    niche: str,
    pain_points: list[str],
    undeniable_offer: str,
    cold_email_rules: str,
    openai_api_key: str,
) -> dict:
    """
    Generate 3-sequence × A/B email copy using GPT-4o.

    Returns: {"sequences": [{step, day, variant_a: {subject, body}, variant_b: {subject, body}}, ...]}
    """
    prompt = GENERATION_PROMPT.format(
        industry=industry or "general",
        job_titles=", ".join(job_titles) if job_titles else "decision makers",
        company_summary=company_summary or "Unknown",
        niche=niche or industry or "general",
        pain_points="\n".join(f"- {p}" for p in pain_points) if pain_points else "- General sales pipeline inefficiency",
        undeniable_offer=undeniable_offer or "Show them how to automate their sales pipeline in 15 minutes",
        cold_email_rules=cold_email_rules or "Keep it short, personal, and focused on their pain.",
    )

    client = OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.8,
        max_tokens=2000,
    )

    result = json.loads(response.choices[0].message.content)
    sequences = result.get("sequences", [])
    log.info("Generated %d email sequences for industry=%s", len(sequences), industry)
    return result


def load_cold_email_rules(rules_path: str = None) -> str:
    """Load cold email rules from the resource file."""
    if rules_path:
        try:
            with open(rules_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            pass
    return ""
