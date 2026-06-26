# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Backend (Flask, port 5000)
pip install -r requirements.txt
python app.py

# Frontend (Next.js, port 3000)
cd frontend
npm install
npm run dev
npm run build
npm run lint

# Test Databricks connection
python database.py

# Run agents directly (useful for one-off ingestion)
python -m agents.ingest.news_agent [competitor_id]   # omit id to run all
python -m agents.ingest.jobs_agent                   # runs all competitors
python -m agents.discovery_agent                     # demo run (hardcoded topic)
```

No test suite exists in this repo.

## Environment Variables

Required in `.env` at project root:
- `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_HTTP_PATH` — data warehouse connection
- `OPENAI_API_KEY` — used by all agents

Optional for frontend (`frontend/.env.local`):
- `NEXT_PUBLIC_API_URL` — defaults to `http://localhost:5000/api`

## Architecture Overview

**Recon** is a competitive intelligence platform. The Flask backend exposes a REST API consumed by a Next.js frontend and powers a multi-agent AI system.

```
Frontend (Next.js + Radix UI + Recharts)  [frontend/lib/api.ts → all API calls]
        ↓ REST /api/*
Flask backend (app.py) — 4 blueprints:
  routes/data_routes.py     → read competitors, events, metrics, patterns
  routes/agent_routes.py    → run orchestrator, trigger pattern detection
  routes/ingest_routes.py   → trigger NewsAgent and JobsAgent per competitor
  routes/voice_routes.py    → voice queries + edge-tts MP3 briefings
        ↓
DatabaseManager (database.py) → Databricks SQL
```

## Agent System

All agents inherit from `BaseAgent` (`agents/base_agent.py`), which provides `self.log()` and an event emitter (`on` / `emit`).

**Agent hierarchy:**

- **OrchestratorAgent** (`agents/orchestrator.py`) — master agent. Receives any user query, uses OpenAI function calling (gpt-4o) in a ReAct loop (max 10 iterations). Tool schemas are defined as `_TOOLS` at module level. The module-level `run_orchestrator()` shim is what routes use — it fetches all competitor IDs, instantiates the agent, and closes the DB.
- **TwinAgent** (`agents/twin_agent.py`) — per-competitor expert. Loads a competitor's full profile, events, metrics, and patterns, then answers questions with citations. Instantiated eagerly by OrchestratorAgent (one per tracked competitor).
- **PatternDetectionAgent** (`agents/pattern_detection.py`) — detects three strategic patterns: hiring surges (2× velocity over 6 months), pricing wars (multiple competitors within 30 days), patent clusters (3+ within 90 days). GPT-4o-mini confirms candidates and scores confidence.
- **TrendAgent** (`agents/trend_agent.py`) — forecasts metrics using NumPy polynomial fitting with LLM-generated interpretation.
- **DiscoveryAgent** (`agents/discovery_agent.py`) — finds top competitors in a market via Google News RSS + LLM extraction. **No HTTP route** — invoked programmatically or via `__main__`.
- **NewsAgent** (`agents/ingest/news_agent.py`) — runs 4 parallel topic searches per competitor, fetches article text, then makes a single GPT batch call. Stores only events with `importance_score >= 0.4`.
- **JobsAgent** (`agents/ingest/jobs_agent.py`) — 5 parallel hiring-keyword searches, single GPT batch analysis, stores monthly metrics and surge events. Uses `asyncio.Semaphore(3)` to throttle requests.

## Database

`DatabaseManager` in `database.py` connects to Databricks and exposes typed methods (`insert_competitor`, `insert_event`, `insert_metrics`, `insert_pattern`, etc.). Run `python database.py` to test the connection and create tables.

**`DBCompat`** is a sqlite3-compatible shim layered on top. Agents that use `get_db()` (returns `DBCompat`) can write sqlite-style SQL and it gets translated:
- Named params (`:name`) → positional (`?`)
- `INSERT OR REPLACE` → `INSERT`
- Column renames: `e.date` → `e.event_date`, `confidence` → `confidence_score`, `competitors_involved` → `affected_competitors`, `supporting_events` → `evidence`, `pattern_id` → `id`
- Queries against `metric_name`/`value` columns (old style) are intercepted and rewritten against the actual columnar schema via `_metrics_compat()`

**Four tables:** `competitors`, `events`, `metrics`, `patterns`

- `events.raw_data`, `patterns.affected_competitors`, and `patterns.evidence` are stored as JSON strings.
- `metrics` stores one row per `(competitor_id, metric_month)` (format `"YYYY-MM"`) with columns: `hiring_velocity`, `news_volume`, `sentiment_avg`, `pricing_changes`, `job_postings`.
- `patterns.is_active` flags currently relevant patterns.

**Frontend metric name aliases** (handled in `data_routes.py` and `compare` endpoint):
- `sentiment` → `sentiment_avg`
- `headcount` → `job_postings`

## Key Design Decisions

- The Orchestrator uses OpenAI **function calling** (not hardcoded routing). Tool calls (`query_twin`, `compare_competitors`, `get_patterns`, `get_metrics`, `detect_patterns`, `project_trend`) are defined as JSON schemas and the LLM decides which to invoke.
- News and jobs ingestion use `asyncio` with parallel tasks; ingest routes call `asyncio.run()` to bridge sync Flask into async agent code.
- Voice routes use `edge-tts` for audio synthesis; the latest briefing MP3 is written to `static/briefing.mp3` and served from `/api/voice/briefing-audio`.
- `data_routes.py` normalizes DB column names to frontend-expected field names via `_norm_event()` and `_norm_pattern()`.
- The frontend is a separate Next.js app in `frontend/`. In production, a built static export can be served from Flask's `static/` folder.
