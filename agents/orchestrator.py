import os
import json
from openai import OpenAI
from database import get_db

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def run_orchestrator(query: str) -> dict:
    conn = get_db()
    competitors = conn.execute("SELECT id, name FROM competitors").fetchall()
    conn.close()

    # Match query to a specific competitor
    competitor_id = None
    for c in competitors:
        if c["name"].lower() in query.lower() or c["id"].lower() in query.lower():
            competitor_id = c["id"]
            break

    # Use TwinAgent if we matched a competitor
    if competitor_id:
        try:
            from agents.twin_agent import TwinAgent
            twin = TwinAgent(competitor_id)
            result = twin.query(query)
            return {
                "answer": result.get("answer", ""),
                "data_points": result.get("cited_events", []),
                "suggested_followups": result.get("follow_up_questions", []),
            }
        except Exception as e:
            return {"answer": f"Error querying twin agent: {e}", "data_points": [], "suggested_followups": []}

    # General query — pull all data and ask GPT
    conn = get_db()
    all_events = conn.execute(
        """SELECT e.title, e.date, e.event_type, c.name as company
           FROM events e JOIN competitors c ON e.competitor_id = c.id
           ORDER BY e.date DESC LIMIT 30"""
    ).fetchall()
    all_patterns = conn.execute(
        "SELECT description, prediction FROM patterns ORDER BY confidence DESC LIMIT 5"
    ).fetchall()
    conn.close()

    context = "RECENT EVENTS:\n" + "\n".join(
        [f"[{e['company']}] [{e['date']}] {e['title']}" for e in all_events]
    )
    context += "\n\nDETECTED PATTERNS:\n" + "\n".join(
        [f"- {p['description']} → {p['prediction']}" for p in all_patterns]
    ) or "None yet."

    comp_names = ", ".join([c["name"] for c in competitors]) or "No competitors seeded yet."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        messages=[
            {
                "role": "system",
                "content": f"""You are Recon, a senior competitive intelligence analyst.
You are tracking these competitors: {comp_names}.
Here is the latest data:

{context}

Answer the user's question using specific data points. Be concise and confident.
End your response with 3 suggested follow-up questions on separate lines starting with '•'.""",
            },
            {"role": "user", "content": query},
        ],
    )

    full_answer = response.choices[0].message.content.strip()
    lines = full_answer.split("\n")
    followups = [l.lstrip("•").strip() for l in lines if l.strip().startswith("•")]
    answer = "\n".join([l for l in lines if not l.strip().startswith("•")]).strip()

    return {
        "answer": answer,
        "data_points": [],
        "suggested_followups": followups[:3],
    }


def run_pattern_detection() -> list:
    try:
        from agents.pattern_detection import run_pattern_detection as _run
        return _run()
    except ImportError:
        return []