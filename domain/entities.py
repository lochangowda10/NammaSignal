"""
NammaSignal Domain Entities & Value Objects
Enterprise-grade domain modeling with immutability, auditability, and validation.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceType(str, Enum):
    CITIZEN = "CITIZEN"
    VERIFIED_RESPONDER = "VERIFIED_RESPONDER"
    OFFICIAL_AUTHORITY = "OFFICIAL_AUTHORITY"
    SENSOR = "SENSOR"


class EvidenceType(str, Enum):
    GROUND_OBSERVATION = "GROUND_OBSERVATION"
    PHOTO = "PHOTO"
    OFFICIAL_ADVISORY = "OFFICIAL_ADVISORY"
    SENSOR_TELEMETRY = "SENSOR_TELEMETRY"
    TRAFFIC_UPDATE = "TRAFFIC_UPDATE"
    CLEARANCE_REPORT = "CLEARANCE_REPORT"


class HazardType(str, Enum):
    WATERLOGGING = "WATERLOGGING"
    ROADBLOCK = "ROADBLOCK"
    FALLEN_TREE = "FALLEN_TREE"
    SEWAGE_OVERFLOW = "SEWAGE_OVERFLOW"
    POTHOLE_DAMAGE = "POTHOLE_DAMAGE"
    CLEARANCE = "CLEARANCE"


class SeverityLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskLevel(str, Enum):
    LOW = "LOW"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNCERTAIN = "UNCERTAIN"
    CLEARED = "CLEARED"


class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class FreshnessLevel(str, Enum):
    FRESH = "FRESH"          # < 15 minutes old
    MODERATE = "MODERATE"    # 15 - 45 minutes old
    AGING = "AGING"          # 45 - 90 minutes old
    STALE = "STALE"          # > 90 minutes old


class EventStatus(str, Enum):
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    VERIFIED = "VERIFIED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class RoleType(str, Enum):
    CITIZEN = "Citizen"
    VERIFIED_RESPONDER = "VerifiedResponder"
    OFFICIAL_AUTHORITY = "OfficialAuthority"
    SYSTEM = "System"


class Principal(BaseModel):
    """Represents the acting entity in the system."""
    id: str
    role: RoleType
    display_name: str
    badge_number: Optional[str] = None
    agency: Optional[str] = None  # e.g., "BTP", "BBMP", "KSNDMC"


class GeoPoint(BaseModel):
    """Geographic coordinate representation."""
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    landmark_name: Optional[str] = None
    accuracy_meters: Optional[float] = Field(default=20.0, ge=0.0)

    @property
    def coordinates(self) -> tuple[float, float]:
        return self.latitude, self.longitude


class Observation(BaseModel):
    """
    An immutable atomic piece of ground-truth evidence submitted by a principal.
    """
    id: UUID = Field(default_factory=uuid4)
    source_id: str
    source_type: SourceType
    evidence_type: EvidenceType
    hazard_type: HazardType
    severity_observation: SeverityLevel
    location: GeoPoint
    raw_content: str
    media_url: Optional[str] = None
    observed_at: datetime = Field(default_factory=utc_now)
    ingested_at: datetime = Field(default_factory=utc_now)
    is_simulated: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("raw_content")
    @classmethod
    def sanitize_raw_content(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Observation raw_content cannot be empty.")
        if len(cleaned) > 2000:
            raise ValueError("Observation raw_content exceeds 2000 characters limit.")
        return cleaned


class ProvenanceSummary(BaseModel):
    """Granular evidence provenance breakdown behind an assessment."""
    total_evidence_count: int
    active_evidence_count: int
    stale_evidence_count: int
    independent_sources_count: int
    authority_reports_count: int
    verified_responder_count: int
    citizen_reports_count: int
    photos_count: int
    sensors_count: int
    evidence_modalities: List[str]
    supporting_observations: List[UUID]
    contradicting_observations: List[UUID]
    last_evidence_time: Optional[datetime] = None
    oldest_active_evidence_time: Optional[datetime] = None


class Assessment(BaseModel):
    """
    The current evaluated assessment of a HazardEvent, with full provenance and time decay.
    """
    event_id: UUID
    hazard_type: HazardType
    risk_level: RiskLevel
    confidence_level: ConfidenceLevel
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Calibrated deterministic evidence score [0, 1]")
    freshness_status: FreshnessLevel
    minutes_since_last_evidence: float
    summary_advisory: str
    provenance: ProvenanceSummary
    evaluated_at: datetime = Field(default_factory=utc_now)


class HazardEvent(BaseModel):
    """
    A cluster of observations correlated across space, time, and semantics.
    """
    id: UUID = Field(default_factory=uuid4)
    primary_location: GeoPoint
    boundary_radius_meters: float = Field(default=300.0, ge=50.0, le=5000.0)
    hazard_type: HazardType
    status: EventStatus = Field(default=EventStatus.ACTIVE)
    first_observed_at: datetime = Field(default_factory=utc_now)
    last_observed_at: datetime = Field(default_factory=utc_now)
    observation_ids: List[UUID] = Field(default_factory=list)
    correlation_reason: str = Field(default="Initial observation cluster")
    version: int = Field(default=1, ge=1)
    current_assessment: Optional[Assessment] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuditLogEntry(BaseModel):
    """Immutable audit record for authorization decisions, event state changes, and agent reasoning."""
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=utc_now)
    event_type: str  # e.g., "CEDAR_EVALUATION", "EVENT_CORRELATED", "STATUS_CHANGE"
    principal_id: str
    action: str
    resource_id: str
    decision: str    # "ALLOW", "DENY", "EXECUTED"
    details: Dict[str, Any] = Field(default_factory=dict)
