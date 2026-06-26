import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

from agents.base_agent import BaseAgent
from database import DatabaseManager

load_dotenv(override=True)


class DiscoveryAgent(BaseAgent):
    def __init__(self, db: DatabaseManager):
        super().__init__("DiscoveryAgent")
        self.db = db
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def run(self, topic: str):
        self.log(f"Starting discovery for topic: '{topic}'")

        # Step 1: Generate a search query
        self.log("Generating search query...")
        query = self._generate_query(topic)
        self.log(f"Search query: {query}")

        # Step 2: Search the web
        self.log("Searching the web...")
        search_results = self._search(query)
        self.log(f"Got {len(search_results)} search results")

        # Step 3: Extract competitor profiles via LLM
        self.log("Extracting competitor profiles with OpenAI...")
        competitors = self._extract_competitors(topic, search_results)
        self.log(f"Identified {len(competitors)} competitors")

        # Step 4: Insert into DB
        competitor_ids = []
        for company in competitors:
            self.log(f"Saving competitor: {company['name']}")
            self.db.insert_competitor(
                id=company["id"],
                name=company["name"],
                industry=company["industry"],
                description=company["description"],
                website=company["website"],
                founded_year=company.get("founded_year") or 0,
                employee_count=company.get("employee_count") or 0,
                pricing_tier=company.get("pricing_tier", ""),
                key_products=company.get("key_products", []),
                hq_location=company.get("hq_location", ""),
            )
            competitor_ids.append(company["id"])

        # Step 5: Emit event
        self.log(f"Done. Emitting 'competitors_found' with ids: {competitor_ids}")
        self.emit("competitors_found", {"competitor_ids": competitor_ids, "topic": topic})

        return competitor_ids

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _generate_query(self, topic: str) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You generate concise web search queries."},
                {"role": "user", "content": (
                    f"Write a single Google search query to find the top competing companies in this market: '{topic}'. "
                    "Return only the query string, nothing else."
                )},
            ],
        )
        return response.choices[0].message.content.strip().strip('"')

    def _search(self, query: str) -> list[dict]:
        """Search Google News RSS and return a list of {title, summary} dicts."""
        encoded = requests.utils.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            self.log(f"Search failed: {e}")
            return []

        # Parse RSS XML — no external library needed
        results = []
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)
        for item in root.findall(".//item")[:15]:
            title = item.findtext("title", "")
            desc = item.findtext("description", "")
            results.append({"title": title, "summary": desc})

        return results

    def _extract_competitors(self, topic: str, search_results: list[dict]) -> list[dict]:
        """Ask OpenAI to identify the top 5 competitors from the search results."""
        results_text = "\n".join(
            f"- {r['title']}: {r['summary']}" for r in search_results
        )

        prompt = f"""
You are a market research analyst. Based on the topic "{topic}" and these news headlines:

{results_text}

Identify the top 5 companies competing in this space. For each company return a JSON array with these fields:
- id: lowercase slug, e.g. "openai" or "google-deepmind"
- name: full company name
- industry: one-line industry label
- description: 1-2 sentence company description
- website: company website URL
- founded_year: integer or null
- employee_count: approximate integer (round number is fine, e.g. 50000, 1500, 300000). Use your training knowledge. Never return 0 — if truly unknown use null
- pricing_tier: "free", "freemium", "paid", "enterprise", or ""
- key_products: list of up to 3 product names
- hq_location: city and country

Return ONLY a valid JSON array, no markdown, no explanation.
"""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a market research analyst. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        # The model may wrap the array in a key like {"companies": [...]}
        if isinstance(parsed, list):
            return parsed
        for value in parsed.values():
            if isinstance(value, list):
                return value
        return []


# -------------------------------------------------------------------------
# Quick test — python -m agents.discovery_agent
# -------------------------------------------------------------------------
if __name__ == "__main__":
    from database import DatabaseManager

    db = DatabaseManager()
    agent = DiscoveryAgent(db)

    def on_found(data):
        print(f"\nEvent received! competitor_ids: {data['competitor_ids']}")

    agent.on("competitors_found", on_found)
    agent.run("Consumer AI")
    db.close()
