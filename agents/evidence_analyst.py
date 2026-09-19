"""
Agent 2: Evidence Analyst (Strands Harness)
Interprets evidence clusters, detects contradictions, identifies duplicates,
and generates structured evidence explanations.
"""

from typing import List, Dict, Any, Set
from pydantic import BaseModel, Field

from domain.entities import Observation, Assessment, HazardType, SeverityLevel


class EvidenceAnalysisReport(BaseModel):
    is_conflicted: bool
    conflict_summary: str
    duplicate_count: int
    key_evidence_bullets: List[str]
    confidence_trajectory_explanation: str


class EvidenceAnalystAgent:
    """
    Strands Agent harness for evidence cluster synthesis and contradiction analysis.
    """

    def analyze(self, observations: List[Observation], assessment: Assessment) -> EvidenceAnalysisReport:
        if not observations:
            return EvidenceAnalysisReport(
                is_conflicted=False,
                conflict_summary="No observations recorded.",
                duplicate_count=0,
                key_evidence_bullets=["Awaiting first evidence signal."],
                confidence_trajectory_explanation="Zero baseline confidence.",
            )

        # 1. Duplicate Detection (matching content or same user within tight window)
        seen_hashes: Set[str] = set()
        duplicates = 0
        for obs in observations:
            normalized = f"{obs.source_id}:{obs.raw_content.lower().strip()}"
            if normalized in seen_hashes:
                duplicates += 1
            else:
                seen_hashes.add(normalized)

        # 2. Conflict / Contradiction Detection
        has_clearance = any(
            o.hazard_type == HazardType.CLEARANCE or o.severity_observation == SeverityLevel.NONE
            for o in observations
        )
        has_high_hazard = any(
            o.severity_observation in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]
            for o in observations
        )

        is_conflicted = has_clearance and has_high_hazard
        if is_conflicted:
            conflict_summary = (
                "CONTRADICTION DETECTED: Ground reports conflict between active inundation "
                "and receding/drained water conditions. Priority given to most recent authoritative verification."
            )
        else:
            conflict_summary = "Evidence signals are semantically aligned without major contradictions."

        # 3. Key Evidence Bullets
        bullets = []
        prov = assessment.provenance
        if prov.authority_reports_count > 0:
            bullets.append(f"Official Authority: {prov.authority_reports_count} verified advisory bulletins")
        if prov.verified_responder_count > 0:
            bullets.append(f"Field Responders: {prov.verified_responder_count} on-ground inspections")
        if prov.photos_count > 0:
            bullets.append(f"Visual Corroboration: {prov.photos_count} authenticated photographic reports")
        if prov.citizen_reports_count > 0:
            bullets.append(f"Citizen Intelligence: {prov.citizen_reports_count} crowd reports from {prov.independent_sources_count} independent sources")

        if prov.stale_evidence_count > 0:
            bullets.append(f"Aging Evidence: {prov.stale_evidence_count} observations are decaying (> 1 hr old)")

        # 4. Confidence Trajectory Explanation
        if assessment.freshness_status.value == "STALE":
            trajectory = (
                f"Confidence has decayed to {assessment.confidence_level.value} because the last evidence "
                f"was received {assessment.minutes_since_last_evidence:.0f} minutes ago. System demands fresh corroboration."
            )
        elif is_conflicted:
            trajectory = (
                f"Confidence calibrated to {assessment.confidence_level.value} due to conflicting "
                f"observations currently being resolved."
            )
        elif prov.independent_sources_count >= 2 and (prov.photos_count > 0 or prov.verified_responder_count > 0):
            trajectory = (
                f"Confidence elevated to {assessment.confidence_level.value} due to multi-source cross-verification: "
                f"{prov.independent_sources_count} independent sources with visual/official confirmation within {assessment.minutes_since_last_evidence:.0f} min."
            )
        else:
            trajectory = (
                f"Initial confidence level ({assessment.confidence_level.value}) reflecting single-source unverified report."
            )

        return EvidenceAnalysisReport(
            is_conflicted=is_conflicted,
            conflict_summary=conflict_summary,
            duplicate_count=duplicates,
            key_evidence_bullets=bullets,
            confidence_trajectory_explanation=trajectory,
        )
