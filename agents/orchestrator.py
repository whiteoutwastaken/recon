import os
import json

from dotenv import load_dotenv
from openai import OpenAI

from agents.base_agent import BaseAgent
from agents.twin_agent import TwinAgent
from agents.pattern_detection import run_pattern_detection as _run_pattern_detection
from agents.trend_agent import TrendAgent
from database import DatabaseManager

load_dotenv(override=True)

# ─────────────────────────────────────────────────────────────────────────────
# Tool schemas for OpenAI function calling
# ─────────────────────────────────────────────────────────────────────────────

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_twin",
            "description": (
                "Ask a specific competitor's digital twin a question. "
                "Use this for any competitor-specific intelligence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "competitor_id": {
                        "type": "string",
                        "description": "The competitor's ID (e.g. 'openai', 'anthropic')",
                    },
                    "question": {
                        "type": "string",
                        "description": "The specific question to ask about this competitor",
                    },
                },
                "required": ["competitor_id", "question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_competitors",
            "description": (
                "Compare multiple competitors on the same dimension by querying each "
                "twin and returning their answers side-by-side."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "competitor_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of competitor IDs to compare",
                    },
                    "dimension": {
                        "type": "string",
                        "description": (
                            "The topic or dimension to compare across competitors "
                            "(e.g. 'pricing strategy', 'hiring trends', 'product roadmap')"
                        ),
                    },
                },
                "required": ["competitor_ids", "dimension"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patterns",
            "description": "Fetch all currently active strategic patterns detected across all competitors.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metrics",
            "description": "Fetch the time-series monthly metrics for a specific competitor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "competitor_id": {
                        "type": "string",
                        "description": "The competitor's ID",
                    },
                    "metric_name": {
                        "type": "string",
                        "description": (
                            "One of: hiring_velocity, news_volume, sentiment_avg, "
                            "pricing_changes, job_postings"
                        ),
                    },
                },
                "required": ["competitor_id", "metric_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_patterns",
            "description": (
                "Trigger the pattern detection agent to run right now and return "
                "any newly detected strategic patterns."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_trend",
            "description": "Call the trend agent to project the future trajectory of a competitor's metric.",
            "parameters": {
                "type": "object",
                "properties": {
                    "competitor_id": {
                        "type": "string",
                        "description": "The competitor's ID",
                    },
                    "metric_name": {
                        "type": "string",
                        "description": (
                            "One of: hiring_velocity, news_volume, sentiment_avg, "
                            "pricing_changes, job_postings"
                        ),
                    },
                },
                "required": ["competitor_id", "metric_name"],
            },
        },
    },
]

_VALID_METRIC_COLS = frozenset(
    {"hiring_velocity", "news_volume", "sentiment_avg", "pricing_changes", "job_postings"}
)


# ─────────────────────────────────────────────────────────────────────────────
# OrchestratorAgent
# ─────────────────────────────────────────────────────────────────────────────

