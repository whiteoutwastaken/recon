import os
import json
import asyncio
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents.base_agent import BaseAgent
from database import DatabaseManager

load_dotenv(override=True)

SEARCH_QUERIES = [
    '"{company}" hiring 2025',
    '"{company}" hiring 2026',
    '"{company}" jobs AI engineer',
    '"{company}" layoffs',
    '"{company}" executive hire',
]


class JobsAgent(BaseAgent):
    def __init__(self, db: DatabaseManager):
        super().__init__("JobsAgent")
        self.db = db
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._semaphore = asyncio.Semaphore(3)

    async def run(self, competitor_id: str, company_name: str):
        self.log(f"Starting hiring signal ingestion for {company_name}")

        # Step 1: Run all search queries in parallel
        self.log("Searching for hiring signals...")
        async def search_with_semaphore(q):
            async with self._semaphore:
                return await asyncio.to_thread(self._search, q.format(company=company_name))

        search_tasks = [search_with_semaphore(q) for q in SEARCH_QUERIES]
        results_per_query = await asyncio.gather(*search_tasks)

        # Flatten and deduplicate by title
        seen = set()
        all_articles = []
        for articles in results_per_query:
            for a in articles:
                if a["title"] not in seen:
                    seen.add(a["title"])
                    all_articles.append(a)

        self.log(f"Collected {len(all_articles)} unique articles")

        # Step 2: Single batch GPT call
        self.log("Analyzing hiring signals with OpenAI...")
        analysis = await self._analyze(all_articles, company_name)

        if not analysis:
            self.log("Analysis failed, skipping")
            return

        # Step 3: Store monthly metrics
        self.log("Storing monthly metrics...")
        monthly = analysis.get("estimated_monthly_hiring", {})
        months_sorted = sorted(monthly.keys())  # e.g. ["2025-04", "2025-05", ...]

        prev_postings = None
        for month_str in months_sorted:
            job_postings = int(monthly[month_str])
            # hiring_velocity = ratio vs previous month (1.0 = no change, 2.0 = doubled)
            if prev_postings and prev_postings > 0:
                hiring_velocity = round(job_postings / prev_postings, 2)
            else:
                hiring_velocity = 1.0
            prev_postings = job_postings

            self.db.insert_metrics(
                competitor_id=competitor_id,
                metric_month=month_str,
                hiring_velocity=hiring_velocity,
                news_volume=0,
                sentiment_avg=0.0,
                pricing_changes=0,
                job_postings=job_postings,
            )
            self.log(f"  {month_str}: {job_postings} postings, velocity {hiring_velocity}x")

        # Step 4: Store surge events
        surges = analysis.get("surges", [])
        for surge_month in surges:
            self.log(f"Surge detected in {surge_month} — storing event")
            self.db.insert_event(
                competitor_id=competitor_id,
                event_type="hiring_surge",
                title=f"{company_name} hiring surge detected in {surge_month}",
                summary=(
                    f"{company_name} showed a significant spike in hiring activity during {surge_month}, "
                    f"with job postings doubling compared to the previous month. "
                    f"Department focus: {json.dumps(analysis.get('department_breakdown', {}))}."
                ),
                sentiment=0.3,
                importance_score=0.9,
                event_date=datetime.now(timezone.utc),
                department="",
            )

        # Notable executive hires as events
        for hire in analysis.get("notable_hires", []):
            self.log(f"Notable hire: {hire}")
            self.db.insert_event(
                competitor_id=competitor_id,
                event_type="leadership_change",
                title=hire,
                summary=f"{company_name} made a notable executive hire: {hire}",
                sentiment=0.4,
                importance_score=0.7,
                event_date=datetime.now(timezone.utc),
                department="",
            )

        self.log(f"Done. {len(months_sorted)} months stored, {len(surges)} surges, {len(analysis.get('notable_hires', []))} notable hires")
        self.emit("data_updated", {"competitor_id": competitor_id})

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _search(self, query: str) -> list[dict]:
        encoded = requests.utils.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            self.log(f"  Search failed ({query}): {e}")
            return []

        results = []
        root = ET.fromstring(resp.text)
        for item in root.findall(".//item")[:8]:
            results.append({
                "title": item.findtext("title", ""),
                "summary": item.findtext("description", ""),
            })
        return results

    async def _analyze(self, articles: list[dict], company_name: str) -> dict | None:
        articles_text = "\n\n".join(
            f"Article {i+1}: {a['title']}\n{a['summary']}"
            for i, a in enumerate(articles)
        )

        # Build the list of past 12 months for context
        now = datetime.now(timezone.utc)
        months = [(now - relativedelta(months=i)).strftime("%Y-%m") for i in range(11, -1, -1)]
        months_list = ", ".join(months)

        prompt = f"""You are a hiring analyst. Based on these news articles about {company_name}:

{articles_text}

Estimate hiring activity and return a JSON object with these fields:

- estimated_monthly_hiring: object where keys are months ({months_list}) and values are estimated job posting counts (integers). Use the articles as signals — if layoffs are mentioned, use lower numbers. If rapid expansion is mentioned, use higher numbers. Make reasonable estimates based on company size and signals.
- department_breakdown: object with keys Engineering, ML_AI, Sales, Marketing, Product, Operations and integer values representing estimated headcount added over the full period
- notable_hires: list of strings describing any specific executive or key hires mentioned (empty list if none)
- surges: list of month strings (YYYY-MM format) where hiring appears to have roughly doubled vs the previous month (empty list if none)

Return only valid JSON."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a hiring analyst. Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            self.log(f"Analysis failed: {e}")
            return None


# -------------------------------------------------------------------------
# Run for all competitors — python -m agents.ingestion.jobs_agent
# -------------------------------------------------------------------------
async def main():
    db = DatabaseManager()
    agent = JobsAgent(db)

    competitors = db.get_all_competitors()
    print(f"Found {len(competitors)} competitors")

    # Run all companies in parallel
    tasks = [agent.run(c["id"], c["name"]) for c in competitors]
    await asyncio.gather(*tasks)

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
