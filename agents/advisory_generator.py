"""
Agent 3: Advisory Generator (Strands Harness)
Synthesizes verified hazard assessments into concise, evidence-grounded commuter bulletins.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from domain.entities import HazardEvent, Assessment
from agents.evidence_analyst import EvidenceAnalysisReport


class CommuterAdvisory(BaseModel):
    headline: str
    location_title: str
    risk_level: str
    evidence_confidence: str
    last_evidence_time_human: str
    why_points: List[str]
    commuter_guidance: str
    disclaimer: str


class AdvisoryGeneratorAgent:
    """
    Strands Agent harness for generating commuter-facing advisories
    strictly grounded in factual evidence and mathematical assessments.
    """

    def generate(
        self,
        event: HazardEvent,
        assessment: Assessment,
        analysis: EvidenceAnalysisReport,
    ) -> CommuterAdvisory:
        loc_name = event.primary_location.landmark_name or "Bengaluru Road Corridor"
        hazard_str = event.hazard_type.value.replace("_", " ").title()

        # Headline
        if assessment.risk_level.value == "CLEARED":
            headline = f"ROAD PASSABLE: {hazard_str} Cleared"
            guidance = "Traffic moving normally. Road conditions confirmed cleared."
        elif assessment.risk_level.value in ["CRITICAL", "HIGH"]:
            headline = f"HIGH HAZARD ALERT: Severe {hazard_str}"
            guidance = "Do NOT enter underpass or flooded corridor. Seek alternate elevated routes immediately."
        elif assessment.risk_level.value == "ELEVATED":
            headline = f"CAUTION: Elevated {hazard_str} Risk"
            guidance = "Moderate water accumulation reported. Slow down and maintain safe braking distance."
        else:
            headline = f"MONITORING: {hazard_str} Reported"
            guidance = "Condition uncertain. Exercise normal driving precautions."

        # Human-readable evidence age
        min_ago = int(assessment.minutes_since_last_evidence)
        last_fresh = f"{min_ago} minutes ago" if min_ago >= 1 else "less than a minute ago"

        # Grounded "Why" points
        why_points = list(analysis.key_evidence_bullets)
        if analysis.is_conflicted:
            why_points.append(analysis.conflict_summary)

        why_points.append(f"Time Decay Status: {assessment.freshness_status.value} (evaluated {last_fresh})")

        return CommuterAdvisory(
            headline=headline,
            location_title=loc_name,
            risk_level=assessment.risk_level.value,
            evidence_confidence=assessment.confidence_level.value,
            last_evidence_time_human=last_fresh,
            why_points=why_points,
            commuter_guidance=guidance,
            disclaimer="NammaSignal evidence fusion is derived from multi-source citizen and public signals. Always obey traffic police directives.",
        )
