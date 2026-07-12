"""Persistent, structured System Timeline storage."""

import calendar
import json
import sqlite3
import time
from pathlib import Path


DEFAULT_EVENT_DB = Path.home() / ".config/command-centre/system_events.db"


class SystemEventStore:
    def __init__(self, path=DEFAULT_EVENT_DB):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.parent.chmod(0o700)
        self.db = sqlite3.connect(path, check_same_thread=False)
        path.chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY, created_utc TEXT NOT NULL,
                category TEXT NOT NULL, severity TEXT NOT NULL,
                source_app TEXT NOT NULL, event_type TEXT NOT NULL,
                title TEXT NOT NULL, detail TEXT DEFAULT '',
                evidence_json TEXT DEFAULT '{}', action_id TEXT DEFAULT '',
                dedupe_key TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_system_events_created ON system_events(created_utc DESC);
            CREATE INDEX IF NOT EXISTS idx_system_events_category ON system_events(category);
            CREATE TABLE IF NOT EXISTS observed_state (
                state_key TEXT PRIMARY KEY, state_value TEXT NOT NULL,
                updated_utc TEXT NOT NULL
            );
        """)
        self.db.execute("DELETE FROM system_events WHERE title IN ('Dashboard monitoring started', 'Telemetry connected')")
        self.db.commit()

    def add(self, category, title, severity="INFO", event_type="state", detail="", evidence=None, action_id="", dedupe_key="", dedupe_seconds=300):
        now_epoch = int(time.time())
        created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_epoch))
        if dedupe_key:
            recent = self.db.execute("SELECT created_utc FROM system_events WHERE dedupe_key=? ORDER BY id DESC LIMIT 1", (dedupe_key,)).fetchone()
            if recent:
                try:
                    previous = calendar.timegm(time.strptime(recent["created_utc"], "%Y-%m-%dT%H:%M:%SZ"))
                    if now_epoch - previous < dedupe_seconds:
                        return False
                except ValueError:
                    pass
        self.db.execute(
            "INSERT INTO system_events(created_utc,category,severity,source_app,event_type,title,detail,evidence_json,action_id,dedupe_key) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (created, category.upper(), severity.upper(), "Command Centre", event_type, title, detail, json.dumps(evidence or {}), action_id, dedupe_key),
        )
        self.db.commit()
        return True

    def recent(self, limit=100, category="ALL"):
        if category == "ALL":
            return self.db.execute("SELECT * FROM system_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return self.db.execute("SELECT * FROM system_events WHERE category=? ORDER BY id DESC LIMIT ?", (category, limit)).fetchall()

    def observed_states(self):
        return {row["state_key"]: row["state_value"] for row in self.db.execute("SELECT state_key,state_value FROM observed_state")}

    def save_observed_states(self, states):
        updated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.db.executemany(
            "INSERT INTO observed_state(state_key,state_value,updated_utc) VALUES(?,?,?) ON CONFLICT(state_key) DO UPDATE SET state_value=excluded.state_value,updated_utc=excluded.updated_utc",
            [(key, json.dumps(value, sort_keys=True), updated) for key, value in states.items()],
        )
        self.db.commit()

    @staticmethod
    def decode_observed_states(states):
        decoded = {}
        for key, value in states.items():
            try:
                decoded[key] = json.loads(value)
            except (TypeError, ValueError):
                decoded[key] = value
        return decoded

    def close(self):
        self.db.close()
