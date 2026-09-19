"""
Audit & Observability Endpoints
Exposes structured audit logs and Cedar authorization trace decisions.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_event_repository
from persistence.repository import EventRepository

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/logs", response_model=List[Dict[str, Any]])
def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    repo: EventRepository = Depends(get_event_repository),
):
    entries = repo.get_audit_logs(limit=limit)
    return [entry.model_dump(mode="json") for entry in entries]
