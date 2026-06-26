import os
import re
import json
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv
from databricks import sql

load_dotenv(override=True)


# ─────────────────────────────────────────────────────────────────────────────
# SQLite-compatible shim so teammate code (get_db() / conn.execute().fetchall())
# works unchanged against our Databricks DatabaseManager.
# ─────────────────────────────────────────────────────────────────────────────

# Maps old metric_name strings → our column names in the metrics table
_METRIC_COL = {
    "hiring_velocity": "hiring_velocity",
    "news_volume":     "news_volume",
    "sentiment":       "sentiment_avg",
    "sentiment_avg":   "sentiment_avg",
    "pricing_changes": "pricing_changes",
    "job_postings":    "job_postings",
    "headcount":       "job_postings",
    "funding":         "job_postings",
    "product_count":   "news_volume",
}


class _Result:
    """Mimics sqlite3 cursor result — supports .fetchall() and .fetchone()."""
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class DBCompat:
    """
    Drop-in replacement for sqlite3 connection.
    Translates the teammate's query patterns to our Databricks schema.
    """
    def __init__(self):
        self._db = DatabaseManager()

    def execute(self, query: str, params=None):
        params_list = self._extract_params(query, params)
        query = self._translate(query)

        # Intercept old-style metric queries (metric_name / value columns)
        if "metric_name" in query.lower() and "metrics" in query.lower():
            return _Result(self._metrics_compat(params_list))

        if query.strip().upper().startswith("SELECT"):
            rows = self._db.fetch(query, params_list or None)
            return _Result(rows)
        else:
            try:
                self._db.execute(query, params_list or None)
            except Exception as e:
                print(f"[DBCompat] {e}")
            return _Result([])

    def commit(self):
        pass  # Databricks auto-commits

    def close(self):
        try:
            self._db.close()
        except Exception:
            pass

    # ── helpers ───────────────────────────────────────────────────────────────

    def _extract_params(self, query: str, params) -> list:
        """Convert named params (:name dict) → ordered list matching ? placeholders."""
        named = re.findall(r":(\w+)", query)
        if named and isinstance(params, dict):
            return [params[n] for n in named]
        if params is None:
            return []
        return list(params)

    def _translate(self, q: str) -> str:
        """Rewrite column/syntax differences between the two schemas."""
        q = re.sub(r":\w+", "?", q)                                              # named → positional
        q = re.sub(r"\bINSERT\s+OR\s+REPLACE\s+INTO\b", "INSERT INTO", q, flags=re.I)
        q = re.sub(r"\bORDER BY e\.date\b", "ORDER BY e.event_date", q, flags=re.I)
        q = re.sub(r"\bORDER BY date\b",    "ORDER BY event_date",    q, flags=re.I)
        q = re.sub(r"\be\.date\b",          "e.event_date",           q, flags=re.I)
        q = re.sub(r"\bORDER BY confidence\b", "ORDER BY confidence_score", q, flags=re.I)
        q = re.sub(r"\bcompetitors_involved\b", "affected_competitors",     q, flags=re.I)
        q = re.sub(r"\bpattern_id\b",       "id",                     q, flags=re.I)
        q = re.sub(r"\bsupporting_events\b", "evidence",               q, flags=re.I)
        q = re.sub(r"\bhistorical_precedent\b", "description",         q, flags=re.I)
        # confidence as a column name → confidence_score (skip if already confidence_score)
        q = re.sub(r"\bconfidence\b(?!_score)", "confidence_score", q, flags=re.I)
        return q

    def _metrics_compat(self, params: list) -> list[dict]:
        """
        Translate: SELECT date, value FROM metrics WHERE competitor_id=? AND metric_name=?
        → our column-based metrics schema, returning [{date, value}] rows.
        """
        if len(params) < 1:
            return []
        competitor_id = params[0]
        metric_name = str(params[1]).lower() if len(params) >= 2 else "hiring_velocity"
        col = _METRIC_COL.get(metric_name, "hiring_velocity")
        rows = self._db.fetch(
            f"SELECT metric_month, {col} FROM metrics WHERE competitor_id = ? ORDER BY metric_month ASC",
            [competitor_id],
        )
        return [{"date": r["metric_month"], "value": r[col]} for r in rows]


def get_db() -> DBCompat:
    """Return a SQLite-compatible connection backed by Databricks."""
    return DBCompat()


