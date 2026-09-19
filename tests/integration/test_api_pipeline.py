"""
End-to-End Integration Tests for NammaSignal API Pipeline
Validates full flow: Ingestion -> Strands -> Correlation -> Cedar -> Assessment -> Simulation.
"""

from fastapi.testclient import TestClient
import pytest
from apps.api.main import app

client = TestClient(app)


def test_health_check():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert data["cedar_security"] == "ACTIVE"


def test_full_incident_lifecycle():
    # 1. Citizen submits ground report at Silk Board
    ingest_payload = {
        "principal_id": "citizen_deepak",
        "principal_role": "Citizen",
        "display_name": "Deepak R",
        "raw_content": "Water is almost knee deep near Silk Board underpass, traffic standstill",
        "source_type": "CITIZEN",
        "evidence_type": "GROUND_OBSERVATION",
        "is_simulated": True,
    }
    res1 = client.post("/api/v1/observations", json=ingest_payload)
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["status"] == "PROCESSED"
    assert data1["correlation_action"] == "SPAWNED"
    assert data1["cedar_authorization"]["decision"] == "Allow"
    event_id = data1["event_id"]

    # 2. Query the created hazard event
    res_hazard = client.get(f"/api/v1/hazards/{event_id}")
    assert res_hazard.status_code == 200
    hazard_data = res_hazard.json()
    assert "Silk Board" in hazard_data["primary_location"]["landmark_name"]
    assert hazard_data["status"] == "ACTIVE"

    # 3. Second citizen submits photo evidence at same location
    ingest_photo = {
        "principal_id": "citizen_priya",
        "principal_role": "Citizen",
        "display_name": "Priya M",
        "raw_content": "Photo of water accumulation at silk board underpass",
        "source_type": "CITIZEN",
        "evidence_type": "PHOTO",
        "media_url": "https://example.com/photo.jpg",
        "latitude": 12.9176,
        "longitude": 77.6238,
        "is_simulated": True,
    }
    res2 = client.post("/api/v1/observations", json=ingest_photo)
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["correlation_action"] == "ATTACHED"
    assert data2["event_id"] == event_id

    # 4. Attempt unauthorized verification by citizen -> MUST BE DENIED BY CEDAR
    verify_citizen_payload = {
        "principal_id": "citizen_deepak",
        "principal_role": "Citizen",
        "display_name": "Deepak R",
        "verification_notes": "Trying to mark verified as a citizen",
    }
    res_deny = client.post(f"/api/v1/hazards/{event_id}/verify", json=verify_citizen_payload)
    assert res_deny.status_code == 403
    assert "Cedar Policy Denied" in res_deny.json()["detail"]["error"]

    # 5. Authorized Verification by Verified Responder -> MUST SUCCEED (Cedar ALLOW)
    verify_responder_payload = {
        "principal_id": "btp_officer_suresh",
        "principal_role": "VerifiedResponder",
        "display_name": "Officer Suresh",
        "badge_number": "BTP-552",
        "agency": "Bengaluru Traffic Police",
        "verification_notes": "BTP patrol on site. Underpass closed, traffic diverted.",
    }
    res_verify = client.post(f"/api/v1/hazards/{event_id}/verify", json=verify_responder_payload)
    assert res_verify.status_code == 200
    assert res_verify.json()["new_status"] == "VERIFIED"
    assert res_verify.json()["cedar_decision"] == "Allow"

    # 6. Check Evidence Provenance endpoint
    res_evidence = client.get(f"/api/v1/hazards/{event_id}/evidence")
    assert res_evidence.status_code == 200
    evidence_data = res_evidence.json()
    assert evidence_data["total_observations"] >= 2
    assert evidence_data["provenance"]["independent_sources_count"] >= 2

    # 7. Advance simulated time by 60 mins -> Freshness should decay
    advance_payload = {
        "minutes": 60.0,
        "principal_id": "admin_authority",
        "principal_role": "OfficialAuthority",
    }
    res_time = client.post("/api/v1/simulation/time", json=advance_payload)
    assert res_time.status_code == 200
    assert res_time.json()["status"] == "TIME_ADVANCED"

    # 8. Check hazard assessment after time decay
    res_decayed = client.get(f"/api/v1/hazards/{event_id}")
    assessment_decayed = res_decayed.json()["current_assessment"]
    assert assessment_decayed["freshness_status"] in ["AGING", "STALE", "MODERATE"]
    assert assessment_decayed["minutes_since_last_evidence"] >= 50.0

    # 9. Clearance report submitted -> Assessment flips to CLEARED
    clearance_payload = {
        "principal_id": "bbmp_engineer_1",
        "principal_role": "VerifiedResponder",
        "display_name": "BBMP Engineer",
        "raw_content": "Water pumped out near Silk Board, road dry and passable",
        "source_type": "VERIFIED_RESPONDER",
        "evidence_type": "CLEARANCE_REPORT",
        "latitude": 12.9176,
        "longitude": 77.6238,
        "is_simulated": True,
    }
    res_clear = client.post("/api/v1/observations", json=clearance_payload)
    assert res_clear.status_code == 201

    res_final = client.get(f"/api/v1/hazards/{event_id}")
    final_assessment = res_final.json()["current_assessment"]
    assert final_assessment["risk_level"] == "CLEARED"
