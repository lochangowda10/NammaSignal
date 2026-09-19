"""
NammaSignal Transactional Repository
Pure Python domain repository handling persistence for observations, hazard events, and audit logs.
"""

from datetime import datetime, timezone
import json
import sqlite3
from typing import List, Optional
from uuid import UUID

from domain.entities import (
    Observation,
    HazardEvent,
    Assessment,
    AuditLogEntry,
    GeoPoint,
    HazardType,
    EventStatus,
    SourceType,
    EvidenceType,
    SeverityLevel,
)
from persistence.database import DatabaseManager


class EventRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    # --------------------------------------------------------------------------
    # Observation Methods
    # --------------------------------------------------------------------------
    def save_observation(self, obs: Observation) -> None:
        conn = self.db.get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO observations (
                        id, source_id, source_type, evidence_type, hazard_type,
                        severity_observation, latitude, longitude, landmark_name,
                        accuracy_meters, raw_content, media_url, observed_at,
                        ingested_at, is_simulated, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(obs.id),
                        obs.source_id,
                        obs.source_type.value,
                        obs.evidence_type.value,
                        obs.hazard_type.value,
                        obs.severity_observation.value,
                        obs.location.latitude,
                        obs.location.longitude,
                        obs.location.landmark_name,
                        obs.location.accuracy_meters,
                        obs.raw_content,
                        obs.media_url,
                        obs.observed_at.isoformat(),
                        obs.ingested_at.isoformat(),
                        1 if obs.is_simulated else 0,
                        json.dumps(obs.metadata),
                    ),
                )
        finally:
            conn.close()

    def get_observation(self, obs_id: UUID | str) -> Optional[Observation]:
        conn = self.db.get_connection()
        try:
            cur = conn.execute("SELECT * FROM observations WHERE id = ?", (str(obs_id),))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_observation(row)
        finally:
            conn.close()

    def get_observations_for_event(self, event_id: UUID | str) -> List[Observation]:
        conn = self.db.get_connection()
        try:
            cur = conn.execute(
                """
                SELECT o.* FROM observations o
                INNER JOIN event_observations eo ON o.id = eo.observation_id
                WHERE eo.event_id = ?
                ORDER BY o.observed_at ASC
                """,
                (str(event_id),),
            )
            return [self._row_to_observation(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # HazardEvent Methods
    # --------------------------------------------------------------------------
    def save_hazard_event(self, event: HazardEvent) -> None:
        conn = self.db.get_connection()
        try:
            assessment_json = (
                event.current_assessment.model_dump_json()
                if event.current_assessment
                else None
            )
            with conn:
                conn.execute(
                    """
                    INSERT INTO hazard_events (
                        id, primary_latitude, primary_longitude, landmark_name,
                        boundary_radius_meters, hazard_type, status,
                        first_observed_at, last_observed_at, correlation_reason,
                        version, current_assessment_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        primary_latitude = excluded.primary_latitude,
                        primary_longitude = excluded.primary_longitude,
                        landmark_name = excluded.landmark_name,
                        boundary_radius_meters = excluded.boundary_radius_meters,
                        status = excluded.status,
                        first_observed_at = excluded.first_observed_at,
                        last_observed_at = excluded.last_observed_at,
                        correlation_reason = excluded.correlation_reason,
                        version = excluded.version,
                        current_assessment_json = excluded.current_assessment_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        str(event.id),
                        event.primary_location.latitude,
                        event.primary_location.longitude,
                        event.primary_location.landmark_name,
                        event.boundary_radius_meters,
                        event.hazard_type.value,
                        event.status.value,
                        event.first_observed_at.isoformat(),
                        event.last_observed_at.isoformat(),
                        event.correlation_reason,
                        event.version,
                        assessment_json,
                        event.created_at.isoformat(),
                        event.updated_at.isoformat(),
                    ),
                )

                # Sync event_observations link table
                for obs_id in event.observation_ids:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO event_observations (event_id, observation_id)
                        VALUES (?, ?)
                        """,
                        (str(event.id), str(obs_id)),
                    )
        finally:
            conn.close()

    def get_hazard_event(self, event_id: UUID | str) -> Optional[HazardEvent]:
        conn = self.db.get_connection()
        try:
            cur = conn.execute("SELECT * FROM hazard_events WHERE id = ?", (str(event_id),))
            row = cur.fetchone()
            if not row:
                return None

            # Fetch linked observation IDs
            obs_cur = conn.execute(
                "SELECT observation_id FROM event_observations WHERE event_id = ?",
                (str(event_id),),
            )
            obs_ids = [UUID(r["observation_id"]) for r in obs_cur.fetchall()]

            return self._row_to_hazard_event(row, obs_ids)
        finally:
            conn.close()

    def get_all_hazard_events(self, status: Optional[EventStatus] = None) -> List[HazardEvent]:
        conn = self.db.get_connection()
        try:
            if status:
                cur = conn.execute(
                    "SELECT * FROM hazard_events WHERE status = ? ORDER BY updated_at DESC",
                    (status.value,),
                )
            else:
                cur = conn.execute("SELECT * FROM hazard_events ORDER BY updated_at DESC")

            rows = cur.fetchall()
            events = []
            for row in rows:
                obs_cur = conn.execute(
                    "SELECT observation_id FROM event_observations WHERE event_id = ?",
                    (row["id"],),
                )
                obs_ids = [UUID(r["observation_id"]) for r in obs_cur.fetchall()]
                events.append(self._row_to_hazard_event(row, obs_ids))
            return events
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Audit Log Methods
    # --------------------------------------------------------------------------
    def record_audit_log(self, entry: AuditLogEntry) -> None:
        conn = self.db.get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO audit_logs (
                        id, timestamp, event_type, principal_id, action,
                        resource_id, decision, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(entry.id),
                        entry.timestamp.isoformat(),
                        entry.event_type,
                        entry.principal_id,
                        entry.action,
                        entry.resource_id,
                        entry.decision,
                        json.dumps(entry.details),
                    ),
                )
        finally:
            conn.close()

    def get_audit_logs(self, limit: int = 50) -> List[AuditLogEntry]:
        conn = self.db.get_connection()
        try:
            cur = conn.execute(
                "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            logs = []
            for r in cur.fetchall():
                logs.append(
                    AuditLogEntry(
                        id=UUID(r["id"]),
                        timestamp=datetime.fromisoformat(r["timestamp"]),
                        event_type=r["event_type"],
                        principal_id=r["principal_id"],
                        action=r["action"],
                        resource_id=r["resource_id"],
                        decision=r["decision"],
                        details=json.loads(r["details_json"]),
                    )
                )
            return logs
        finally:
            conn.close()

    def reset_database(self) -> None:
        """Clears all transactional tables for deterministic simulation resets and testing."""
        conn = self.db.get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM event_observations")
                conn.execute("DELETE FROM hazard_events")
                conn.execute("DELETE FROM observations")
                conn.execute("DELETE FROM audit_logs")
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # Deserialization Helpers
    # --------------------------------------------------------------------------
    @staticmethod
    def _row_to_observation(row: sqlite3.Row) -> Observation:
        return Observation(
            id=UUID(row["id"]),
            source_id=row["source_id"],
            source_type=SourceType(row["source_type"]),
            evidence_type=EvidenceType(row["evidence_type"]),
            hazard_type=HazardType(row["hazard_type"]),
            severity_observation=SeverityLevel(row["severity_observation"]),
            location=GeoPoint(
                latitude=row["latitude"],
                longitude=row["longitude"],
                landmark_name=row["landmark_name"],
                accuracy_meters=row["accuracy_meters"],
            ),
            raw_content=row["raw_content"],
            media_url=row["media_url"],
            observed_at=datetime.fromisoformat(row["observed_at"]),
            ingested_at=datetime.fromisoformat(row["ingested_at"]),
            is_simulated=bool(row["is_simulated"]),
            metadata=json.loads(row["metadata_json"]),
        )

    @staticmethod
    def _row_to_hazard_event(row: sqlite3.Row, obs_ids: List[UUID]) -> HazardEvent:
        assessment = None
        if row["current_assessment_json"]:
            assessment = Assessment.model_validate_json(row["current_assessment_json"])

        return HazardEvent(
            id=UUID(row["id"]),
            primary_location=GeoPoint(
                latitude=row["primary_latitude"],
                longitude=row["primary_longitude"],
                landmark_name=row["landmark_name"],
            ),
            boundary_radius_meters=row["boundary_radius_meters"],
            hazard_type=HazardType(row["hazard_type"]),
            status=EventStatus(row["status"]),
            first_observed_at=datetime.fromisoformat(row["first_observed_at"]),
            last_observed_at=datetime.fromisoformat(row["last_observed_at"]),
            observation_ids=obs_ids,
            correlation_reason=row["correlation_reason"],
            version=row["version"],
            current_assessment=assessment,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
