import json
from flask import Blueprint, jsonify, request
from database import get_db

data_bp = Blueprint("data", __name__)


@data_bp.route("/competitors", methods=["GET"])
def get_competitors():
    conn = get_db()
    rows = conn.execute("SELECT * FROM competitors").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@data_bp.route("/competitor/<competitor_id>", methods=["GET"])
def get_competitor(competitor_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM competitors WHERE id = ?", (competitor_id,)
    ).fetchone()
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
            "SELECT * FROM events WHERE competitor_id = ? AND event_type = ? ORDER BY date DESC",
            (competitor_id, event_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM events WHERE competitor_id = ? ORDER BY date DESC",
            (competitor_id,),
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@data_bp.route("/competitor/<competitor_id>/metrics", methods=["GET"])
def get_metrics(competitor_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM metrics WHERE competitor_id = ? ORDER BY date ASC",
        (competitor_id,),
    ).fetchall()
    conn.close()
    grouped = {}
    for row in rows:
        r = dict(row)
        name = r["metric_name"]
        if name not in grouped:
            grouped[name] = []
        grouped[name].append({"date": r["date"], "value": r["value"]})
    return jsonify(grouped)


@data_bp.route("/competitor/<competitor_id>/intel", methods=["GET"])
def get_intel(competitor_id):
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM events
           WHERE competitor_id = ?
           AND event_type IN ('news','product_launch','partnership','funding')
           ORDER BY importance_score DESC, date DESC
           LIMIT 15""",
        (competitor_id,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@data_bp.route("/patterns", methods=["GET"])
def get_patterns():
    competitor_id = request.args.get("competitor_id")
    conn = get_db()
    if competitor_id:
        rows = conn.execute(
            "SELECT * FROM patterns WHERE competitors_involved LIKE ? ORDER BY confidence DESC",
            (f"%{competitor_id}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM patterns ORDER BY confidence DESC"
        ).fetchall()
    conn.close()
    results = []
    for row in rows:
        r = dict(row)
        for field in ["competitors_involved", "supporting_events"]:
            if r.get(field):
                try:
                    r[field] = json.loads(r[field])
                except Exception:
                    pass
        results.append(r)
    return jsonify(results)


@data_bp.route("/compare", methods=["GET"])
def compare_competitors():
    ids_param = request.args.get("ids", "")
    ids = [i.strip() for i in ids_param.split(",") if i.strip()]
    if not ids:
        return jsonify({"error": "Provide ?ids=id1,id2"}), 400
    conn = get_db()
    result = {}
    for cid in ids:
        profile = conn.execute(
            "SELECT * FROM competitors WHERE id = ?", (cid,)
        ).fetchone()
        if not profile:
            continue
        metrics = conn.execute(
            "SELECT metric_name, value FROM metrics WHERE competitor_id = ? ORDER BY date DESC",
            (cid,),
        ).fetchall()
        latest_metrics = {}
        for m in metrics:
            if m["metric_name"] not in latest_metrics:
                latest_metrics[m["metric_name"]] = m["value"]
        result[cid] = {
            "profile": dict(profile),
            "latest_metrics": latest_metrics,
        }
    conn.close()
    return jsonify(result)