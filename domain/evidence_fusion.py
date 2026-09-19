"""
NammaSignal Evidence Fusion & Assessment Engine
Deterministic multi-source evidence aggregation, authority weighting,
and calibrated confidence scoring.
"""

from datetime import datetime, timezone
import math
from typing import List, Tuple, Dict, Set
from uuid import UUID

from domain.entities import (
    Observation,
    Assessment,
    ProvenanceSummary,
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


# Base weights by Source Type
SOURCE_WEIGHTS: Dict[SourceType, float] = {
    SourceType.OFFICIAL_AUTHORITY: 1.00,
    SourceType.VERIFIED_RESPONDER: 0.90,
    SourceType.SENSOR: 0.85,
    SourceType.CITIZEN: 0.50,
}

# Modality multiplier bonuses
MEDIA_BONUS = 0.25   # For photo / camera evidence

# Severity weights
SEVERITY_WEIGHTS: Dict[SeverityLevel, float] = {
    SeverityLevel.CRITICAL: 1.00,
    SeverityLevel.HIGH: 0.80,
    SeverityLevel.MEDIUM: 0.50,
    SeverityLevel.LOW: 0.20,
    SeverityLevel.NONE: 0.00,
}


def calculate_single_evidence_weight(
    obs: Observation,
    eval_time: datetime,
) -> float:
    """
    Computes effective weight of an individual observation:
        EffectiveWeight = W_src * W_time * W_severity
    For clearance evidence, severity is not zero-multiplied; weight represents clearance mass.
    """
    w_src = SOURCE_WEIGHTS.get(obs.source_type, 0.40)
    if obs.evidence_type == EvidenceType.PHOTO:
        w_src = min(1.0, w_src + MEDIA_BONUS)
    
    w_time = calculate_time_weight(obs.observed_at, obs.hazard_type, eval_time)
    
    # Clearance reports have full source-authority mass to cancel out hazard
    if obs.hazard_type == HazardType.CLEARANCE or obs.evidence_type == EvidenceType.CLEARANCE_REPORT:
        return w_src * w_time

    w_sev = SEVERITY_WEIGHTS.get(obs.severity_observation, 0.50)
    return w_src * w_time * w_sev


def evaluate_hazard_event(
    event_id: UUID,
    hazard_type: HazardType,
    observations: List[Observation],
    evaluation_time: datetime | None = None,
) -> Assessment:
    """
    Synthesizes all linked observations into a unified, time-aware assessment.
    Guaranteed deterministic and explainable.
    """
    if evaluation_time is None:
        evaluation_time = datetime.now(timezone.utc)
    if evaluation_time.tzinfo is None:
        evaluation_time = evaluation_time.replace(tzinfo=timezone.utc)

    if not observations:
        # Empty assessment baseline
        return Assessment(
            event_id=event_id,
            hazard_type=hazard_type,
            risk_level=RiskLevel.UNCERTAIN,
            confidence_level=ConfidenceLevel.LOW,
            confidence_score=0.0,
            freshness_status=FreshnessLevel.STALE,
            minutes_since_last_evidence=999.0,
            summary_advisory="No evidence recorded for this location.",
            provenance=ProvenanceSummary(
                total_evidence_count=0,
                active_evidence_count=0,
                stale_evidence_count=0,
                independent_sources_count=0,
                authority_reports_count=0,
                verified_responder_count=0,
                citizen_reports_count=0,
                photos_count=0,
                sensors_count=0,
                evidence_modalities=[],
                supporting_observations=[],
                contradicting_observations=[],
                last_evidence_time=None,
                oldest_active_evidence_time=None,
            ),
            evaluated_at=evaluation_time,
        )

    # Separate supporting vs clearance/contradicting evidence
    supporting_obs: List[Observation] = []
    contradicting_obs: List[Observation] = []
    active_count = 0
    stale_count = 0
    modalities: Set[str] = set()
    unique_sources: Set[str] = set()

    authority_count = 0
    responder_count = 0
    citizen_count = 0
    photo_count = 0
    sensor_count = 0

    most_recent_time: datetime = observations[0].observed_at
    oldest_active_time: datetime | None = None

    for obs in observations:
        # Age check
        age_min = calculate_age_minutes(obs.observed_at, evaluation_time)
        stale = is_observation_stale(obs.observed_at, obs.hazard_type, evaluation_time)
        if stale:
            stale_count += 1
        else:
            active_count += 1
            if oldest_active_time is None or obs.observed_at < oldest_active_time:
                oldest_active_time = obs.observed_at

        if obs.observed_at > most_recent_time:
            most_recent_time = obs.observed_at

        # Modality and provenance metrics
        modalities.add(obs.evidence_type.value)
        unique_sources.add(obs.source_id)

        if obs.source_type == SourceType.OFFICIAL_AUTHORITY:
            authority_count += 1
        elif obs.source_type == SourceType.VERIFIED_RESPONDER:
            responder_count += 1
        elif obs.source_type == SourceType.CITIZEN:
            citizen_count += 1
        elif obs.source_type == SourceType.SENSOR:
            sensor_count += 1

        if obs.evidence_type == EvidenceType.PHOTO:
            photo_count += 1

        # Contradiction / Clearance check
        if (
            obs.hazard_type == HazardType.CLEARANCE
            or obs.evidence_type == EvidenceType.CLEARANCE_REPORT
            or obs.severity_observation == SeverityLevel.NONE
        ):
            contradicting_obs.append(obs)
        else:
            supporting_obs.append(obs)

    min_since_last = calculate_age_minutes(most_recent_time, evaluation_time)
    freshness = determine_freshness_level(min_since_last)

    # 1. Compute cumulative supporting weight
    supporting_weights = [
        calculate_single_evidence_weight(o, evaluation_time) for o in supporting_obs
    ]
    sum_supporting_weight = sum(supporting_weights)

    # 2. Compute cumulative clearance/contradiction weight
    contradicting_weights = [
        calculate_single_evidence_weight(o, evaluation_time) for o in contradicting_obs
    ]
    sum_clearance_weight = sum(contradicting_weights)

    # 3. Independent Corroboration Multiplier
    # Non-linear diminishing returns: 1 - 2^(-N_sources / 2)
    n_sources = len(unique_sources)
    corroboration_factor = 1.0 - math.pow(2.0, -n_sources / 2.0)

    # 4. Modality Diversity Bonus
    modality_bonus = min(0.15, (len(modalities) - 1) * 0.05) if len(modalities) > 1 else 0.0

    # 5. Raw hazard evidence score
    # Baseline score scales from weighted sum dampened by corroboration
    if sum_supporting_weight + sum_clearance_weight > 0:
        net_hazard_mass = max(0.0, sum_supporting_weight - (1.2 * sum_clearance_weight))
    else:
        net_hazard_mass = 0.0

    # Bounded score [0.0, 1.0]
    raw_score = (1.0 - math.exp(-net_hazard_mass * 1.5)) * corroboration_factor + modality_bonus
    confidence_score = max(0.0, min(1.0, round(raw_score, 4)))

    is_conflicted = False
    is_sensor_only = (sensor_count > 0 and citizen_count == 0 and responder_count == 0 and photo_count == 0)

    # Determine Calibrated RiskLevel and ConfidenceLevel
    # Rule A: Strong recent clearance evidence overrides hazard
    if sum_clearance_weight > 0 and sum_clearance_weight >= sum_supporting_weight:
        risk_level = RiskLevel.CLEARED
        confidence_level = (
            ConfidenceLevel.HIGH if (responder_count > 0 or authority_count > 0) else ConfidenceLevel.MEDIUM
        )
    # Rule B: Conflicting evidence (both ground hazard and recent clearance co-exist) - AC-014
    elif sum_clearance_weight > 0 and sum_supporting_weight > 0 and (0.3 <= sum_clearance_weight / sum_supporting_weight <= 1.2):
        risk_level = RiskLevel.UNCERTAIN
        confidence_level = ConfidenceLevel.LOW
        is_conflicted = True
    # Rule C: Sensor-only rainfall indicators without ground confirmation - AC-014
    elif is_sensor_only:
        risk_level = RiskLevel.UNCERTAIN
        confidence_level = ConfidenceLevel.LOW
    # Rule D: Stale evidence with no recent refresh -> UNCERTAIN
    elif freshness == FreshnessLevel.STALE:
        risk_level = RiskLevel.UNCERTAIN
        confidence_level = ConfidenceLevel.LOW
    # Rule E: Calibrated score tiers
    else:
        if confidence_score >= 0.75 and (authority_count > 0 or responder_count > 0 or photo_count > 0):
            risk_level = RiskLevel.CRITICAL
            confidence_level = ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 0.50:
            risk_level = RiskLevel.HIGH
            confidence_level = (
                ConfidenceLevel.HIGH if n_sources >= 2 else ConfidenceLevel.MEDIUM
            )
        elif confidence_score >= 0.30:
            risk_level = RiskLevel.ELEVATED
            confidence_level = (
                ConfidenceLevel.HIGH if (n_sources >= 2 and photo_count > 0) else ConfidenceLevel.MEDIUM
            )
        elif confidence_score >= 0.10:
            risk_level = RiskLevel.LOW
            confidence_level = ConfidenceLevel.LOW
        else:
            risk_level = RiskLevel.UNCERTAIN
            confidence_level = ConfidenceLevel.LOW

    # Summary Advisory Construction
    summary_advisory = _generate_deterministic_advisory(
        risk_level=risk_level,
        confidence_level=confidence_level,
        hazard_type=hazard_type,
        min_since_last=min_since_last,
        n_sources=n_sources,
        photo_count=photo_count,
        authority_count=authority_count,
        responder_count=responder_count,
        is_conflicted=is_conflicted,
        is_sensor_only=is_sensor_only,
    )

    provenance = ProvenanceSummary(
        total_evidence_count=len(observations),
        active_evidence_count=active_count,
        stale_evidence_count=stale_count,
        independent_sources_count=n_sources,
        authority_reports_count=authority_count,
        verified_responder_count=responder_count,
        citizen_reports_count=citizen_count,
        photos_count=photo_count,
        sensors_count=sensor_count,
        evidence_modalities=sorted(list(modalities)),
        supporting_observations=[o.id for o in supporting_obs],
        contradicting_observations=[o.id for o in contradicting_obs],
        last_evidence_time=most_recent_time,
        oldest_active_evidence_time=oldest_active_time,
    )

    return Assessment(
        event_id=event_id,
        hazard_type=hazard_type,
        risk_level=risk_level,
        confidence_level=confidence_level,
        confidence_score=confidence_score,
        freshness_status=freshness,
        minutes_since_last_evidence=round(min_since_last, 1),
        summary_advisory=summary_advisory,
        provenance=provenance,
        evaluated_at=evaluation_time,
    )


def _generate_deterministic_advisory(
    risk_level: RiskLevel,
    confidence_level: ConfidenceLevel,
    hazard_type: HazardType,
    min_since_last: float,
    n_sources: int,
    photo_count: int,
    authority_count: int,
    responder_count: int,
    is_conflicted: bool = False,
    is_sensor_only: bool = False,
) -> str:
    """Generates concise, factual commuter advisories grounded strictly in evidence."""
    hazard_label = hazard_type.value.lower().replace("_", " ")
    age_str = f"{int(min_since_last)}m ago" if min_since_last >= 1.0 else "just now"

    if risk_level == RiskLevel.CLEARED:
        return f"ROAD PASSABLE: Evidence indicates {hazard_label} has cleared (last updated {age_str})."

    if risk_level == RiskLevel.UNCERTAIN:
        if is_conflicted:
            return (
                f"UNCERTAIN HAZARD CONDITIONS: Recent evidence is conflicting or insufficient ({age_str}). "
                f"Reports of waterlogging conflict with clearance reports. Awaiting on-ground responder verification."
            )
        if is_sensor_only:
            return (
                f"STATUS: UNCERTAIN. Recent rainfall indicators suggest elevated risk, "
                f"but no recent ground-level observation confirms waterlogging ({age_str})."
            )
        return (
            f"UNCERTAIN HAZARD CONDITIONS: Isolated or aging reports of {hazard_label} "
            f"({age_str}). Awaiting fresh ground corroboration."
        )

    evidence_points = []
    if authority_count > 0:
        evidence_points.append("official authority advisory")
    if responder_count > 0:
        evidence_points.append(f"{responder_count} on-ground responder verification")
    if photo_count > 0:
        evidence_points.append(f"{photo_count} photographic evidence")
    if n_sources > 1:
        evidence_points.append(f"{n_sources} independent sources")

    details = f" Corroborated by {', '.join(evidence_points)}." if evidence_points else ""

    return (
        f"{risk_level.value} RISK — Active {hazard_label} reported (Confidence: {confidence_level.value}, "
        f"last fresh evidence {age_str}).{details} Exercise caution or seek alternate routes."
    )
