"""
NammaSignal Time Decay Engine
Deterministic exponential half-life decay modeling for real-world road hazards.
"""

from datetime import datetime, timezone
import math
from typing import Dict
from domain.entities import HazardType, FreshnessLevel


# Half-life tau (in minutes) by hazard type
DEFAULT_HALF_LIVES: Dict[HazardType, float] = {
    HazardType.WATERLOGGING: 30.0,       # Water changes rapidly: 30 min half-life
    HazardType.ROADBLOCK: 180.0,         # Blockages / barricades: 3 hours
    HazardType.FALLEN_TREE: 180.0,       # Tree clearing operations: 3 hours
    HazardType.SEWAGE_OVERFLOW: 60.0,    # Sewage / overflow: 1 hour
    HazardType.POTHOLE_DAMAGE: 4320.0,   # Potholes / structural: 3 days
    HazardType.CLEARANCE: 45.0,          # Clearance notices remain fresh for 45 min
}

# Cutoff threshold: observations older than 4 * half_life retain < 6.25% weight and are considered stale
STALE_THRESHOLD_MULTIPLIER = 4.0


def calculate_age_minutes(observed_at: datetime, evaluation_time: datetime | None = None) -> float:
    """Calculates observation age in minutes, safely handling timezones."""
    if evaluation_time is None:
        evaluation_time = datetime.now(timezone.utc)
    
    # Ensure UTC timezone awareness
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    if evaluation_time.tzinfo is None:
        evaluation_time = evaluation_time.replace(tzinfo=timezone.utc)

    delta_seconds = (evaluation_time - observed_at).total_seconds()
    # Guard against clock skew or microsecond future stamps
    return max(0.0, delta_seconds / 60.0)


def calculate_time_weight(
    observed_at: datetime,
    hazard_type: HazardType = HazardType.WATERLOGGING,
    evaluation_time: datetime | None = None,
    custom_half_life: float | None = None,
) -> float:
    """
    Computes time-decay weight using the exponential half-life formula:
        w_time = 2 ^ (-age / tau)

    Returns a float in [0.0, 1.0].
    """
    age_minutes = calculate_age_minutes(observed_at, evaluation_time)
    tau = custom_half_life if custom_half_life is not None else DEFAULT_HALF_LIVES.get(hazard_type, 30.0)
    
    if tau <= 0.0:
        return 0.0

    # Exponential decay
    weight = math.pow(2.0, -age_minutes / tau)
    return max(0.0, min(1.0, weight))


def determine_freshness_level(age_minutes: float) -> FreshnessLevel:
    """Categorizes age into standardized human-interpretable freshness tiers."""
    if age_minutes <= 15.0:
        return FreshnessLevel.FRESH
    elif age_minutes <= 45.0:
        return FreshnessLevel.MODERATE
    elif age_minutes <= 90.0:
        return FreshnessLevel.AGING
    else:
        return FreshnessLevel.STALE


def is_observation_stale(
    observed_at: datetime,
    hazard_type: HazardType = HazardType.WATERLOGGING,
    evaluation_time: datetime | None = None,
) -> bool:
    """Returns True if the observation has decayed past 4 half-lives."""
    age_minutes = calculate_age_minutes(observed_at, evaluation_time)
    tau = DEFAULT_HALF_LIVES.get(hazard_type, 30.0)
    return age_minutes >= (STALE_THRESHOLD_MULTIPLIER * tau)
