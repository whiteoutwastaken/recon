from flask import Blueprint, jsonify, request
from agents.orchestrator import run_orchestrator
from agents.pattern_detection import run_pattern_detection

agent_bp = Blueprint("agent", __name__)


@agent_bp.route("/agent/query", methods=["POST"])
def agent_query():
    data = request.get_json()
    if not data or not data.get("query"):
        return jsonify({"error": "Provide {query: string}"}), 400

    result = run_orchestrator(data["query"])
    return jsonify(result)


@agent_bp.route("/detect-patterns", methods=["POST"])
def detect_patterns():
    new_patterns = run_pattern_detection()
    return jsonify({"new_patterns": new_patterns, "count": len(new_patterns)})