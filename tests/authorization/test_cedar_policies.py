"""
Exhaustive Authorization Tests for AWS Cedar Policies
Validates server-side zero-trust, RBAC boundaries, and deny-by-default behavior.
"""

import pytest
from domain.entities import Principal, RoleType
from authorization.evaluator import CedarPolicyEngine


@pytest.fixture
def engine():
    return CedarPolicyEngine()


def test_citizen_allowed_to_submit_observation(engine):
    citizen = Principal(id="citizen_lochan", role=RoleType.CITIZEN, display_name="Lochan")
    res = engine.is_authorized(citizen, "SubmitObservation", "Observation", "obs_123")
    assert res.allowed is True
    assert res.decision == "Allow"


def test_citizen_allowed_to_view_hazards(engine):
    citizen = Principal(id="citizen_lochan", role=RoleType.CITIZEN, display_name="Lochan")
    res = engine.is_authorized(citizen, "ViewHazards", "HazardEvent", "event_456")
    assert res.allowed is True
    assert res.decision == "Allow"


def test_citizen_forbidden_to_verify_hazard(engine):
    citizen = Principal(id="citizen_attacker", role=RoleType.CITIZEN, display_name="Attacker")
    res = engine.is_authorized(citizen, "VerifyHazard", "HazardEvent", "event_456")
    assert res.allowed is False
    assert res.decision == "Deny"


def test_citizen_forbidden_to_publish_advisory(engine):
    citizen = Principal(id="citizen_attacker", role=RoleType.CITIZEN, display_name="Attacker")
    res = engine.is_authorized(citizen, "PublishAdvisory", "HazardEvent", "event_456")
    assert res.allowed is False
    assert res.decision == "Deny"


def test_verified_responder_can_verify_hazard(engine):
    responder = Principal(
        id="responder_warden_42",
        role=RoleType.VERIFIED_RESPONDER,
        display_name="Traffic Warden Ramesh",
        agency="BTP",
    )
    res = engine.is_authorized(responder, "VerifyHazard", "HazardEvent", "event_456")
    assert res.allowed is True
    assert res.decision == "Allow"


def test_verified_responder_cannot_dismiss_hazard(engine):
    responder = Principal(
        id="responder_warden_42",
        role=RoleType.VERIFIED_RESPONDER,
        display_name="Traffic Warden Ramesh",
    )
    res = engine.is_authorized(responder, "DismissHazard", "HazardEvent", "event_456")
    assert res.allowed is False
    assert res.decision == "Deny"


def test_official_authority_has_full_operational_privileges(engine):
    authority = Principal(
        id="btp_inspector_kumar",
        role=RoleType.OFFICIAL_AUTHORITY,
        display_name="Inspector Kumar",
        agency="BTP Control Room",
    )
    # Authority can verify
    assert engine.is_authorized(authority, "VerifyHazard", "HazardEvent", "event_1").allowed is True
    # Authority can publish official advisory
    assert engine.is_authorized(authority, "PublishAdvisory", "HazardEvent", "event_1").allowed is True
    # Authority can dismiss
    assert engine.is_authorized(authority, "DismissHazard", "HazardEvent", "event_1").allowed is True
    # Authority can advance simulation time
    assert engine.is_authorized(authority, "AdvanceSimulationTime", "SystemResource", "clock").allowed is True


def test_system_role_evaluation_actions(engine):
    system_agent = Principal(
        id="nammasignal_core_evaluator",
        role=RoleType.SYSTEM,
        display_name="Core Evaluator Agent",
    )
    assert engine.is_authorized(system_agent, "EvaluateAssessment", "HazardEvent", "event_1").allowed is True
    assert engine.is_authorized(system_agent, "CorrelateEvent", "Observation", "obs_1").allowed is True
    # System agent cannot impersonate official authority
    assert engine.is_authorized(system_agent, "PublishAdvisory", "HazardEvent", "event_1").allowed is False
