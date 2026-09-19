"""
NammaSignal Deterministic Simulation Runner
Provides a step-by-step simulation demonstrating evidence fusion,
independent corroboration, Cedar authorization, time decay, and hazard clearance.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from domain.entities import (
    Observation,
    Principal,
    RoleType,
    SourceType,
    EvidenceType,
    HazardType,
    SeverityLevel,
    GeoPoint,
    HazardEvent,
    EventStatus,
)
from domain.time_decay import calculate_time_weight
from domain.evidence_fusion import evaluate_hazard_event
from domain.correlation import EventCorrelationEngine
from authorization.evaluator import CedarPolicyEngine
from persistence.repository import EventRepository
from search.opensearch_client import OpenSearchManager
from agents.observation_interpreter import ObservationInterpreterAgent
from agents.evidence_analyst import EvidenceAnalystAgent
from agents.advisory_generator import AdvisoryGeneratorAgent


class SimulationScenarioManager:
    """
    Orchestrates deterministic scenarios for live hackathon demos.
    Clearly tags all simulated observations as IS_SIMULATED = True.
    """

    def __init__(
        self,
        repository: EventRepository,
        search_manager: OpenSearchManager,
        cedar_engine: CedarPolicyEngine,
    ):
        self.repo = repository
        self.search = search_manager
        self.cedar = cedar_engine
        self.correlation_engine = EventCorrelationEngine()
        self.interpreter = ObservationInterpreterAgent()
        self.analyst = EvidenceAnalystAgent()
        self.advisory_gen = AdvisoryGeneratorAgent()

        # Simulated Clock (defaults to current real time)
        self.current_sim_time = datetime.now(timezone.utc)
        self.scenario_state = {
            "name": "silk_board_cloudburst",
            "current_step": 0,
            "total_steps": 5,
            "active_event_id": None,
        }

    def reset_simulation(self) -> Dict[str, Any]:
        """Resets the simulation clock and database state for deterministic demonstration."""
        self.current_sim_time = datetime.now(timezone.utc)
        self.scenario_state["current_step"] = 0
        self.scenario_state["active_event_id"] = None
        self.repo.reset_database()
        self.search.memory_fallback.clear()
        return {
            "status": "RESET",
            "sim_time": self.current_sim_time.isoformat(),
            "step": 0,
            "message": "Simulation clock and database reset to baseline.",
        }

    def advance_time(self, minutes: float) -> Dict[str, Any]:
        """Advances the simulated clock and re-evaluates all active and verified events."""
        self.current_sim_time += timedelta(minutes=minutes)

        # Re-evaluate all ongoing events under the new time horizon
        all_events = self.repo.get_all_hazard_events()
        active_events = [
            ev for ev in all_events
            if ev.status not in [EventStatus.DISMISSED, EventStatus.RESOLVED]
        ]
        updated_assessments = []

        for event in active_events:
            linked_obs = self.repo.get_observations_for_event(event.id)
            new_assessment = evaluate_hazard_event(
                event_id=event.id,
                hazard_type=event.hazard_type,
                observations=linked_obs,
                evaluation_time=self.current_sim_time,
            )
            event.current_assessment = new_assessment
            self.repo.save_hazard_event(event)
            self.search.index_event(event)
            updated_assessments.append({
                "event_id": str(event.id),
                "risk_level": new_assessment.risk_level.value,
                "confidence_level": new_assessment.confidence_level.value,
                "confidence_score": new_assessment.confidence_score,
                "freshness_status": new_assessment.freshness_status.value,
                "minutes_since_last": new_assessment.minutes_since_last_evidence,
            })

        return {
            "status": "TIME_ADVANCED",
            "advanced_by_minutes": minutes,
            "new_sim_time": self.current_sim_time.isoformat(),
            "updated_events": updated_assessments,
        }

    def execute_next_scenario_step(self) -> Dict[str, Any]:
        """
        Steps through the canonical Silk Board Cloudburst demonstration:
          Step 1: First unverified citizen report -> LOW/UNCERTAIN
          Step 2: Second independent report + photo -> HIGH corroboration
          Step 3: Verified Responder arrives & verifies -> Cedar ALLOW
          Step 4: Advance time by 60 mins -> Freshness decays to AGING
          Step 5: Road clearance report -> State transitions to CLEARED
        """
        step = self.scenario_state["current_step"] + 1

        loc = GeoPoint(
            latitude=12.9176,
            longitude=77.6238,
            landmark_name="Silk Board Junction & Underpass",
        )

        if step == 1:
            # Step 1: Single Citizen Text Report
            principal = Principal(id="citizen_ravi", role=RoleType.CITIZEN, display_name="Ravi K")
            raw_text = "Water is accumulating near Silk Board underpass, cars starting to slow down"
            
            # 1. Cedar check
            auth = self.cedar.is_authorized(principal, "SubmitObservation", "Observation")
            obs = Observation(
                source_id=principal.id,
                source_type=SourceType.CITIZEN,
                evidence_type=EvidenceType.GROUND_OBSERVATION,
                hazard_type=HazardType.WATERLOGGING,
                severity_observation=SeverityLevel.MEDIUM,
                location=loc,
                raw_content=raw_text,
                observed_at=self.current_sim_time,
                is_simulated=True,
                metadata={"source_channel": "SIMULATED_CITIZEN_APP"},
            )
            self.repo.save_observation(obs)

            event = self.correlation_engine.create_new_event(obs)
            assessment = evaluate_hazard_event(event.id, event.hazard_type, [obs], self.current_sim_time)
            event.current_assessment = assessment
            self.repo.save_hazard_event(event)
            self.search.index_event(event)

            self.scenario_state["active_event_id"] = str(event.id)
            self.scenario_state["current_step"] = 1

            return {
                "step": 1,
                "title": "Step 1: Isolated Citizen Observation",
                "description": "A single citizen reports water accumulation. System marks risk as ELEVATED/UNCERTAIN awaiting corroboration.",
                "cedar_decision": auth.decision,
                "cedar_reason": auth.reason,
                "event_id": str(event.id),
                "risk_level": assessment.risk_level.value,
                "confidence_level": assessment.confidence_level.value,
                "confidence_score": assessment.confidence_score,
                "advisory": assessment.summary_advisory,
            }

        elif step == 2:
            # Step 2: Second Independent Citizen + Photo
            self.current_sim_time += timedelta(minutes=4)
            event_id = self.scenario_state["active_event_id"]
            event = self.repo.get_hazard_event(event_id)
            principal = Principal(id="citizen_ananya", role=RoleType.CITIZEN, display_name="Ananya S")
            raw_text = "Underpass is flooded! Knee deep water, vehicles are turning back."
            
            auth = self.cedar.is_authorized(principal, "SubmitObservation", "Observation")
            obs = Observation(
                source_id=principal.id,
                source_type=SourceType.CITIZEN,
                evidence_type=EvidenceType.PHOTO,
                hazard_type=HazardType.WATERLOGGING,
                severity_observation=SeverityLevel.HIGH,
                location=loc,
                raw_content=raw_text,
                media_url="https://images.unsplash.com/photo-1547683905-f686c993aae5?auto=format&fit=crop&w=800&q=80",
                observed_at=self.current_sim_time,
                is_simulated=True,
                metadata={"source_channel": "SIMULATED_TWITTER_FEED"},
            )
            self.repo.save_observation(obs)
            event = self.correlation_engine.attach_observation_to_event(event, obs)

            linked_obs = [self.repo.get_observation(oid) for oid in event.observation_ids]
            linked_obs = [o for o in linked_obs if o is not None]
            assessment = evaluate_hazard_event(event.id, event.hazard_type, linked_obs, self.current_sim_time)
            event.current_assessment = assessment
            self.repo.save_hazard_event(event)
            self.search.index_event(event)

            self.scenario_state["current_step"] = 2

            return {
                "step": 2,
                "title": "Step 2: Multi-Source Corroboration + Photo Evidence",
                "description": "Second independent source submits a geotagged photo. Non-linear corroboration elevates confidence to HIGH.",
                "cedar_decision": auth.decision,
                "event_id": str(event.id),
                "risk_level": assessment.risk_level.value,
                "confidence_level": assessment.confidence_level.value,
                "confidence_score": assessment.confidence_score,
                "advisory": assessment.summary_advisory,
                "provenance": assessment.provenance.model_dump(),
            }

        elif step == 3:
            # Step 3: Verified Responder Verification via Cedar
            self.current_sim_time += timedelta(minutes=4)
            event_id = self.scenario_state["active_event_id"]
            event = self.repo.get_hazard_event(event_id)
            responder = Principal(
                id="btp_officer_gowda",
                role=RoleType.VERIFIED_RESPONDER,
                display_name="Sub-Inspector Gowda",
                agency="Bengaluru Traffic Police",
            )
            
            # Cedar Check for VerifyHazard
            auth = self.cedar.is_authorized(responder, "VerifyHazard", "HazardEvent", str(event.id))
            
            obs = Observation(
                source_id=responder.id,
                source_type=SourceType.VERIFIED_RESPONDER,
                evidence_type=EvidenceType.OFFICIAL_ADVISORY,
                hazard_type=HazardType.WATERLOGGING,
                severity_observation=SeverityLevel.HIGH,
                location=loc,
                raw_content="BTP on site: Underpass closed, traffic diverted to service road",
                observed_at=self.current_sim_time,
                is_simulated=True,
                metadata={"badge": "BTP-9082"},
            )
            self.repo.save_observation(obs)
            event.status = EventStatus.VERIFIED
            event = self.correlation_engine.attach_observation_to_event(event, obs)

            linked_obs = [self.repo.get_observation(oid) for oid in event.observation_ids]
            linked_obs = [o for o in linked_obs if o is not None]
            assessment = evaluate_hazard_event(event.id, event.hazard_type, linked_obs, self.current_sim_time)
            event.current_assessment = assessment
            self.repo.save_hazard_event(event)
            self.search.index_event(event)

            self.scenario_state["current_step"] = 3

            return {
                "step": 3,
                "title": "Step 3: Official Verification (Cedar Policy Evaluation)",
                "description": "Verified Traffic Police responder confirms flood status. AWS Cedar evaluates and GRANTS verification action.",
                "cedar_decision": auth.decision,
                "cedar_reason": auth.reason,
                "event_id": str(event.id),
                "event_status": event.status.value,
                "risk_level": assessment.risk_level.value,
                "confidence_level": assessment.confidence_level.value,
                "confidence_score": assessment.confidence_score,
                "advisory": assessment.summary_advisory,
            }

        elif step == 4:
            # Step 4: Time Advancement & Exponential Decay
            advance_result = self.advance_time(minutes=75.0)
            event_id = self.scenario_state["active_event_id"]
            event = self.repo.get_hazard_event(event_id)
            assessment = event.current_assessment

            self.scenario_state["current_step"] = 4

            return {
                "step": 4,
                "title": "Step 4: Time Decay in Action",
                "description": "Simulation clock advanced by 75 minutes with no new rain. Exponential half-life decay reduces evidence weight.",
                "sim_time": self.current_sim_time.isoformat(),
                "event_id": str(event.id),
                "risk_level": assessment.risk_level.value,
                "confidence_level": assessment.confidence_level.value,
                "confidence_score": assessment.confidence_score,
                "freshness_status": assessment.freshness_status.value,
                "minutes_since_last_evidence": assessment.minutes_since_last_evidence,
                "advisory": assessment.summary_advisory,
            }

        elif step == 5:
            # Step 5: Clearance Observation
            self.current_sim_time += timedelta(minutes=5)
            event_id = self.scenario_state["active_event_id"]
            event = self.repo.get_hazard_event(event_id)
            responder = Principal(
                id="bbmp_warden_kumar",
                role=RoleType.VERIFIED_RESPONDER,
                display_name="BBMP Warden Kumar",
                agency="BBMP SWD Wing",
            )
            
            auth = self.cedar.is_authorized(responder, "SubmitClearance", "HazardEvent", str(event.id))

            obs_clear = Observation(
                source_id=responder.id,
                source_type=SourceType.VERIFIED_RESPONDER,
                evidence_type=EvidenceType.CLEARANCE_REPORT,
                hazard_type=HazardType.CLEARANCE,
                severity_observation=SeverityLevel.NONE,
                location=loc,
                raw_content="Dewatering pump operational. Water cleared, underpass fully passable.",
                observed_at=self.current_sim_time,
                is_simulated=True,
            )
            self.repo.save_observation(obs_clear)
            event.status = EventStatus.RESOLVED
            event = self.correlation_engine.attach_observation_to_event(event, obs_clear)

            linked_obs = [self.repo.get_observation(oid) for oid in event.observation_ids]
            linked_obs = [o for o in linked_obs if o is not None]
            assessment = evaluate_hazard_event(event.id, event.hazard_type, linked_obs, self.current_sim_time)
            event.current_assessment = assessment
            self.repo.save_hazard_event(event)
            self.search.index_event(event)

            self.scenario_state["current_step"] = 5

            return {
                "step": 5,
                "title": "Step 5: Road Clearance & Hazard Resolution",
                "description": "Clearance report cancels out active hazard mass. Assessment flips to CLEARED, informing commuters the road is safe.",
                "cedar_decision": auth.decision,
                "event_id": str(event.id),
                "event_status": event.status.value,
                "risk_level": assessment.risk_level.value,
                "confidence_level": assessment.confidence_level.value,
                "confidence_score": assessment.confidence_score,
                "advisory": assessment.summary_advisory,
                "provenance": assessment.provenance.model_dump(),
            }

        else:
            return {
                "step": step,
                "message": "Scenario completed. Call reset to start again.",
            }
