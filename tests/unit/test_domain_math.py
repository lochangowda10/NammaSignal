"""
Unit tests for NammaSignal Domain Logic, Time Decay, and Evidence Fusion.
"""

from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest

from domain.entities import (
    Observation,
    GeoPoint,
    HazardType,
    SourceType,
    EvidenceType,
    SeverityLevel,
    RiskLevel,
    ConfidenceLevel,
    FreshnessLevel,
)
from domain.time_decay import (
    calculate_time_weight,
    calculate_age_minutes,
    determine_freshness_level,
    is_observation_stale,
)
from domain.evidence_fusion import evaluate_hazard_event
from domain.correlation import (
    haversine_distance_meters,
    EventCorrelationEngine,
)
from domain.gazetteer import resolve_landmark


def test_time_decay_exact_half_life():
    now = datetime.now(timezone.utc)
    t_30m_ago = now - timedelta(minutes=30)
    
    # Half-life for WATERLOGGING is 30m, so weight at 30m should be exactly 0.50
    weight = calculate_time_weight(t_30m_ago, HazardType.WATERLOGGING, evaluation_time=now)
    assert pytest.approx(weight, 0.01) == 0.50

    # At 60m (2 half-lives), weight should be 0.25
    t_60m_ago = now - timedelta(minutes=60)
    weight_60 = calculate_time_weight(t_60m_ago, HazardType.WATERLOGGING, evaluation_time=now)
    assert pytest.approx(weight_60, 0.01) == 0.25

    # At 120m (4 half-lives), should be stale
    t_120m_ago = now - timedelta(minutes=120)
    assert is_observation_stale(t_120m_ago, HazardType.WATERLOGGING, evaluation_time=now)


def test_gazetteer_resolution():
    text = "Heavy waterlogging near Silk Board Underpass, traffic blocked"
    pt = resolve_landmark(text)
    assert pt is not None
    assert "Silk Board" in pt.landmark_name
    assert pytest.approx(pt.latitude, 0.001) == 12.9176
    assert pytest.approx(pt.longitude, 0.001) == 77.6238


def test_haversine_distance_calculation():
    # Silk Board (12.9176, 77.6238) to nearby point (~200m away)
    p1 = GeoPoint(latitude=12.9176, longitude=77.6238)
    p2 = GeoPoint(latitude=12.9190, longitude=77.6238)
    dist = haversine_distance_meters(p1, p2)
    assert 140.0 < dist < 170.0


def test_corroboration_increases_confidence():
    event_id = uuid4()
    now = datetime.now(timezone.utc)
    loc = GeoPoint(latitude=12.9176, longitude=77.6238, landmark_name="Silk Board")

    obs1 = Observation(
        source_id="citizen_1",
        source_type=SourceType.CITIZEN,
        evidence_type=EvidenceType.GROUND_OBSERVATION,
        hazard_type=HazardType.WATERLOGGING,
        severity_observation=SeverityLevel.HIGH,
        location=loc,
        raw_content="Knee deep water near silk board",
        observed_at=now,
    )

    assessment1 = evaluate_hazard_event(event_id, HazardType.WATERLOGGING, [obs1], now)
    # Single citizen report -> should be low or elevated, not critical
    assert assessment1.confidence_level in [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM]
    assert assessment1.risk_level in [RiskLevel.LOW, RiskLevel.ELEVATED]

    # Add second independent report with photo
    obs2 = Observation(
        source_id="citizen_2",
        source_type=SourceType.CITIZEN,
        evidence_type=EvidenceType.PHOTO,
        hazard_type=HazardType.WATERLOGGING,
        severity_observation=SeverityLevel.HIGH,
        location=loc,
        raw_content="Photo of water accumulation",
        observed_at=now,
    )

    assessment2 = evaluate_hazard_event(event_id, HazardType.WATERLOGGING, [obs1, obs2], now)
    assert assessment2.confidence_score > assessment1.confidence_score
    assert assessment2.confidence_level in [ConfidenceLevel.HIGH, ConfidenceLevel.VERY_HIGH]


def test_clearance_reduces_hazard():
    event_id = uuid4()
    now = datetime.now(timezone.utc)
    loc = GeoPoint(latitude=12.9176, longitude=77.6238, landmark_name="Silk Board")

    obs1 = Observation(
        source_id="citizen_1",
        source_type=SourceType.CITIZEN,
        evidence_type=EvidenceType.GROUND_OBSERVATION,
        hazard_type=HazardType.WATERLOGGING,
        severity_observation=SeverityLevel.HIGH,
        location=loc,
        raw_content="Waterlogged road",
        observed_at=now - timedelta(minutes=45),
    )

    # Authorized responder reports water has drained
    obs_clear = Observation(
        source_id="responder_warden_1",
        source_type=SourceType.VERIFIED_RESPONDER,
        evidence_type=EvidenceType.CLEARANCE_REPORT,
        hazard_type=HazardType.CLEARANCE,
        severity_observation=SeverityLevel.NONE,
        location=loc,
        raw_content="Water pumped out, traffic moving smoothly",
        observed_at=now - timedelta(minutes=2),
    )

    assessment = evaluate_hazard_event(event_id, HazardType.WATERLOGGING, [obs1, obs_clear], now)
    assert assessment.risk_level == RiskLevel.CLEARED
