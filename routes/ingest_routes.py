from flask import Blueprint, jsonify

ingest_bp = Blueprint("ingest", __name__)


@ingest_bp.route("/ingest/<competitor_id>", methods=["POST"])
def ingest_all(competitor_id):
    try:
        from ingest.news_scraper import ingest_news
        from ingest.jobs_scraper import ingest_jobs
        news_results = ingest_news(competitor_id)
        jobs_results = ingest_jobs(competitor_id)
        return jsonify({
            "competitor_id": competitor_id,
            "news": {"stored": len(news_results)},
            "jobs": jobs_results,
        })
    except ImportError:
        return jsonify({"error": "Ingest agents not available yet"}), 503


@ingest_bp.route("/ingest/news/<competitor_id>", methods=["POST"])
def ingest_news_route(competitor_id):
    try:
        from ingest.news_scraper import ingest_news
        results = ingest_news(competitor_id)
        return jsonify({"stored": len(results), "events": results})
    except ImportError:
        return jsonify({"error": "News scraper not available yet"}), 503


@ingest_bp.route("/ingest/jobs/<competitor_id>", methods=["POST"])
def ingest_jobs_route(competitor_id):
    try:
        from ingest.jobs_scraper import ingest_jobs
        results = ingest_jobs(competitor_id)
        return jsonify(results)
    except ImportError:
        return jsonify({"error": "Jobs scraper not available yet"}), 503