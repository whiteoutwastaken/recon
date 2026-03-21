import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "recon.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS competitors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            ticker TEXT,
            industry TEXT,
            founded INTEGER,
            hq TEXT,
            funding_total REAL,
            headcount_current INTEGER,
            website TEXT,
            logo_url TEXT,
            description TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            competitor_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            source_url TEXT,
            sentiment_score REAL,
            importance_score REAL,
            FOREIGN KEY (competitor_id) REFERENCES competitors(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competitor_id TEXT NOT NULL,
            date TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            value REAL NOT NULL,
            FOREIGN KEY (competitor_id) REFERENCES competitors(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            pattern_id TEXT PRIMARY KEY,
            description TEXT,
            competitors_involved TEXT,
            confidence REAL,
            supporting_events TEXT,
            historical_precedent TEXT,
            prediction TEXT,
            detected_at TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialized.")


if __name__ == "__main__":
    init_db()