class OrchestratorAgent(BaseAgent):
    """
    Master agent. Receives any user question and uses OpenAI function calling
    to decide which sub-agents and database tools to invoke in a ReAct loop.
    """

    MAX_ITERATIONS = 10

    def __init__(self, competitor_ids: list[str]):
        super().__init__("Orchestrator")
        self.competitor_ids = competitor_ids
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.db = DatabaseManager()
        self.trend_agent = TrendAgent()

        # One TwinAgent per tracked competitor — created eagerly so they're
        # ready to answer without a cold-start DB hit mid-loop.
        self.twins: dict[str, TwinAgent] = {}
        for cid in competitor_ids:
            self.twins[cid] = TwinAgent(cid)
            self.log(f"Initialized TwinAgent for '{cid}'")

    # ─────────────────────────────────────────────────────────────────────────
    # Public interface
    # ─────────────────────────────────────────────────────────────────────────

    def run(self, query: str) -> dict:
        """
        Send the query through a gpt-4o ReAct loop with tool use.

        Returns:
            {
                "answer":           str,
                "tools_called":     list[{"tool": str, "args": dict}],
                "data_points_cited": list[str],
            }
        """
        competitor_list = ", ".join(self.competitor_ids) if self.competitor_ids else "none tracked yet"
        system_prompt = (
            f"You are Recon, a senior competitive intelligence analyst. "
            f"You have access to digital twins of these competitors: {competitor_list}. "
            f"Use your tools to answer questions thoroughly. Always cite specific data points. "
            f"If a question requires data from multiple competitors, query each one."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        tools_called: list[dict] = []
        data_points_cited: list[str] = []

        for iteration in range(self.MAX_ITERATIONS):
            self.log(f"ReAct iteration {iteration + 1}/{self.MAX_ITERATIONS}")

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=_TOOLS,
                tool_choice="auto",
            )
            message = response.choices[0].message

            # No tool calls → final answer
            if not message.tool_calls:
                return {
                    "answer": message.content or "",
                    "tools_called": tools_called,
                    "data_points_cited": data_points_cited,
                }

            # Append assistant turn (with tool_calls) to history
            messages.append(message)

            # Execute every tool call in this turn and feed results back
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                tools_called.append({"tool": fn_name, "args": args})

                result_str = self._dispatch(fn_name, args, data_points_cited)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str,
                })

        # Hit the iteration cap — request a final answer without tools
        self.log("Max iterations reached, requesting final answer without tools")
        messages.append({
            "role": "user",
            "content": "Please provide your final answer now based on all the information gathered.",
        })
        final = self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )
        return {
            "answer": final.choices[0].message.content or "",
            "tools_called": tools_called,
            "data_points_cited": data_points_cited,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Tool dispatch
    # ─────────────────────────────────────────────────────────────────────────

    def _dispatch(self, fn_name: str, args: dict, data_points_cited: list) -> str:
        handlers = {
            "query_twin":          lambda: self._tool_query_twin(
                                       args.get("competitor_id", ""),
                                       args.get("question", ""),
                                       data_points_cited,
                                   ),
            "compare_competitors": lambda: self._tool_compare_competitors(
                                       args.get("competitor_ids", []),
                                       args.get("dimension", ""),
                                       data_points_cited,
                                   ),
            "get_patterns":        lambda: self._tool_get_patterns(),
            "get_metrics":         lambda: self._tool_get_metrics(
                                       args.get("competitor_id", ""),
                                       args.get("metric_name", ""),
                                   ),
            "detect_patterns":     lambda: self._tool_detect_patterns(),
            "project_trend":       lambda: self._tool_project_trend(
                                       args.get("competitor_id", ""),
                                       args.get("metric_name", ""),
                                   ),
        }
        handler = handlers.get(fn_name)
        if not handler:
            return f"Unknown tool: {fn_name}"
        try:
            return handler()
        except Exception as e:
            self.log(f"Tool '{fn_name}' raised: {e}")
            return f"Tool error ({fn_name}): {e}"

    # ─────────────────────────────────────────────────────────────────────────
    # Individual tool implementations
    # ─────────────────────────────────────────────────────────────────────────

    def _tool_query_twin(self, competitor_id: str, question: str, data_points_cited: list) -> str:
        self.log(f"Calling query_twin for {competitor_id}...")
        twin = self.twins.get(competitor_id)
        if not twin:
            # Lazily create a twin for competitors added after __init__
            twin = TwinAgent(competitor_id)
            self.twins[competitor_id] = twin
        result = twin.query(question)
        cited = result.get("cited_events", [])
        data_points_cited.extend(cited)
        return json.dumps({
            "competitor_id": competitor_id,
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence", 0),
            "cited_events": cited,
        })

    def _tool_compare_competitors(
        self, competitor_ids: list, dimension: str, data_points_cited: list
    ) -> str:
        self.log(f"Calling compare_competitors for {competitor_ids} on '{dimension}'...")
        comparisons = {}
        for cid in competitor_ids:
            twin = self.twins.get(cid)
            if not twin:
                twin = TwinAgent(cid)
                self.twins[cid] = twin
            result = twin.query(f"What is your {dimension}?")
            cited = result.get("cited_events", [])
            data_points_cited.extend(cited)
            comparisons[cid] = {
                "answer": result.get("answer", ""),
                "confidence": result.get("confidence", 0),
                "cited_events": cited,
            }
        return json.dumps({"dimension": dimension, "comparisons": comparisons})

    def _tool_get_patterns(self) -> str:
        self.log("Calling get_patterns — fetching all active patterns from database...")
        patterns = self.db.get_patterns(limit=20)
        if not patterns:
            return "No active patterns detected yet."
        return json.dumps([
            {
                "title": p.get("title", ""),
                "pattern_type": p.get("pattern_type", ""),
                "description": p.get("description", ""),
                "affected_competitors": p.get("affected_competitors", ""),
                "confidence_score": p.get("confidence_score", 0),
                "prediction": p.get("prediction", ""),
                "detected_at": str(p.get("detected_at", "")),
            }
            for p in patterns
        ])

    def _tool_get_metrics(self, competitor_id: str, metric_name: str) -> str:
        self.log(f"Calling get_metrics for {competitor_id} / {metric_name}...")
        rows = self.db.get_metrics(competitor_id)
        if not rows:
            return f"No metrics found for competitor '{competitor_id}'."
        col = metric_name if metric_name in _VALID_METRIC_COLS else "hiring_velocity"
        series = [
            {"month": r.get("metric_month", ""), "value": r.get(col)}
            for r in rows
            if r.get(col) is not None
        ]
        return json.dumps({"competitor_id": competitor_id, "metric": col, "data": series})

    def _tool_detect_patterns(self) -> str:
        self.log("Calling detect_patterns — triggering pattern detection agent now...")
        new_patterns = _run_pattern_detection()
        if not new_patterns:
            return "Pattern detection ran successfully but found no new patterns."
        return json.dumps(new_patterns)

    def _tool_project_trend(self, competitor_id: str, metric_name: str) -> str:
        self.log(f"Calling project_trend for {competitor_id} / {metric_name}...")
        result = self.trend_agent.run(competitor_id, metric_name)
        return json.dumps({
            "competitor_id": competitor_id,
            "metric_name": metric_name,
            "historical_months": result.get("historical_months", []),
            "historical": result.get("historical", []),
            "projected_months": result.get("projected_months", []),
            "projected": result.get("projected", []),
            "confidence": result.get("confidence", 0),
            "interpretation": result.get("interpretation", ""),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Module-level shim — keeps agent_routes.py working without changes
# ─────────────────────────────────────────────────────────────────────────────

def run_orchestrator(query: str) -> dict:
    """Thin wrapper used by agent_routes.py."""
    db = DatabaseManager()
    try:
        competitor_ids = [r["id"] for r in db.get_all_competitors()]
    finally:
        db.close()

    agent = OrchestratorAgent(competitor_ids)
    result = agent.run(query)
    agent.db.close()

    return {
        "answer": result["answer"],
        "data_points": result["data_points_cited"],
        "suggested_followups": [],
    }
