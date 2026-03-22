import os
import json
import numpy as np
from datetime import datetime
from openai import OpenAI
from database import get_db

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


class TrendAgent:
    def __init__(self):
        self.name = "TrendAgent"

    def run(self, competitor_id: str, metric_name: str, months_forward: int = 3) -> dict:
        historical_rows = self._load_metrics(competitor_id, metric_name)
        if not historical_rows:
            return {
                "competitor_id": competitor_id,
                "metric_name": metric_name,
                "historical": [],
                "projected": [],
                "projected_months": [],
                "confidence": 0.0,
                "interpretation": "No historical data available.",
                "llm_adjusted_projection": [],
            }

        months = [r[0] for r in historical_rows]
        values = [r[1] for r in historical_rows]
        projection = self._extrapolate(values, months_forward)
        projected_months = self._next_months(months[-1], months_forward)
        interpretation = self._interpret(competitor_id, metric_name, historical_rows, projection, projected_months)

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

    def _load_metrics(self, competitor_id: str, metric_name: str) -> list[tuple]:
        conn = get_db()
        rows = conn.execute(
            "SELECT date, value FROM metrics WHERE competitor_id = ? AND metric_name = ? ORDER BY date ASC",
            (competitor_id, metric_name),
        ).fetchall()
        conn.close()
        return [(r["date"], r["value"]) for r in rows]

    def _extrapolate(self, values: list[float], months_forward: int = 3) -> dict:
        n = len(values)
        x = np.arange(n, dtype=float)
        y = np.array(values, dtype=float)
        degree = 2 if n >= 8 else 1
        coeffs = np.polyfit(x, y, degree)
        poly = np.poly1d(coeffs)
        residuals = y - poly(x)
        std = float(np.std(residuals))
        mean_val = float(np.mean(np.abs(y))) or 1.0
        confidence = float(max(0.0, min(1.0, 1.0 - (std / mean_val))))
        x_future = np.arange(n, n + months_forward, dtype=float)
        projected = [float(poly(xi)) for xi in x_future]
        return {
            "projected_values": [round(p, 2) for p in projected],
            "lower_band": [round(max(0.0, p - 1.5 * std), 2) for p in projected],
            "upper_band": [round(p + 1.5 * std, 2) for p in projected],
            "confidence": round(confidence, 2),
            "std": round(std, 2),
        }

    def _interpret(self, competitor_id, metric_name, historical_rows, projection, projected_months) -> dict:
        conn = get_db()
        patterns = conn.execute(
            "SELECT description, prediction FROM patterns WHERE competitors_involved LIKE ? LIMIT 3",
            (f"%{competitor_id}%",),
        ).fetchall()
        conn.close()

        patterns_text = "\n".join([f"- {p['description']} → {p['prediction']}" for p in patterns]) or "None."
        historical_text = "\n".join([f"  {m}: {v}" for m, v in historical_rows])

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=512,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": f"""Analyze this {metric_name} data for '{competitor_id}':

{historical_text}

Mathematical projection for {projected_months}: {projection['projected_values']}
Confidence: {projection['confidence']}

Known patterns:
{patterns_text}

Return JSON with:
- interpretation: 2-3 sentence plain-English strategic interpretation
- agrees_with_projection: true or false
- reasoning: 1-2 sentences
- adjusted_projection: list of {len(projection['projected_values'])} numbers (your adjusted forecast)""",
                }
            ],
        )

        try:
            result = json.loads(response.choices[0].message.content.strip())
            if "adjusted_projection" not in result or len(result["adjusted_projection"]) != len(projection["projected_values"]):
                result["adjusted_projection"] = projection["projected_values"]
            return result
        except Exception:
            return {"interpretation": "Could not generate interpretation.", "adjusted_projection": projection["projected_values"]}

    def _next_months(self, last_month_str: str, n: int) -> list[str]:
        try:
            if len(last_month_str) == 7:
                last_month_str += "-01"
            last = datetime.strptime(last_month_str[:10], "%Y-%m-%d")
        except Exception:
            last = datetime.utcnow()
        months = []
        for i in range(1, n + 1):
            month = last.month + i
            year = last.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            months.append(f"{year}-{month:02d}")
        return months