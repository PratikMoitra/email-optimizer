"""
Company researcher — scrapes company website and uses GPT-4o to extract
business context, niche, and sales pain points for email personalization.
"""

import logging
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

log = logging.getLogger("researcher")

RESEARCH_PROMPT = """You are researching {company_name} ({domain}) in the {industry} industry.
Their decision maker is {first_name} {last_name}, {job_title}.

Based on the company website content below, extract the following as JSON:

{{
  "company_summary": "What this company does in 1-2 sentences",
  "niche": "Their specific market niche",
  "sales_pain_points": [
    "Pain point 1 in their sales pipeline that automation could solve",
    "Pain point 2 that directly impacts their revenue",
    "Pain point 3 around lead conversion or follow-up"
  ],
  "undeniable_offer": "A specific, compelling reason for a 15-min discovery call that addresses their #1 pain point. Make it impossible to say no."
}}

Focus on pain points that:
- Are specific to their industry and niche
- Relate to their sales pipeline, lead generation, or revenue growth
- Could be solved with automation (but do NOT mention any specific tools)
- Would resonate with a {job_title}

Website content:
{website_content}

If the website content is empty or unhelpful, use your knowledge of the {industry} industry to infer likely pain points for a company like {company_name}."""


def scrape_website(domain: str, timeout: int = 15) -> str:
    """Fetch and extract text from a company's homepage."""
    urls_to_try = [f"https://www.{domain}", f"https://{domain}", f"http://{domain}"]

    for url in urls_to_try:
        try:
            r = requests.get(url, timeout=timeout, headers={
                "User-Agent": "Mozilla/5.0 (compatible; EmailOptimizer/1.0)"
            })
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")

                # Remove scripts, styles, nav, footer
                for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                    tag.decompose()

                text = soup.get_text(separator="\n", strip=True)
                # Truncate to ~3000 chars to stay within token limits
                return text[:3000]
        except requests.RequestException:
            continue

    log.warning("Could not scrape website for domain: %s", domain)
    return ""


def research_company(
    domain: str,
    company_name: str,
    industry: str,
    first_name: str,
    last_name: str,
    job_title: str,
    openai_api_key: str,
) -> dict:
    """
    Scrape company website and use GPT-4o to extract business context.

    Returns:
        {
            "company_summary": str,
            "niche": str,
            "sales_pain_points": [str, str, str],
            "undeniable_offer": str
        }
    """
    website_content = scrape_website(domain)

    prompt = RESEARCH_PROMPT.format(
        company_name=company_name,
        domain=domain,
        industry=industry or "general",
        first_name=first_name or "the decision maker",
        last_name=last_name or "",
        job_title=job_title or "executive",
        website_content=website_content or "(No website content available)",
    )

    client = OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_tokens=500,
    )

    import json
    result = json.loads(response.choices[0].message.content)
    log.info("Researched %s: niche=%s", company_name, result.get("niche", "unknown"))
    return result
