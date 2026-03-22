import os
import json
from openai import OpenAI
from database import get_db

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


class TwinAgent:
    def __init__(self, competitor_id: str):
        self.competitor_id = competitor_id
        self.company_name = self._get_company_name()

    def _get_company_name(self) -> str:
        conn = get_db()
        row = conn.execute("SELECT name FROM competitors WHERE id = ?", (self.competitor_id,)).fetchone()
        conn.close()
        return row["name"] if row else self.competitor_id

    def query(self, question: str) -> dict:
        data = self._load_all_data()
        context = self._format_context(data)
        return self._ask_gpt(question, context)

    def _load_all_data(self) -> dict:
        conn = get_db()
        profile = conn.execute("SELECT * FROM competitors WHERE id = ?", (self.competitor_id,)).fetchone()
        events = conn.execute(
            "SELECT * FROM events WHERE competitor_id = ? ORDER BY date DESC LIMIT 40",
            (self.competitor_id,),
        ).fetchall()
        metrics = conn.execute(
            "SELECT * FROM metrics WHERE competitor_id = ? ORDER BY date ASC",
            (self.competitor_id,),
        ).fetchall()
        patterns = conn.execute(
            "SELECT * FROM patterns WHERE competitors_involved LIKE ? ORDER BY confidence DESC LIMIT 10",
            (f"%{self.competitor_id}%",),
        ).fetchall()
        conn.close()
        return {
            "profile": dict(profile) if profile else {},
            "events": [dict(e) for e in events],
            "metrics": [dict(m) for m in metrics],
            "patterns": [dict(p) for p in patterns],
        }

    def _format_context(self, data: dict) -> str:
        lines = []
        lines.append("=== COMPANY PROFILE ===")
        for k, v in data["profile"].items():
            if v is not None:
                lines.append(f"{k}: {v}")

        lines.append("\n=== RECENT EVENTS ===")
        if data["events"]:
            for e in data["events"]:
                lines.append(
                    f"[{e.get('date','')}] [{e.get('event_type','').upper()}] {e.get('title','')}"
                    + (f" — {e.get('description','')}" if e.get("description") else "")
                )
        else:
            lines.append("No events recorded yet.")

        lines.append("\n=== METRICS ===")
        if data["metrics"]:
            grouped: dict[str, list] = {}
            for m in data["metrics"]:
                grouped.setdefault(m["metric_name"], []).append(f"{m['date']}:{m['value']}")
            for name, vals in grouped.items():
                lines.append(f"{name}: {', '.join(vals[-6:])}")
        else:
            lines.append("No metrics recorded yet.")

        lines.append("\n=== PATTERNS ===")
        if data["patterns"]:
            for p in data["patterns"]:
                lines.append(f"- {p.get('description','')} ({p.get('confidence',0):.0%}) → {p.get('prediction','')}")
        else:
            lines.append("No patterns detected yet.")

        return "\n".join(lines)

    def _ask_gpt(self, question: str, context: str) -> dict:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1024,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a competitive intelligence analyst specializing in {self.company_name}.
Here is everything we know about them:

{context}

Answer questions using specific data points. Be concise and data-driven.
Always respond with a JSON object with exactly these keys:
- answer: string (2-5 sentences, cite specific events or metrics)
- confidence: float 0-1 (how confident given available data)
- cited_events: list of strings (event titles you referenced)
- follow_up_questions: list of exactly 3 suggested follow-up questions""",
                },
                {"role": "user", "content": question},
            ],
        )

        text = response.choices[0].message.content.strip()
        try:
            result = json.loads(text)
            result.setdefault("answer", text)
            result.setdefault("confidence", 0.5)
            result.setdefault("cited_events", [])
            result.setdefault("follow_up_questions", [])
            return result
        except json.JSONDecodeError:
            return {"answer": text, "confidence": 0.5, "cited_events": [], "follow_up_questions": []}