class DatabaseManager:
    """
    Manages the Databricks connection and all CRUD operations for RECON.

    Usage:
        db = DatabaseManager()   # connects on creation
        db.init_db()             # creates all tables
        db.insert_competitor(...)
        db.close()               # always close when done
    """

    def __init__(self):
        host = os.getenv("DATABRICKS_HOST", "").replace("https://", "")
        http_path = os.getenv("DATABRICKS_HTTP_PATH")
        token = os.getenv("DATABRICKS_TOKEN")

        if not all([host, http_path, token]):
            raise ValueError(
                "Missing Databricks credentials. "
                "Check DATABRICKS_HOST, DATABRICKS_HTTP_PATH, and DATABRICKS_TOKEN in .env"
            )

        self.conn = sql.connect(
            server_hostname=host,
            http_path=http_path,
            access_token=token,
        )
        print(f"Connected to Databricks ({host})")

    # -------------------------------------------------------------------------
    # Core utilities
    # -------------------------------------------------------------------------

    def execute(self, query: str, params: list = None):
        """Run a SQL statement that doesn't return rows (INSERT, UPDATE, CREATE, etc.)."""
        with self.conn.cursor() as cursor:
            cursor.execute(query, params or [])

    def fetch(self, query: str, params: list = None) -> list:
        """Run a SELECT and return results as a list of dicts."""
        with self.conn.cursor() as cursor:
            cursor.execute(query, params or [])
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self):
        """Close the Databricks connection."""
        self.conn.close()
        print("Databricks connection closed.")

    # -------------------------------------------------------------------------
    # Table creation
    # -------------------------------------------------------------------------

    def init_db(self):
        """Create all 4 tables if they don't already exist. Safe to run multiple times."""

        self.execute("""
            CREATE TABLE IF NOT EXISTS competitors (
                id             VARCHAR(100),
                name           VARCHAR(200),
                industry       VARCHAR(100),
                description    STRING,
                website        VARCHAR(200),
                founded_year   INT,
                employee_count INT,
                pricing_tier   VARCHAR(100),
                key_products   STRING,
                hq_location    VARCHAR(200),
                created_at     TIMESTAMP,
                updated_at     TIMESTAMP
            )
        """)

        self.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id               VARCHAR(100),
                competitor_id    VARCHAR(100),
                event_type       VARCHAR(50),
                title            VARCHAR(500),
                summary          STRING,
                sentiment        DOUBLE,
                importance_score DOUBLE,
                source_url       VARCHAR(1000),
                event_date       TIMESTAMP,
                department       VARCHAR(100),
                raw_data         STRING,
                created_at       TIMESTAMP
            )
        """)

        self.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id               VARCHAR(100),
                competitor_id    VARCHAR(100),
                metric_month     VARCHAR(7),
                hiring_velocity  DOUBLE,
                news_volume      INT,
                sentiment_avg    DOUBLE,
                pricing_changes  INT,
                job_postings     INT,
                created_at       TIMESTAMP
            )
        """)

        self.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id                   VARCHAR(100),
                pattern_type         VARCHAR(100),
                title                VARCHAR(500),
                description          STRING,
                affected_competitors STRING,
                confidence_score     DOUBLE,
                evidence             STRING,
                prediction           STRING,
                is_active            BOOLEAN,
                detected_at          TIMESTAMP,
                created_at           TIMESTAMP
            )
        """)

        print("All 4 tables ready.")

    # -------------------------------------------------------------------------
    # COMPETITORS
    # -------------------------------------------------------------------------

    def insert_competitor(
        self,
        id: str,
        name: str,
        industry: str,
        description: str,
        website: str,
        founded_year: int,
        employee_count: int,
        pricing_tier: str,
        key_products: list,
        hq_location: str,
    ):
        now = datetime.utcnow()
        self.execute(
            """
            INSERT INTO competitors
              (id, name, industry, description, website, founded_year,
               employee_count, pricing_tier, key_products, hq_location,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                id, name, industry, description, website, founded_year,
                employee_count, pricing_tier, json.dumps(key_products),
                hq_location, now, now,
            ],
        )

    def get_competitor(self, competitor_id: str):
        rows = self.fetch("SELECT * FROM competitors WHERE id = ?", [competitor_id])
        return rows[0] if rows else None

    def get_all_competitors(self) -> list:
        return self.fetch("SELECT * FROM competitors ORDER BY name")

    def update_competitor(self, competitor_id: str, **fields):
        """Update specific fields on a competitor. Example: update_competitor('salesforce', employee_count=80000)"""
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [datetime.utcnow(), competitor_id]
        self.execute(
            f"UPDATE competitors SET {set_clause}, updated_at = ? WHERE id = ?",
            values,
        )

    # -------------------------------------------------------------------------
    # EVENTS
    # -------------------------------------------------------------------------

    def insert_event(
        self,
        competitor_id: str,
        event_type: str,
        title: str,
        summary: str,
        sentiment: float,
        importance_score: float,
        source_url: str = "",
        event_date: datetime = None,
        department: str = "",
        raw_data: dict = None,
    ) -> str:
        """Insert an event and return its generated ID."""
        event_id = str(uuid.uuid4())
        now = datetime.utcnow()
        self.execute(
            """
            INSERT INTO events
              (id, competitor_id, event_type, title, summary, sentiment,
               importance_score, source_url, event_date, department, raw_data,
               created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event_id, competitor_id, event_type, title, summary,
                sentiment, importance_score, source_url,
                event_date or now, department, json.dumps(raw_data or {}), now,
            ],
        )
        return event_id

    def get_events(self, competitor_id: str, limit: int = 50) -> list:
        return self.fetch(
            """
            SELECT * FROM events
            WHERE competitor_id = ?
            ORDER BY event_date DESC
            LIMIT ?
            """,
            [competitor_id, limit],
        )

    def get_recent_events(self, competitor_id: str, days: int = 30) -> list:
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.fetch(
            """
            SELECT * FROM events
            WHERE competitor_id = ? AND event_date >= ?
            ORDER BY event_date DESC
            """,
            [competitor_id, cutoff],
        )

    # -------------------------------------------------------------------------
    # METRICS
    # -------------------------------------------------------------------------

    def insert_metrics(
        self,
        competitor_id: str,
        metric_month: str,
        hiring_velocity: float,
        news_volume: int,
        sentiment_avg: float,
        pricing_changes: int,
        job_postings: int,
    ) -> str:
        """Insert monthly metrics. metric_month format: '2024-03'"""
        metric_id = str(uuid.uuid4())
        now = datetime.utcnow()
        self.execute(
            """
            INSERT INTO metrics
              (id, competitor_id, metric_month, hiring_velocity, news_volume,
               sentiment_avg, pricing_changes, job_postings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                metric_id, competitor_id, metric_month, hiring_velocity,
                news_volume, sentiment_avg, pricing_changes, job_postings, now,
            ],
        )
        return metric_id

    def get_metrics(self, competitor_id: str) -> list:
        return self.fetch(
            """
            SELECT * FROM metrics
            WHERE competitor_id = ?
            ORDER BY metric_month DESC
            """,
            [competitor_id],
        )

    def get_latest_metrics(self, competitor_id: str):
        rows = self.fetch(
            """
            SELECT * FROM metrics
            WHERE competitor_id = ?
            ORDER BY metric_month DESC
            LIMIT 1
            """,
            [competitor_id],
        )
        return rows[0] if rows else None

    # -------------------------------------------------------------------------
    # PATTERNS
    # -------------------------------------------------------------------------

    def insert_pattern(
        self,
        pattern_type: str,
        title: str,
        description: str,
        affected_competitors: list,
        confidence_score: float,
        evidence: dict,
        prediction: str,
        detected_at: datetime = None,
    ) -> str:
        """Insert a detected pattern and return its generated ID."""
        pattern_id = str(uuid.uuid4())
        now = datetime.utcnow()
        self.execute(
            """
            INSERT INTO patterns
              (id, pattern_type, title, description, affected_competitors,
               confidence_score, evidence, prediction, is_active,
               detected_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                pattern_id, pattern_type, title, description,
                json.dumps(affected_competitors), confidence_score,
                json.dumps(evidence), prediction, True,
                detected_at or now, now,
            ],
        )
        return pattern_id

    def get_patterns(self, limit: int = 20) -> list:
        return self.fetch(
            """
            SELECT * FROM patterns
            WHERE is_active = true
            ORDER BY detected_at DESC
            LIMIT ?
            """,
            [limit],
        )

    def get_recent_patterns(self, days: int = 7) -> list:
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.fetch(
            """
            SELECT * FROM patterns
            WHERE is_active = true AND detected_at >= ?
            ORDER BY confidence_score DESC
            """,
            [cutoff],
        )

    def deactivate_pattern(self, pattern_id: str):
        self.execute(
            "UPDATE patterns SET is_active = false WHERE id = ?",
            [pattern_id],
        )


# -------------------------------------------------------------------------
# Quick connection test — run `python database.py` to verify everything works
# -------------------------------------------------------------------------
if __name__ == "__main__":
    print("Testing Databricks connection...")
    db = DatabaseManager()
    db.init_db()
    print("\nSuccess! Run seed.py next to load demo data.")
    db.close()
