import json
import os
import uuid
from datetime import datetime
from openai import OpenAI
from database import get_db

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def _detect_hiring_surge(conn, competitor_id: str) -> list[dict]:
    candidates = []
    rows = conn.execute(
        "SELECT date, value FROM metrics WHERE competitor_id = ? AND metric_name = 'hiring_velocity' ORDER BY date DESC LIMIT 6",
        (competitor_id,),
    ).fetchall()
    if len(rows) >= 2:
        recent = rows[0]["value"]
        older = rows[-1]["value"]
        if older > 0 and recent / older >= 2.0:
            candidates.append({
                "type": "hiring_surge",
                "competitor_id": competitor_id,
                "detail": f"Hiring velocity increased {recent/older:.1f}x ({older} → {recent})",
            })
    return candidates


def _detect_pricing_war(conn) -> list[dict]:
    candidates = []
    rows = conn.execute(
        "SELECT competitor_id, date FROM events WHERE event_type = 'pricing_change' ORDER BY date DESC LIMIT 20"
    ).fetchall()
    from datetime import timedelta
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
    candidates = []
    rows = conn.execute(
        "SELECT date FROM events WHERE competitor_id = ? AND event_type = 'patent' ORDER BY date DESC LIMIT 10",
        (competitor_id,),
    ).fetchall()
    if len(rows) >= 3:
        from datetime import timedelta
        dates = [datetime.fromisoformat(r["date"]) for r in rows]
        if (dates[0] - dates[2]).days <= 90:
            candidates.append({
                "type": "patent_cluster",
                "competitor_id": competitor_id,
                "detail": f"{len(rows)} patents filed in 90-day window — possible product pivot",
            })
    return candidates


def _confirm_with_gpt(candidate: dict, supporting_events: list) -> dict | None:
    prompt = f"""Competitive pattern detected:
Type: {candidate['type']}
Detail: {candidate.get('detail', '')}

Supporting events:
{json.dumps(supporting_events, indent=2)}

Analyze this pattern and return JSON with:
- confirmed: true or false (is this a real strategic signal?)
- description: one sentence describing the pattern
- historical_precedent: one sentence of relevant historical precedent
- confidence: float 0-1
- prediction: one sentence prediction

Return ONLY valid JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=400,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(response.choices[0].message.content.strip())
        return result if result.get("confirmed") else None
    except Exception:
        return None


def run_pattern_detection() -> list[dict]:
    conn = get_db()
    competitor_ids = [r["id"] for r in conn.execute("SELECT id FROM competitors").fetchall()]

    all_candidates = []
    for cid in competitor_ids:
        all_candidates.extend(_detect_hiring_surge(conn, cid))
        all_candidates.extend(_detect_patent_cluster(conn, cid))
    all_candidates.extend(_detect_pricing_war(conn))

    new_patterns = []
    for candidate in all_candidates:
        cid = candidate.get("competitor_id") or (candidate.get("competitors_involved", [None])[0])
        events = []
        if cid:
            events = [dict(r) for r in conn.execute(
                "SELECT * FROM events WHERE competitor_id = ? ORDER BY date DESC LIMIT 5", (cid,)
            ).fetchall()]

        confirmed = _confirm_with_gpt(candidate, events)
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