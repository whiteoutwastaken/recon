import os
import json
import numpy as np
from datetime import datetime, timedelta
from database import get_db

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
except Exception:
    _client = None


class TrendAgent:
    def __init__(self):
        self.name = "TrendAgent"

    def run(self, competitor_id: str, metric_name: str, months_forward: int = 3) -> dict:
        """
        Full pipeline:
          1. Load historical data from metrics table
          2. numpy polyfit projection + confidence band
          3. LLM interpretation
          4. Return structured result
        """
        historical_rows = self._load_metrics(competitor_id, metric_name)

        if not historical_rows:
            return {
                "competitor_id": competitor_id,
                "metric_name": metric_name,
                "historical": [],
                "projected": [],
                "projected_months": [],
                "confidence": 0.0,
                "interpretation": "No historical data available for this metric.",
                "llm_adjusted_projection": [],
            }

        months = [r[0] for r in historical_rows]
        values = [r[1] for r in historical_rows]

        projection = self._extrapolate(values, months_forward)
        projected_months = self._next_months(months[-1], months_forward)

        interpretation = self._interpret(
            competitor_id, metric_name, historical_rows, projection, projected_months
        )

        return {
            "competitor_id": competitor_id,
            "metric_name": metric_name,
            "historical": values,
            "historical_months": months,
            "projected": projection["projected_values"],
            "projected_months": projected_months,
            "confidence": projection["confidence"],
            "confidence_lower": projection["lower_band"],
            "confidence_upper": projection["upper_band"],
            "interpretation": interpretation.get("interpretation", ""),
            "llm_adjusted_projection": interpretation.get("adjusted_projection", projection["projected_values"]),
        }

    # ── Step 1 ────────────────────────────────────────────────────────────────

    def _load_metrics(self, competitor_id: str, metric_name: str) -> list[tuple]:
        """Returns list of (month, value) tuples sorted by date."""
        conn = get_db()
        rows = conn.execute(
            """SELECT date, value FROM metrics
               WHERE competitor_id = ? AND metric_name = ?
               ORDER BY date ASC""",
            (competitor_id, metric_name),
        ).fetchall()
        conn.close()
        return [(r["date"], r["value"]) for r in rows]

    # ── Step 2 ────────────────────────────────────────────────────────────────

    def _extrapolate(self, values: list[float], months_forward: int = 3) -> dict:
        """
        Fit a polynomial trend line and project forward.
        Returns projected values + confidence band based on residual std dev.
        """
        n = len(values)
        x = np.arange(n, dtype=float)
        y = np.array(values, dtype=float)

        # Degree 1 for short series, degree 2 if we have enough data
        degree = 2 if n >= 8 else 1
        coeffs = np.polyfit(x, y, degree)
        poly = np.poly1d(coeffs)

        # Residuals → std dev → confidence
        residuals = y - poly(x)
        std = float(np.std(residuals))
        # Confidence: lower std relative to mean = higher confidence
        mean_val = float(np.mean(np.abs(y))) or 1.0
        confidence = float(max(0.0, min(1.0, 1.0 - (std / mean_val))))

        # Project forward
        x_future = np.arange(n, n + months_forward, dtype=float)
        projected = [float(poly(xi)) for xi in x_future]
        lower = [max(0.0, p - 1.5 * std) for p in projected]
        upper = [p + 1.5 * std for p in projected]

        return {
            "projected_values": [round(p, 2) for p in projected],
            "lower_band": [round(l, 2) for l in lower],
            "upper_band": [round(u, 2) for u in upper],
            "confidence": round(confidence, 2),
            "std": round(std, 2),
        }

    # ── Step 3 ────────────────────────────────────────────────────────────────

    def _interpret(
        self,
        competitor_id: str,
        metric_name: str,
        historical_rows: list[tuple],
        projection: dict,
        projected_months: list[str],
    ) -> dict:
        """Send data to Claude and get plain-English interpretation + adjusted projection."""
        if _client is None:
            return {
                "interpretation": "LLM not available.",
                "adjusted_projection": projection["projected_values"],
            }

        # Pull any relevant patterns for context
        conn = get_db()
        patterns = conn.execute(
            "SELECT description, prediction FROM patterns WHERE competitors_involved LIKE ? LIMIT 3",
            (f"%{competitor_id}%",),
        ).fetchall()
        conn.close()

        patterns_text = "\n".join(
            [f"- {p['description']} → {p['prediction']}" for p in patterns]
        ) or "No patterns detected yet."

        historical_text = "\n".join(
            [f"  {month}: {value}" for month, value in historical_rows]
        )

        prompt = f"""Here are {len(historical_rows)} months of {metric_name} data for competitor '{competitor_id}':

{historical_text}

The mathematical trend projects these values for {projected_months}:
{projection['projected_values']}

Confidence level: {projection['confidence']} (based on historical variance)

Known patterns involving this competitor:
{patterns_text}

Please analyze this and return a JSON object with exactly these keys:
{{
  "interpretation": "2-3 sentence plain-English interpretation of this trend and what it means strategically",
  "agrees_with_projection": true or false,
  "reasoning": "1-2 sentences explaining why you agree or disagree",
  "adjusted_projection": [{projected_months[0] value}, {projected_months[1] if len > 1 else '...'}, ...] (same length as mathematical projection, your adjusted numbers)
}}

Return ONLY valid JSON, no markdown, no explanation outside the JSON."""

        try:
            response = _client.messages.create(
                model="claude-opus-4-5",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            text = text.lstrip("```json").lstrip("```").rstrip("```").strip()
            result = json.loads(text)
            # Ensure adjusted_projection exists and is right length
            if "adjusted_projection" not in result or len(result["adjusted_projection"]) != len(projection["projected_values"]):
                result["adjusted_projection"] = projection["projected_values"]
            return result
        except Exception as e:
            print(f"TrendAgent LLM error: {e}")
            return {
                "interpretation": "Could not generate LLM interpretation.",
                "adjusted_projection": projection["projected_values"],
            }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _next_months(self, last_month_str: str, n: int) -> list[str]:
        """Given a date string, return the next n month strings."""
        try:
            # Handle both YYYY-MM and YYYY-MM-DD formats
            if len(last_month_str) == 7:
                last_month_str += "-01"
            last = datetime.strptime(last_month_str[:10], "%Y-%m-%d")
        except Exception:
            last = datetime.utcnow()

        months = []
        for i in range(1, n + 1):
            # Add i months
            month = last.month + i
            year = last.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            months.append(f"{year}-{month:02d}")
        return months