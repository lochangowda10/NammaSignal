"""
NammaSignal Persistence Layer
Transactional SQLite storage engine with WAL mode and ACID guarantees.
"""

import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger("nammasignal.persistence")

DEFAULT_DB_PATH = Path(__file__).parent / "nammasignal.db"


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    hazard_type TEXT NOT NULL,
    severity_observation TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    landmark_name TEXT,
    accuracy_meters REAL,
    raw_content TEXT NOT NULL,
    media_url TEXT,
    observed_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    is_simulated INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_obs_hazard ON observations(hazard_type);
CREATE INDEX IF NOT EXISTS idx_obs_time ON observations(observed_at);
CREATE INDEX IF NOT EXISTS idx_obs_source ON observations(source_id);

CREATE TABLE IF NOT EXISTS hazard_events (
    id TEXT PRIMARY KEY,
    primary_latitude REAL NOT NULL,
    primary_longitude REAL NOT NULL,
    landmark_name TEXT,
    boundary_radius_meters REAL NOT NULL,
    hazard_type TEXT NOT NULL,
    status TEXT NOT NULL,
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    correlation_reason TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    current_assessment_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_status ON hazard_events(status);
CREATE INDEX IF NOT EXISTS idx_event_hazard ON hazard_events(hazard_type);
CREATE INDEX IF NOT EXISTS idx_event_updated ON hazard_events(updated_at);

CREATE TABLE IF NOT EXISTS event_observations (
    event_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    PRIMARY KEY (event_id, observation_id),
    FOREIGN KEY(event_id) REFERENCES hazard_events(id) ON DELETE CASCADE,
    FOREIGN KEY(observation_id) REFERENCES observations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_principal ON audit_logs(principal_id);
"""


class DatabaseManager:
    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            self.db_path = DEFAULT_DB_PATH
        elif str(db_path) == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
        self._initialize_schema()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_schema(self) -> None:
        conn = self.get_connection()
        try:
            with conn:
                conn.executescript(SCHEMA_SQL)
            logger.info("Initialized NammaSignal database at: %s", self.db_path)
        finally:
            conn.close()
