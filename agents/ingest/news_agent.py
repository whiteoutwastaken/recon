import os
import re
import json
import asyncio
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents.base_agent import BaseAgent
from database import DatabaseManager

load_dotenv(override=True)

# 4 focused topic searches run in parallel — replaces the old 12-month sequential loop.
# Each maps to a Google News RSS query; results are deduplicated by URL before analysis.
_SEARCH_TOPICS = [
    '"{company}"',
    '"{company}" product OR launch OR announcement',
    '"{company}" hiring OR layoffs OR leadership',
    '"{company}" funding OR acquisition OR partnership OR pricing',
]

# Max articles kept per topic search (before dedup)
_ARTICLES_PER_TOPIC = 8


class NewsAgent(BaseAgent):
    def __init__(self, db: DatabaseManager):
        super().__init__("NewsAgent")
        self.db = db
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def run(self, competitor_id: str, company_name: str, full_scrape: bool = True):
        self.log(f"Starting news ingest for {company_name} ({len(_SEARCH_TOPICS)} parallel topic searches)")

        # ── Phase 1: all topic searches in parallel ──────────────────────────
        search_tasks = [
            asyncio.to_thread(self._search, company_name, topic)
            for topic in _SEARCH_TOPICS
        ]
        topic_results = await asyncio.gather(*search_tasks)

        # Flatten and deduplicate by URL
        seen_urls: set[str] = set()
        articles: list[dict] = []
        for batch in topic_results:
            for a in batch:
                if a["url"] and a["url"] not in seen_urls:
                    seen_urls.add(a["url"])
                    articles.append(a)

        self.log(f"Collected {len(articles)} unique articles across all topics")

        if not articles:
            self.log("No articles found")
            self.emit("data_updated", {"competitor_id": competitor_id})
            return 0

        # ── Phase 2: fetch article text in parallel (5 s timeout) ────────────
        self.log("Fetching article text in parallel...")
        fetch_tasks = [asyncio.to_thread(self._fetch_article, a["url"]) for a in articles]
        fetched = await asyncio.gather(*fetch_tasks)
        for article, (real_url, full_text) in zip(articles, fetched):
            if real_url:
                article["url"] = real_url
            article["full_text"] = full_text

        # ── Phase 3: single GPT batch call for all articles ──────────────────
        self.log(f"Analyzing {len(articles)} articles with GPT...")
        events = await self._analyze_batch(articles, company_name)

        # ── Phase 4: store results ────────────────────────────────────────────
        now = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        stored = 0
        for article, event in zip(articles, events):
            if event is None or event.get("importance_score", 0) < 0.4:
                continue
            self.db.insert_event(
                competitor_id=competitor_id,
                event_type=event["event_type"],
                title=event["title"],
                summary=event["summary"],
                sentiment=event["sentiment"],
                importance_score=event["importance_score"],
                source_url=article.get("url", ""),
                event_date=now,
                raw_data={"headline": article["title"], "full_text": article.get("full_text", "")},
            )
            stored += 1

        self.log(f"Done. {stored} events stored for {company_name}")
        self.emit("data_updated", {"competitor_id": competitor_id})
        return stored

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _search(self, company_name: str, topic_template: str) -> list[dict]:
        query = topic_template.format(company=company_name)
        encoded = requests.utils.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
        except Exception as e:
            self.log(f"Search failed for topic '{topic_template}': {e}")
            return []

        results = []
        root = ET.fromstring(resp.text)
        for item in root.findall(".//item")[:_ARTICLES_PER_TOPIC]:
            results.append({
                "title": item.findtext("title", ""),
                "summary": item.findtext("description", ""),
                "url": item.findtext("link", ""),
            })
        return results

    def _fetch_article(self, url: str) -> tuple[str, str]:
        try:
            resp = requests.get(url, timeout=5, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            real_url = resp.url
            text = re.sub(r"<[^>]+>", " ", resp.text)
            text = re.sub(r"\s+", " ", text).strip()
            return real_url, text[:4000]
        except Exception:
            return "", ""

    async def _analyze_batch(self, articles: list[dict], company_name: str) -> list[dict | None]:
        articles_text = "\n\n".join(
            f"Article {i+1}:\nTitle: {a['title']}\nText: {a.get('full_text') or a['summary']}"
            for i, a in enumerate(articles)
        )

        prompt = f"""Analyze these {len(articles)} news articles about {company_name}.

{articles_text}

Return a JSON object with key "articles" containing an array of exactly {len(articles)} objects (one per article, in the same order).
Each object must have:
- event_type: one of "product_launch", "funding", "partnership", "pricing_change", "controversy", "leadership_change", "acquisition", "expansion", "hiring_surge", "other"
- title: clean 1-line title (max 100 chars)
- summary: 2-3 sentence summary of what happened and why it matters competitively
- sentiment: float from -1.0 (very negative) to 1.0 (very positive)
- importance_score: float from 0.0 to 1.0 (competitive significance)
- relevant: true if genuinely about {company_name}, false if just a passing mention"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a competitive intelligence analyst. Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            results = data.get("articles", [])
            while len(results) < len(articles):
                results.append(None)
            return [r if r and r.get("relevant", True) else None for r in results]
        except Exception as e:
            self.log(f"Batch analysis failed: {e}")
            return [None] * len(articles)


# ─────────────────────────────────────────────────────────────────────────────
# Run directly:  python ingest/news_agent.py [competitor_id]
#                python ingest/news_agent.py              ← runs all competitors
# ─────────────────────────────────────────────────────────────────────────────
async def main(target_id: str | None = None):
    db = DatabaseManager()
    agent = NewsAgent(db)

    if target_id:
        comp = db.get_competitor(target_id)
        if not comp:
            print(f"Competitor '{target_id}' not found in database.")
            db.close()
            return
        competitors = [comp]
    else:
        competitors = db.get_all_competitors()

    print(f"Running news ingest for {len(competitors)} competitor(s)")

    for c in competitors:
        print(f"\n{'='*50}\n{c['name']} ({c['id']})")
        total = await agent.run(c["id"], c["name"])
        print(f"  → {total} events stored")

    db.close()


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(target))
