import asyncio
from flask import Blueprint, jsonify
from database import DatabaseManager

ingest_bp = Blueprint("ingest", __name__)


def _get_company_name(competitor_id: str) -> str:
    db = DatabaseManager()
    competitor = db.get_competitor(competitor_id)
    db.close()
    return competitor["name"] if competitor else competitor_id


@ingest_bp.route("/ingest/<competitor_id>", methods=["POST"])
def ingest_all(competitor_id):
    from agents.ingest.news_agent import NewsAgent
    from agents.ingest.jobs_agent import JobsAgent

    company_name = _get_company_name(competitor_id)
    db = DatabaseManager()

    news_count = asyncio.run(NewsAgent(db).run(competitor_id, company_name))
    asyncio.run(JobsAgent(db).run(competitor_id, company_name))

    db.close()
    return jsonify({"competitor_id": competitor_id, "news_events_stored": news_count})


@ingest_bp.route("/ingest/news/<competitor_id>", methods=["POST"])
def ingest_news_route(competitor_id):
    from agents.ingest.news_agent import NewsAgent

    company_name = _get_company_name(competitor_id)
    db = DatabaseManager()
    count = asyncio.run(NewsAgent(db).run(competitor_id, company_name))
    db.close()
    return jsonify({"stored": count})


@ingest_bp.route("/ingest/jobs/<competitor_id>", methods=["POST"])
def ingest_jobs_route(competitor_id):
    from agents.ingest.jobs_agent import JobsAgent

    company_name = _get_company_name(competitor_id)
    db = DatabaseManager()
    asyncio.run(JobsAgent(db).run(competitor_id, company_name))
    db.close()
    return jsonify({"status": "done", "competitor_id": competitor_id})
