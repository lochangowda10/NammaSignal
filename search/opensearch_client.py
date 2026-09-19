"""
NammaSignal OpenSearch Geospatial & Semantic Search Client
Implements OpenSearch geo_point indexing with graceful fallback to MemorySpatialIndex.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from domain.entities import HazardEvent, GeoPoint, EventStatus
from search.memory_index import MemorySpatialIndex

logger = logging.getLogger("nammasignal.search")

INDEX_NAME = "nammasignal_hazards"

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "location": {"type": "geo_point"},
            "landmark_name": {"type": "text"},
            "hazard_type": {"type": "keyword"},
            "status": {"type": "keyword"},
            "boundary_radius_meters": {"type": "float"},
            "first_observed_at": {"type": "date"},
            "last_observed_at": {"type": "date"},
            "risk_level": {"type": "keyword"},
            "confidence_score": {"type": "float"},
        }
    }
}


class OpenSearchManager:
    """
    Manages geospatial and temporal indexing in OpenSearch,
    with zero-docker fallback to MemorySpatialIndex.
    """

    def __init__(
        self,
        hosts: List[str] | None = None,
        use_ssl: bool = False,
        verify_certs: bool = False,
    ):
        self.hosts = hosts or ["http://localhost:9200"]
        self.memory_fallback = MemorySpatialIndex()
        self.is_connected = False
        self.client = None

        self._connect()

    @property
    def active_engine_name(self) -> str:
        return "OpenSearch" if self.is_connected else "MemorySpatialIndex (Embedded Fallback)"

    def _connect(self) -> None:
        try:
            from opensearchpy import OpenSearch
            self.client = OpenSearch(
                hosts=self.hosts,
                use_ssl=False,
                verify_certs=False,
                request_timeout=2.0,
            )
            # Health ping
            if self.client.ping():
                self.is_connected = True
                self._ensure_index()
                logger.info("Connected to OpenSearch cluster at: %s", self.hosts)
            else:
                logger.warning("OpenSearch ping failed. Using in-memory spatial index fallback.")
        except Exception as e:
            logger.info("OpenSearch not reachable (%s). Using high-speed MemorySpatialIndex.", str(e))
            self.is_connected = False

    def _ensure_index(self) -> None:
        if not self.is_connected or not self.client:
            return
        try:
            if not self.client.indices.exists(index=INDEX_NAME):
                self.client.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
                logger.info("Created OpenSearch index '%s' with geo_point mappings.", INDEX_NAME)
        except Exception as e:
            logger.error("Failed creating OpenSearch index: %s", str(e))

    def index_event(self, event: HazardEvent) -> None:
        # Always maintain memory fallback
        self.memory_fallback.index_event(event)

        if not self.is_connected or not self.client:
            return

        doc = {
            "id": str(event.id),
            "location": {
                "lat": event.primary_location.latitude,
                "lon": event.primary_location.longitude,
            },
            "landmark_name": event.primary_location.landmark_name or "",
            "hazard_type": event.hazard_type.value,
            "status": event.status.value,
            "boundary_radius_meters": event.boundary_radius_meters,
            "first_observed_at": event.first_observed_at.isoformat(),
            "last_observed_at": event.last_observed_at.isoformat(),
            "risk_level": event.current_assessment.risk_level.value if event.current_assessment else "UNCERTAIN",
            "confidence_score": event.current_assessment.confidence_score if event.current_assessment else 0.0,
        }

        try:
            self.client.index(index=INDEX_NAME, id=str(event.id), body=doc, refresh=True)
        except Exception as e:
            logger.error("OpenSearch indexing error: %s", str(e))

    def search_nearby_events(
        self,
        center: GeoPoint,
        radius_meters: float = 1000.0,
        status: Optional[EventStatus] = None,
        now: Optional[datetime] = None,
    ) -> List[Tuple[HazardEvent, float]]:
        # If not connected or in tests, seamlessly use in-memory index
        if not self.is_connected or not self.client:
            return self.memory_fallback.search_nearby_events(
                center=center,
                radius_meters=radius_meters,
                status=status,
                now=now,
            )

        # Execute OpenSearch geo_distance query
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "geo_distance": {
                                "distance": f"{int(radius_meters)}m",
                                "location": {
                                    "lat": center.latitude,
                                    "lon": center.longitude,
                                }
                            }
                        }
                    ]
                }
            }
        }

        if status:
            query["query"]["bool"]["must"].append({"term": {"status": status.value}})

        try:
            res = self.client.search(index=INDEX_NAME, body=query)
            hits = res.get("hits", {}).get("hits", [])
            results = []
            for hit in hits:
                event_id = UUID(hit["_id"])
                # Resolve full domain entity from fallback repository
                ev = self.memory_fallback._events.get(event_id)
                if ev:
                    # Calculate exact distance
                    from domain.correlation import haversine_distance_meters
                    dist = haversine_distance_meters(center, ev.primary_location)
                    results.append((ev, round(dist, 1)))
            results.sort(key=lambda x: x[1])
            return results
        except Exception as e:
            logger.warning("OpenSearch query error (%s). Falling back to memory index.", str(e))
            return self.memory_fallback.search_nearby_events(
                center=center,
                radius_meters=radius_meters,
                status=status,
                now=now,
            )
