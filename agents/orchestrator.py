import json
import os
import anthropic
from database import get_db

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ── Tool definitions ──────────────────────────────────────────────────────────

def _get_all_competitor_ids():
    conn = get_db()
    rows = conn.execute("SELECT id, name FROM competitors").fetchall()
    conn.close()
    return {r["id"]: r["name"] for r in rows}


def query_twin(competitor_id: str, question: str) -> str:
    """Pull all data for a competitor and answer a question about them."""
    conn = get_db()
    profile = conn.execute(
        "SELECT * FROM competitors WHERE id = ?", (competitor_id,)
    ).fetchone()
    if not profile:
        conn.close()
        return f"No competitor found with id '{competitor_id}'."

    events = conn.execute(
        "SELECT * FROM events WHERE competitor_id = ? ORDER BY date DESC LIMIT 30",
        (competitor_id,),
    ).fetchall()
    metrics = conn.execute(
        "SELECT * FROM metrics WHERE competitor_id = ? ORDER BY date DESC",
        (competitor_id,),
    ).fetchall()
    conn.close()

    context = f"""
COMPETITOR PROFILE:
{json.dumps(dict(profile), indent=2)}

RECENT EVENTS (last 30):
{json.dumps([dict(e) for e in events], indent=2)}

METRICS TIME-SERIES:
{json.dumps([dict(m) for m in metrics], indent=2)}
"""
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=(
            f"You are an expert competitive intelligence analyst specializing in {profile['name']}. "
            "Answer questions using only the data provided. Be concise and cite specific data points."
        ),
        messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
    )
    return response.content[0].text


def compare_competitors(comp_a: str, comp_b: str, dimension: str) -> str:
    """Compare two competitors on a specific dimension."""
    conn = get_db()
    results = {}
    for cid in [comp_a, comp_b]:
        profile = conn.execute("SELECT * FROM competitors WHERE id = ?", (cid,)).fetchone()
        events = conn.execute(
            "SELECT * FROM events WHERE competitor_id = ? ORDER BY date DESC LIMIT 20",
            (cid,),
        ).fetchall()
        metrics = conn.execute(
            "SELECT * FROM metrics WHERE competitor_id = ? ORDER BY date DESC LIMIT 24",
            (cid,),
        ).fetchall()
        if profile:
            results[cid] = {
                "profile": dict(profile),
                "events": [dict(e) for e in events],
                "metrics": [dict(m) for m in metrics],
            }
    conn.close()

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system="You are a senior competitive intelligence analyst. Compare these two companies objectively and call a winner on the specified dimension.",
        messages=[{
            "role": "user",
            "content": (
                f"Compare {comp_a} vs {comp_b} on the dimension of: {dimension}\n\n"
                f"Data:\n{json.dumps(results, indent=2)}"
            ),
        }],
    )
    return response.content[0].text


def get_patterns() -> str:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM patterns ORDER BY confidence DESC LIMIT 10"
    ).fetchall()
    conn.close()
    if not rows:
        return "No patterns detected yet."
    return json.dumps([dict(r) for r in rows], indent=2)


def get_metrics(competitor_id: str, metric_name: str) -> str:
    conn = get_db()
    rows = conn.execute(
        "SELECT date, value FROM metrics WHERE competitor_id = ? AND metric_name = ? ORDER BY date ASC",
        (competitor_id, metric_name),
    ).fetchall()
    conn.close()
    if not rows:
        return f"No metric '{metric_name}' found for '{competitor_id}'."
    return json.dumps([dict(r) for r in rows], indent=2)


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "query_twin",
        "description": "Query a competitor's digital twin. Ask any question about a specific competitor.",
        "input_schema": {
            "type": "object",
            "properties": {
                "competitor_id": {"type": "string", "description": "The competitor's id (e.g. 'salesforce')"},
                "question": {"type": "string", "description": "The question to answer about this competitor"},
            },
            "required": ["competitor_id", "question"],
        },
    },
    {
        "name": "compare_competitors",
        "description": "Compare two competitors on a specific dimension.",
        "input_schema": {
            "type": "object",
            "properties": {
                "comp_a": {"type": "string"},
                "comp_b": {"type": "string"},
                "dimension": {"type": "string", "description": "e.g. 'AI strategy', 'hiring velocity', 'pricing'"},
            },
            "required": ["comp_a", "comp_b", "dimension"],
        },
    },
    {
        "name": "get_patterns",
        "description": "Get all detected competitive patterns and alerts.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_metrics",
        "description": "Get time-series metric data for a competitor.",
        "input_schema": {
            "type": "object",
            "properties": {
                "competitor_id": {"type": "string"},
                "metric_name": {
                    "type": "string",
                    "enum": ["headcount", "funding", "sentiment", "hiring_velocity", "product_count", "news_volume"],
                },
            },
            "required": ["competitor_id", "metric_name"],
        },
    },
]

TOOL_FUNCTIONS = {
    "query_twin": query_twin,
    "compare_competitors": compare_competitors,
    "get_patterns": get_patterns,
    "get_metrics": get_metrics,
}


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_orchestrator(user_query: str) -> dict:
    """
    Main orchestrator loop. Routes queries to tools, synthesizes a final answer.
    Returns: {answer, data_points, suggested_followups}
    """
    competitors = _get_all_competitor_ids()
    competitor_list = ", ".join([f"{k} ({v})" for k, v in competitors.items()])

    system_prompt = f"""You are Recon, a senior competitive intelligence analyst. 
You have access to digital twins of these competitors: {competitor_list}.
Use your tools to answer questions thoroughly. Always cite specific data points.
When you have enough information, provide a final answer.
After your answer, suggest 2-3 follow-up questions the user might want to ask."""

    messages = [{"role": "user", "content": user_query}]
    data_points = []

    # Agentic loop - max 5 iterations
    for _ in range(5):
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        # Collect any text content
        text_blocks = [b.text for b in response.content if b.type == "text"]

        # If no tool use, we're done
        if response.stop_reason == "end_turn":
            final_answer = "\n".join(text_blocks)
            followups = _extract_followups(final_answer)
            return {
                "answer": final_answer,
                "data_points": data_points,
                "suggested_followups": followups,
            }

        # Execute tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                fn = TOOL_FUNCTIONS.get(block.name)
                if fn:
                    result = fn(**block.input)
                    data_points.append({"tool": block.name, "input": block.input})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

        # Feed results back into the conversation
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    # Fallback if loop exhausted
    return {
        "answer": "I gathered the data but ran out of steps to synthesize a full answer. Try a more specific question.",
        "data_points": data_points,
        "suggested_followups": [],
    }


def _extract_followups(text: str) -> list[str]:
    """Best-effort extraction of follow-up questions from the answer text."""
    lines = text.split("\n")
    followups = []
    capture = False
    for line in lines:
        line = line.strip()
        if "follow" in line.lower() and "?" not in line:
            capture = True
            continue
        if capture and line and ("?" in line or line[0].isdigit()):
            clean = line.lstrip("0123456789.-) ").strip()
            if clean:
                followups.append(clean)
        if len(followups) >= 3:
            break
    return followups