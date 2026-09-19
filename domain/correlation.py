"""
NammaSignal Event Correlation Engine
Deterministic spatial-temporal-semantic clustering of multi-source observations.
"""

from datetime import datetime, timezone
import math
from typing import List, Optional, Tuple
from uuid import UUID

from domain.entities import (
    HazardEvent,
    Observation,
    GeoPoint,
    HazardType,
    EventStatus,
)


EARTH_RADIUS_METERS = 6371000.0


def haversine_distance_meters(p1: GeoPoint, p2: GeoPoint) -> float:
    """
    Computes great-circle distance between two GeoPoints in meters
    using the Haversine formula.
    """
    lat1, lon1 = math.radians(p1.latitude), math.radians(p1.longitude)
    lat2, lon2 = math.radians(p2.latitude), math.radians(p2.longitude)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


class CorrelationResult:
    def __init__(
        self,
        should_correlate: bool,
        reason: str,
        matched_event: Optional[HazardEvent] = None,
        distance_meters: float = 0.0,
    ):
        self.should_correlate = should_correlate
        self.reason = reason
        self.matched_event = matched_event
        self.distance_meters = distance_meters


class EventCorrelationEngine:
    """
    Deterministic correlation pipeline matching incoming observations
    against active hazard events.
    """

    def __init__(
        self,
        max_distance_meters: float = 350.0,
        max_time_window_minutes: float = 120.0,
    ):
        self.max_distance_meters = max_distance_meters
        self.max_time_window_minutes = max_time_window_minutes

    def evaluate_correlation(
        self,
        observation: Observation,
        active_events: List[HazardEvent],
        evaluation_time: datetime | None = None,
    ) -> CorrelationResult:
        """
        Determines whether an observation belongs to an existing active event
        or requires spawning a new one.
        """
        if evaluation_time is None:
            evaluation_time = datetime.now(timezone.utc)
        if evaluation_time.tzinfo is None:
            evaluation_time = evaluation_time.replace(tzinfo=timezone.utc)

        best_match: Optional[HazardEvent] = None
        min_distance = float("inf")
        correlation_reason = ""

        for event in active_events:
            # Only correlate with non-dismissed events
            if event.status in [EventStatus.DISMISSED, EventStatus.RESOLVED]:
                # Exception: a clearance report can correlate with a recently resolved/active event
                if observation.hazard_type != HazardType.CLEARANCE:
                    continue

            # 1. Geographic proximity check
            dist = haversine_distance_meters(observation.location, event.primary_location)
            effective_radius = max(self.max_distance_meters, event.boundary_radius_meters)
            if dist > effective_radius:
                continue

            # 2. Temporal proximity check
            delta_seconds = abs((observation.observed_at - event.last_observed_at).total_seconds())
            delta_minutes = delta_seconds / 60.0
            if delta_minutes > self.max_time_window_minutes:
                continue

            # 3. Hazard Type Compatibility
            is_compatible = self._are_hazards_compatible(
                obs_hazard=observation.hazard_type,
                event_hazard=event.hazard_type,
            )
            if not is_compatible:
                continue

            # Select closest spatial candidate
            if dist < min_distance:
                min_distance = dist
                best_match = event
                correlation_reason = (
                    f"Correlated with active {event.hazard_type.value} event {event.id} "
                    f"({int(dist)}m away, within {int(delta_minutes)}m temporal window)"
                )

        if best_match:
            return CorrelationResult(
                should_correlate=True,
                reason=correlation_reason,
                matched_event=best_match,
                distance_meters=min_distance,
            )

        return CorrelationResult(
            should_correlate=False,
            reason="No existing active hazard event found within spatial-temporal radius",
            matched_event=None,
            distance_meters=0.0,
        )

    def attach_observation_to_event(
        self,
        event: HazardEvent,
        observation: Observation,
    ) -> HazardEvent:
        """
        Immutably appends observation to event, advancing event version and timestamps.
        """
        new_obs_ids = list(event.observation_ids)
        if observation.id not in new_obs_ids:
            new_obs_ids.append(observation.id)

        # Update timestamps
        first_time = min(event.first_observed_at, observation.observed_at)
        last_time = max(event.last_observed_at, observation.observed_at)

        # Preserve canonical landmark if existing, else take observation landmark
        primary_loc = event.primary_location
        if not primary_loc.landmark_name and observation.location.landmark_name:
            primary_loc = observation.location

        return HazardEvent(
            id=event.id,
            primary_location=primary_loc,
            boundary_radius_meters=event.boundary_radius_meters,
            hazard_type=event.hazard_type,
            status=event.status,
            first_observed_at=first_time,
            last_observed_at=last_time,
            observation_ids=new_obs_ids,
            correlation_reason=f"Updated with observation {observation.id}",
            version=event.version + 1,
            current_assessment=event.current_assessment,
            created_at=event.created_at,
            updated_at=datetime.now(timezone.utc),
        )

    def create_new_event(
        self,
        observation: Observation,
        boundary_radius_meters: float = 350.0,
    ) -> HazardEvent:
        """Spawns a new HazardEvent seeded with the initial observation."""
        now = datetime.now(timezone.utc)
        return HazardEvent(
            primary_location=observation.location,
            boundary_radius_meters=boundary_radius_meters,
            hazard_type=observation.hazard_type,
            status=EventStatus.ACTIVE,
            first_observed_at=observation.observed_at,
            last_observed_at=observation.observed_at,
            observation_ids=[observation.id],
            correlation_reason=f"Spawned from initial observation {observation.id}",
            version=1,
            current_assessment=None,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _are_hazards_compatible(obs_hazard: HazardType, event_hazard: HazardType) -> bool:
        """Checks whether two hazard types are semantically compatible for clustering."""
        if obs_hazard == event_hazard:
            return True
        # Clearance reports are compatible with any active hazard
        if obs_hazard == HazardType.CLEARANCE:
            return True
        # Severe waterlogging can cause roadblocks
        if obs_hazard == HazardType.ROADBLOCK and event_hazard == HazardType.WATERLOGGING:
            return True
        return False
