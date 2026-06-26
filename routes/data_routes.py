import json
from flask import Blueprint, jsonify, request
from database import get_db

data_bp = Blueprint("data", __name__)


def _norm_event(r: dict) -> dict:
    """Normalize event row to the field names the frontend expects."""
    return {
        "id":              r.get("id", ""),
        "competitor_id":   r.get("competitor_id", ""),
        "event_type":      r.get("event_type", ""),
        "title":           r.get("title", ""),
        "description":     r.get("summary") or r.get("description", ""),
        "summary":         r.get("summary", ""),
        "sentiment_score": r.get("sentiment") or r.get("sentiment_score", 0),
        "importance_score":r.get("importance_score", 0),
        "source_url":      r.get("source_url", ""),
        "date":            str(r.get("event_date") or r.get("date", ""))[:10],
        "department":      r.get("department", ""),
    }


def _norm_pattern(r: dict) -> dict:
    """Normalize pattern row to the field names the frontend expects."""
    competitors = r.get("affected_competitors") or r.get("competitors_involved") or "[]"
    if isinstance(competitors, str):
        try:
            competitors = json.loads(competitors)
        except Exception:
            competitors = []
    return {
        "pattern_id":   r.get("id") or r.get("pattern_id", ""),
        "type":         r.get("pattern_type") or r.get("type", "other"),
        "title":        r.get("title", ""),
        "description":  r.get("description", ""),
        "confidence":   r.get("confidence_score") or r.get("confidence", 0),
        "prediction":   r.get("prediction", ""),
        "affected_competitors": competitors,
        "detected_at":  str(r.get("detected_at", "")),
    }


@data_bp.route("/competitors", methods=["GET"])
def get_competitors():
    conn = get_db()
    rows = conn.execute("SELECT * FROM competitors").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@data_bp.route("/competitor/<competitor_id>", methods=["GET"])
def get_competitor(competitor_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM competitors WHERE id = ?", (competitor_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Competitor not found"}), 404
    return jsonify(dict(row))


@data_bp.route("/competitor/<competitor_id>/events", methods=["GET"])
def get_events(competitor_id):
    event_type = request.args.get("type")
    conn = get_db()
    if event_type:
        rows = conn.execute(
            "SELECT * FROM events WHERE competitor_id = ? AND event_type = ? ORDER BY event_date DESC",
            (competitor_id, event_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM events WHERE competitor_id = ? ORDER BY event_date DESC",
            (competitor_id,),
        ).fetchall()
    conn.close()
    return jsonify([_norm_event(dict(r)) for r in rows])


@data_bp.route("/competitor/<competitor_id>/metrics", methods=["GET"])
def get_metrics(competitor_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM metrics WHERE competitor_id = ? ORDER BY metric_month ASC",
        (competitor_id,),
    ).fetchall()
    conn.close()

    metric_cols = ["hiring_velocity", "news_volume", "sentiment_avg", "pricing_changes", "job_postings"]
    grouped: dict = {col: [] for col in metric_cols}
    for row in rows:
        r = dict(row)
        for col in metric_cols:
            if r.get(col) is not None:
                grouped[col].append({"date": r["metric_month"], "value": r[col]})

    # Frontend uses "sentiment" not "sentiment_avg"
    grouped["sentiment"] = grouped["sentiment_avg"]
    return jsonify(grouped)


@data_bp.route("/competitor/<competitor_id>/intel", methods=["GET"])
def get_intel(competitor_id):
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM events
           WHERE competitor_id = ?
           AND event_type IN ('news','product_launch','partnership','funding')
           ORDER BY importance_score DESC, event_date DESC
           LIMIT 15""",
        (competitor_id,),
    ).fetchall()
    conn.close()
    return jsonify([_norm_event(dict(r)) for r in rows])


@data_bp.route("/competitor/<competitor_id>/trend/<metric>", methods=["GET"])
def get_trend(competitor_id, metric):
    # Map frontend metric names to our DB column names
    metric_map = {
        "sentiment": "sentiment_avg",
        "headcount": "job_postings",
    }
    db_metric = metric_map.get(metric, metric)
    try:
        from agents.trend_agent import TrendAgent
        agent = TrendAgent()
        result = agent.run(competitor_id, db_metric)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@data_bp.route("/patterns", methods=["GET"])
def get_patterns():
    competitor_id = request.args.get("competitor_id")
    conn = get_db()
    if competitor_id:
        rows = conn.execute(
            "SELECT * FROM patterns WHERE affected_competitors LIKE ? ORDER BY confidence_score DESC",
            (f"%{competitor_id}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM patterns ORDER BY confidence_score DESC"
        ).fetchall()
    conn.close()
    return jsonify([_norm_pattern(dict(r)) for r in rows])


@data_bp.route("/compare", methods=["GET"])
def compare_competitors():
    ids_param = request.args.get("ids", "")
    ids = [i.strip() for i in ids_param.split(",") if i.strip()]
    if not ids:
        return jsonify({"error": "Provide ?ids=id1,id2"}), 400

    conn = get_db()
    result = {}
    metric_cols = ["hiring_velocity", "news_volume", "sentiment_avg", "pricing_changes", "job_postings"]

    for cid in ids:
        profile = conn.execute("SELECT * FROM competitors WHERE id = ?", (cid,)).fetchone()
        if not profile:
            continue
        # Get latest metrics row
        latest = conn.execute(
            "SELECT * FROM metrics WHERE competitor_id = ? ORDER BY metric_month DESC LIMIT 1",
            (cid,),
        ).fetchone()
        latest_metrics = {}
        if latest:
            r = dict(latest)
            for col in metric_cols:
                latest_metrics[col] = r.get(col, 0)
            # Aliases the frontend uses
            latest_metrics["sentiment"] = latest_metrics.get("sentiment_avg", 0)
            latest_metrics["headcount"] = latest_metrics.get("job_postings", 0)
        result[cid] = {
            "profile": dict(profile),
            "latest_metrics": latest_metrics,
        }
    conn.close()
    return jsonify(result)
