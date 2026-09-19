"""
Observation Ingestion Endpoint
Handles validation, Cedar authorization, Strands interpretation, and event correlation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from domain.entities import (
    Observation,
    Principal,
    RoleType,
    SourceType,
    EvidenceType,
    GeoPoint,
    HazardEvent,
    HazardType,
    SeverityLevel,
    AuditLogEntry,
)
from domain.evidence_fusion import evaluate_hazard_event
from apps.api.dependencies import (
    get_event_repository,
    get_cedar_engine,
    get_search_manager,
    get_correlation_engine,
    get_interpreter_agent,
    get_advisory_generator,
    get_evidence_analyst,
)
from persistence.repository import EventRepository
from authorization.evaluator import CedarPolicyEngine
from search.opensearch_client import OpenSearchManager
from domain.correlation import EventCorrelationEngine
from agents.observation_interpreter import ObservationInterpreterAgent
from agents.advisory_generator import AdvisoryGeneratorAgent
from agents.evidence_analyst import EvidenceAnalystAgent

router = APIRouter(prefix="/observations", tags=["Observations"])


class InterpretDryRunRequest(BaseModel):
    """Request for a stateless Strands interpretation preview (no persistence)."""
    raw_content: str = Field(..., min_length=3, max_length=2000)


@router.post("/interpret-dry", response_model=Dict[str, Any])
def interpret_dry_run(
    req: InterpretDryRunRequest,
    interpreter: ObservationInterpreterAgent = Depends(get_interpreter_agent),
):
    """
    Runs Strands Agent 1 (Observation Interpreter) against raw text without
    persisting any observation or mutating hazard state. Read-only preview.
    """
    proposal = interpreter.interpret(req.raw_content)
    return proposal.model_dump(mode="json")


class IngestObservationRequest(BaseModel):
    principal_id: str = Field(default="citizen_anonymous")
    principal_role: RoleType = Field(default=RoleType.CITIZEN)
    display_name: str = Field(default="Bengaluru Citizen")
    raw_content: str = Field(..., min_length=3, max_length=2000)
    source_type: SourceType = Field(default=SourceType.CITIZEN)
    evidence_type: EvidenceType = Field(default=EvidenceType.GROUND_OBSERVATION)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    landmark_name: Optional[str] = None
    media_url: Optional[str] = None
    is_simulated: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("raw_content")
    @classmethod
    def validate_raw_content(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped or len(stripped) < 3:
            raise ValueError("raw_content must contain at least 3 non-whitespace characters.")
        return stripped


class IngestionResponse(BaseModel):
    status: str
    observation_id: str
    event_id: str
    correlation_action: str  # "ATTACHED" or "SPAWNED"
    correlation_reason: str
    cedar_authorization: Dict[str, Any]
    interpreted_proposal: Dict[str, Any]
    updated_assessment: Dict[str, Any]


@router.post("", response_model=IngestionResponse, status_code=status.HTTP_201_CREATED)
def ingest_observation(
    req: IngestObservationRequest,
    repo: EventRepository = Depends(get_event_repository),
    cedar: CedarPolicyEngine = Depends(get_cedar_engine),
    search: OpenSearchManager = Depends(get_search_manager),
    correlation: EventCorrelationEngine = Depends(get_correlation_engine),
    interpreter: ObservationInterpreterAgent = Depends(get_interpreter_agent),
    analyst: EvidenceAnalystAgent = Depends(get_evidence_analyst),
    advisory_gen: AdvisoryGeneratorAgent = Depends(get_advisory_generator),
):
    principal = Principal(
        id=req.principal_id,
        role=req.principal_role,
        display_name=req.display_name,
    )

    # 1. Server-side Cedar Policy Evaluation
    auth_decision = cedar.is_authorized(
        principal=principal,
        action="SubmitObservation",
        resource_type="Observation",
        resource_id="new_ingest",
    )

    # Record Cedar evaluation in audit log
    repo.record_audit_log(
        AuditLogEntry(
            event_type="CEDAR_AUTHORIZATION",
            principal_id=principal.id,
            action="SubmitObservation",
            resource_id="Observation::new_ingest",
            decision=auth_decision.decision,
            details={"allowed": auth_decision.allowed, "reason": auth_decision.reason},
        )
    )

    if not auth_decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Cedar Authorization Denied",
                "reason": auth_decision.reason,
                "diagnostics": auth_decision.diagnostics,
            },
        )

    # 2. Strands Agent: Observation Interpretation
    proposal = interpreter.interpret(req.raw_content, source_evidence_type=req.evidence_type)

    if proposal.is_adversarial_flagged:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "Security Sanitization Triggered",
                "message": proposal.rationale,
            },
        )

    # Resolve location: caller coordinates take priority, otherwise use gazetteer match
    if req.latitude is not None and req.longitude is not None:
        loc = GeoPoint(
            latitude=req.latitude,
            longitude=req.longitude,
            landmark_name=req.landmark_name or proposal.recognized_landmark,
        )
    elif proposal.resolved_location:
        loc = proposal.resolved_location
    else:
        # Fallback to Central Bengaluru if unresolvable
        loc = GeoPoint(
            latitude=12.9716,
            longitude=77.5946,
            landmark_name="Central Bengaluru (Approximate)",
            accuracy_meters=500.0,
        )

    # 3. Create Immutable Observation
    now = datetime.now(timezone.utc)
    obs = Observation(
        source_id=principal.id,
        source_type=req.source_type,
        evidence_type=req.evidence_type,
        hazard_type=proposal.hazard_type,
        severity_observation=proposal.severity_observation,
        location=loc,
        raw_content=req.raw_content,
        media_url=req.media_url,
        observed_at=now,
        ingested_at=now,
        is_simulated=req.is_simulated,
        metadata=req.metadata,
    )
    repo.save_observation(obs)

    # 4. Search nearby active events for correlation
    nearby_events_with_dist = search.search_nearby_events(
        center=loc,
        radius_meters=500.0,
        now=now,
    )
    active_events = [ev for ev, _ in nearby_events_with_dist]

    corr_result = correlation.evaluate_correlation(obs, active_events, evaluation_time=now)

    if corr_result.should_correlate and corr_result.matched_event:
        event = correlation.attach_observation_to_event(corr_result.matched_event, obs)
        action_type = "ATTACHED"
    else:
        event = correlation.create_new_event(obs)
        action_type = "SPAWNED"

    # 5. Deterministic Assessment Evaluation
    linked_observations = repo.get_observations_for_event(event.id)
    # Ensure current observation is included
    if not any(o.id == obs.id for o in linked_observations):
        linked_observations.append(obs)

    assessment = evaluate_hazard_event(
        event_id=event.id,
        hazard_type=event.hazard_type,
        observations=linked_observations,
        evaluation_time=now,
    )
    event.current_assessment = assessment

    # Persist and Index
    repo.save_hazard_event(event)
    search.index_event(event)

    return IngestionResponse(
        status="PROCESSED",
        observation_id=str(obs.id),
        event_id=str(event.id),
        correlation_action=action_type,
        correlation_reason=corr_result.reason,
        cedar_authorization={
            "allowed": auth_decision.allowed,
            "decision": auth_decision.decision,
            "reason": auth_decision.reason,
        },
        interpreted_proposal=proposal.model_dump(mode="json"),
        updated_assessment=assessment.model_dump(mode="json"),
    )
