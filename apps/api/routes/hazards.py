"""
Hazard Events Query & Verification Endpoints
Provides public access to assessed hazard events and Cedar-governed responder verification.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from domain.entities import (
    HazardEvent,
    EventStatus,
    Principal,
    RoleType,
    AuditLogEntry,
    Observation,
)
from apps.api.dependencies import (
    get_event_repository,
    get_cedar_engine,
    get_search_manager,
    get_evidence_analyst,
    get_advisory_generator,
    get_current_user,
)
from persistence.repository import EventRepository
from authorization.evaluator import CedarPolicyEngine
from search.opensearch_client import OpenSearchManager
from agents.evidence_analyst import EvidenceAnalystAgent
from agents.advisory_generator import AdvisoryGeneratorAgent

router = APIRouter(prefix="/hazards", tags=["Hazards"])


class VerifyHazardRequest(BaseModel):
    principal_id: str
    principal_role: RoleType
    display_name: str
    badge_number: Optional[str] = None
    agency: Optional[str] = None
    verification_notes: str = Field(..., min_length=3)
    target_status: EventStatus = Field(default=EventStatus.VERIFIED)


@router.get("", response_model=List[Dict[str, Any]])
def list_hazards(
    status_filter: Optional[EventStatus] = Query(default=None, alias="status"),
    repo: EventRepository = Depends(get_event_repository),
):
    events = repo.get_all_hazard_events(status=status_filter)
    return [ev.model_dump(mode="json") for ev in events]


@router.get("/{event_id}", response_model=Dict[str, Any])
def get_hazard_by_id(
    event_id: UUID,
    repo: EventRepository = Depends(get_event_repository),
    analyst: EvidenceAnalystAgent = Depends(get_evidence_analyst),
    advisory_gen: AdvisoryGeneratorAgent = Depends(get_advisory_generator),
):
    event = repo.get_hazard_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hazard event {event_id} not found",
        )

    linked_obs = repo.get_observations_for_event(event.id)
    analysis = (
        analyst.analyze(linked_obs, event.current_assessment)
        if event.current_assessment
        else None
    )
    advisory = (
        advisory_gen.generate(event, event.current_assessment, analysis)
        if event.current_assessment and analysis
        else None
    )

    data = event.model_dump(mode="json")
    if advisory:
        data["commuter_advisory"] = advisory.model_dump(mode="json")
    if analysis:
        data["evidence_analysis"] = analysis.model_dump(mode="json")

    return data


@router.get("/{event_id}/evidence", response_model=Dict[str, Any])
def get_hazard_evidence(
    event_id: UUID,
    repo: EventRepository = Depends(get_event_repository),
):
    event = repo.get_hazard_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hazard event {event_id} not found",
        )

    observations = repo.get_observations_for_event(event.id)
    return {
        "event_id": str(event.id),
        "total_observations": len(observations),
        "provenance": (
            event.current_assessment.provenance.model_dump(mode="json")
            if event.current_assessment
            else None
        ),
        "observations": [o.model_dump(mode="json") for o in observations],
    }


@router.post("/{event_id}/verify", status_code=status.HTTP_200_OK)
def verify_hazard(
    event_id: UUID,
    req: VerifyHazardRequest,
    repo: EventRepository = Depends(get_event_repository),
    cedar: CedarPolicyEngine = Depends(get_cedar_engine),
    search: OpenSearchManager = Depends(get_search_manager),
    current_user: Principal = Depends(get_current_user),
):
    event = repo.get_hazard_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hazard event {event_id} not found",
        )

    # Use authenticated user instead of self-declared principal info
    principal = current_user

    # Override request fields with authenticated user info for security
    req.principal_id = principal.id
    req.principal_role = principal.role
    req.display_name = principal.display_name
    req.badge_number = principal.badge_number
    req.agency = principal.agency

    # 1. AWS Cedar Authorization Boundary Check
    auth_decision = cedar.is_authorized(
        principal=principal,
        action="VerifyHazard",
        resource_type="HazardEvent",
        resource_id=str(event.id),
    )

    # Record in audit log
    repo.record_audit_log(
        AuditLogEntry(
            event_type="CEDAR_VERIFICATION_ATTEMPT",
            principal_id=principal.id,
            action="VerifyHazard",
            resource_id=f"HazardEvent::{event.id}",
            decision=auth_decision.decision,
            details={
                "allowed": auth_decision.allowed,
                "reason": auth_decision.reason,
                "target_status": req.target_status.value,
            },
        )
    )

    if not auth_decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Cedar Policy Denied",
                "message": f"Principal {principal.id} with role {principal.role.value} is not authorized to verify hazards.",
                "diagnostics": auth_decision.diagnostics,
                "reason": auth_decision.reason,
            },
        )

    # Apply Verified Status
    event.status = req.target_status
    event.version += 1
    event.correlation_reason = f"Verified by {principal.display_name} ({req.agency or 'Official'}): {req.verification_notes}"
    repo.save_hazard_event(event)
    search.index_event(event)

    return {
        "status": "VERIFIED",
        "event_id": str(event.id),
        "new_status": event.status.value,
        "cedar_decision": auth_decision.decision,
        "verified_by": principal.display_name,
    }
