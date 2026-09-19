"""
NammaSignal In-Memory Spatial & Temporal Index
Zero-dependency spatial index supporting radius bounding queries,
temporal filtering, and full-text keyword search.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from domain.entities import HazardEvent, GeoPoint, EventStatus
from domain.correlation import haversine_distance_meters


class MemorySpatialIndex:
    """
    Lightweight, deterministic in-memory spatial index.
    Used for local execution, unit tests, and resilient fallback.
    """

    def __init__(self):
        self._events: dict[UUID, HazardEvent] = {}

    def index_event(self, event: HazardEvent) -> None:
        self._events[event.id] = event

    def remove_event(self, event_id: UUID) -> None:
        self._events.pop(event_id, None)

    def search_nearby_events(
        self,
        center: GeoPoint,
        radius_meters: float = 1000.0,
        status: Optional[EventStatus] = None,
        max_age_minutes: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> List[Tuple[HazardEvent, float]]:
        """
        Returns list of (HazardEvent, distance_in_meters) sorted by distance.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        results: List[Tuple[HazardEvent, float]] = []

        for event in self._events.values():
            if status and event.status != status:
                continue

            if max_age_minutes:
                age_min = (now - event.last_observed_at).total_seconds() / 60.0
                if age_min > max_age_minutes:
                    continue

            dist = haversine_distance_meters(center, event.primary_location)
            if dist <= radius_meters:
                results.append((event, round(dist, 1)))

        results.sort(key=lambda x: x[1])
        return results

    def clear(self) -> None:
        self._events.clear()
