import json
import os
import uuid
from datetime import datetime
import anthropic
from database import get_db

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ── Statistical heuristics ────────────────────────────────────────────────────

def _detect_hiring_surge(conn, competitor_id: str) -> list[dict]:
    """Flag if ML/AI hiring velocity > 2x in last 3 months."""
    candidates = []
    rows = conn.execute(
        """SELECT date, value FROM metrics 
           WHERE competitor_id = ? AND metric_name = 'hiring_velocity'
           ORDER BY date DESC LIMIT 6""",
        (competitor_id,),
    ).fetchall()
    if len(rows) >= 2:
        recent = rows[0]["value"]
        older = rows[-1]["value"]
        if older > 0 and recent / older >= 2.0:
            candidates.append({
                "type": "hiring_surge_before_launch",
                "competitor_id": competitor_id,
                "detail": f"Hiring velocity increased {recent/older:.1f}x over 6 months ({older} → {recent})",
                "recent_value": recent,
                "old_value": older,
            })
    return candidates


def _detect_pricing_war(conn) -> list[dict]:
    """Flag if 2+ competitors had pricing_change events within 30 days."""
    candidates = []
    rows = conn.execute(
        """SELECT competitor_id, date FROM events 
           WHERE event_type = 'pricing_change'
           ORDER BY date DESC LIMIT 20"""
    ).fetchall()
    if len(rows) >= 2:
        from datetime import datetime, timedelta
        dates = [(r["competitor_id"], datetime.fromisoformat(r["date"])) for r in rows]
        for i in range(len(dates)):
            for j in range(i + 1, len(dates)):
                cid_a, date_a = dates[i]
                cid_b, date_b = dates[j]
                if cid_a != cid_b and abs((date_a - date_b).days) <= 30:
                    candidates.append({
                        "type": "pricing_war",
                        "competitors_involved": [cid_a, cid_b],
                        "detail": f"{cid_a} and {cid_b} both changed pricing within 30 days",
                    })
    return candidates


def _detect_patent_cluster(conn, competitor_id: str) -> list[dict]:
    """Flag if a competitor filed 3+ patents in 90 days."""
    candidates = []
    rows = conn.execute(
        """SELECT date FROM events 
           WHERE competitor_id = ? AND event_type = 'patent'
           ORDER BY date DESC LIMIT 10""",
        (competitor_id,),
    ).fetchall()
    if len(rows) >= 3:
        from datetime import datetime, timedelta
        dates = [datetime.fromisoformat(r["date"]) for r in rows]
        window = timedelta(days=90)
        for i in range(len(dates) - 2):
            if (dates[i] - dates[i + 2]).days <= 90:
                candidates.append({
                    "type": "patent_cluster_pivot",
                    "competitor_id": competitor_id,
                    "detail": f"{len(rows)} patents filed in 90-day window — possible product pivot",
                })
                break
    return candidates


# ── LLM confirmation ──────────────────────────────────────────────────────────

def _confirm_pattern_with_llm(candidate: dict, supporting_events: list) -> dict | None:
    prompt = f"""Here is a potential competitive pattern we detected:

Pattern type: {candidate['type']}
Detail: {candidate.get('detail', '')}

Supporting events:
{json.dumps(supporting_events, indent=2)}

Analyze this pattern:
1. Is this a real strategic signal or noise? (yes/no + reasoning)
2. What historical precedent exists for this pattern in the tech industry?
3. What is your confidence level (0.0–1.0)?
4. What prediction would you make based on this pattern?

Respond in JSON with keys: confirmed (bool), historical_precedent (str), confidence (float), prediction (str), description (str)"""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    # Strip markdown fences if present
    text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        result = json.loads(text)
        if result.get("confirmed"):
            return result
    except Exception:
        pass
    return None


# ── Main detection runner ─────────────────────────────────────────────────────

def run_pattern_detection() -> list[dict]:
    conn = get_db()
    competitor_ids = [
        r["id"] for r in conn.execute("SELECT id FROM competitors").fetchall()
    ]

    all_candidates = []

    for cid in competitor_ids:
        all_candidates.extend(_detect_hiring_surge(conn, cid))
        all_candidates.extend(_detect_patent_cluster(conn, cid))

    all_candidates.extend(_detect_pricing_war(conn))

    new_patterns = []
    for candidate in all_candidates:
        # Fetch supporting events
        cid = candidate.get("competitor_id") or (
            candidate.get("competitors_involved", [None])[0]
        )
        events = []
        if cid:
            events = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM events WHERE competitor_id = ? ORDER BY date DESC LIMIT 5",
                    (cid,),
                ).fetchall()
            ]

        confirmed = _confirm_pattern_with_llm(candidate, events)
        if confirmed:
            pattern_id = str(uuid.uuid4())
            involved = candidate.get("competitors_involved") or [candidate.get("competitor_id")]
            pattern = {
                "pattern_id": pattern_id,
                "description": confirmed.get("description", candidate.get("detail")),
                "competitors_involved": json.dumps(involved),
                "confidence": confirmed.get("confidence", 0.5),
                "supporting_events": json.dumps([e.get("id") for e in events]),
                "historical_precedent": confirmed.get("historical_precedent", ""),
                "prediction": confirmed.get("prediction", ""),
                "detected_at": datetime.utcnow().isoformat(),
            }
            conn.execute(
                """INSERT OR REPLACE INTO patterns 
                   (pattern_id, description, competitors_involved, confidence, supporting_events, historical_precedent, prediction, detected_at)
                   VALUES (:pattern_id, :description, :competitors_involved, :confidence, :supporting_events, :historical_precedent, :prediction, :detected_at)""",
                pattern,
            )
            conn.commit()
            new_patterns.append(pattern)

    conn.close()
    return new_patterns