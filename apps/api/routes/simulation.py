"""
Simulation Management Endpoints
Provides control over the simulated time clock and deterministic scenario demonstrations.
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from domain.entities import Principal, RoleType, AuditLogEntry
from apps.api.dependencies import get_simulation_manager, get_cedar_engine, get_event_repository
from simulation.scenario_runner import SimulationScenarioManager
from authorization.evaluator import CedarPolicyEngine
from persistence.repository import EventRepository

router = APIRouter(prefix="/simulation", tags=["Simulation"])


class AdvanceTimeRequest(BaseModel):
    minutes: float = Field(..., gt=0.0, le=1440.0, description="Minutes to advance simulated clock")
    principal_id: str = Field(default="authority_admin")
    principal_role: RoleType = Field(default=RoleType.OFFICIAL_AUTHORITY)


@router.get("/state", response_model=Dict[str, Any])
def get_simulation_state(
    sim: SimulationScenarioManager = Depends(get_simulation_manager),
):
    return {
        "current_sim_time": sim.current_sim_time.isoformat(),
        "scenario_state": sim.scenario_state,
    }


@router.post("/reset", response_model=Dict[str, Any])
def reset_simulation(
    sim: SimulationScenarioManager = Depends(get_simulation_manager),
):
    return sim.reset_simulation()


@router.post("/time", response_model=Dict[str, Any])
def advance_simulated_time(
    req: AdvanceTimeRequest,
    sim: SimulationScenarioManager = Depends(get_simulation_manager),
    cedar: CedarPolicyEngine = Depends(get_cedar_engine),
    repo: EventRepository = Depends(get_event_repository),
):
    principal = Principal(id=req.principal_id, role=req.principal_role, display_name="Admin")
    auth = cedar.is_authorized(principal, "AdvanceSimulationTime", "SystemResource", "clock")

    repo.record_audit_log(
        AuditLogEntry(
            event_type="SIMULATION_TIME_ADVANCE",
            principal_id=principal.id,
            action="AdvanceSimulationTime",
            resource_id="SystemResource::clock",
            decision=auth.decision,
            details={"minutes": req.minutes, "reason": auth.reason},
        )
    )

    if not auth.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Cedar Denied", "reason": auth.reason},
        )

    return sim.advance_time(req.minutes)


@router.post("/step", response_model=Dict[str, Any])
def execute_next_scenario_step(
    sim: SimulationScenarioManager = Depends(get_simulation_manager),
):
    return sim.execute_next_scenario_step()
