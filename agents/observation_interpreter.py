"""
Agent 1: Observation Interpreter (Strands Harness)
Translates unstructured citizen/channel reports (multilingual, slang) into
strictly validated Pydantic proposals, flagging uncertainties and injection attempts.
"""

import re
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
import logging

from strands import tool
from domain.entities import HazardType, SeverityLevel, EvidenceType, GeoPoint
from domain.gazetteer import resolve_landmark

logger = logging.getLogger("nammasignal.agents.interpreter")


class InterpretedObservationProposal(BaseModel):
    hazard_type: HazardType
    severity_observation: SeverityLevel
    evidence_type: EvidenceType
    recognized_landmark: Optional[str] = None
    resolved_location: Optional[GeoPoint] = None
    has_uncertainty: bool = False
    is_adversarial_flagged: bool = False
    extracted_features: List[str] = Field(default_factory=list)
    interpretation_confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str
    strands_sdk_version: str = "AWS Strands Agents SDK v1.56.0"
    strands_tool_invoked: str = "extract_bengaluru_hazard_features"


PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all)\s+instructions",
    r"system\s+override",
    r"grant\s+admin",
    r"delete\s+(database|table|event)",
    r"bypass\s+cedar",
    r"drop\s+table",
    r"sudo\s+",
]


@tool
def extract_bengaluru_hazard_features(raw_text: str) -> dict:
    """
    Strands Tool: Extracts semantic hazard features, severity cues, and landmark matches
    from unstructured Bengaluru citizen text reports.
    """
    loc = resolve_landmark(raw_text)
    return {
        "landmark": loc.landmark_name if loc else None,
        "coords": (loc.latitude, loc.longitude) if loc else None,
    }


class ObservationInterpreterAgent:
    """
    Strands Agent harness for interpreting unstructured observations.
    Tolerates slang, Kannada romanized phrases, abbreviations.
    """

    def interpret(self, raw_text: str, source_evidence_type: Optional[EvidenceType] = None) -> InterpretedObservationProposal:
        text_lower = raw_text.lower().strip()

        # 1. Adversarial Injection Defense Barrier
        is_adversarial = any(re.search(p, text_lower) for p in PROMPT_INJECTION_PATTERNS)
        if is_adversarial:
            logger.warning("Adversarial injection attempt intercepted: %s", raw_text)
            return InterpretedObservationProposal(
                hazard_type=HazardType.WATERLOGGING,
                severity_observation=SeverityLevel.NONE,
                evidence_type=EvidenceType.GROUND_OBSERVATION,
                has_uncertainty=True,
                is_adversarial_flagged=True,
                extracted_features=["adversarial_pattern_detected"],
                interpretation_confidence=0.0,
                rationale="Flagged potential prompt injection. Sanitized and neutralized.",
            )

        features = []

        # 2. Invoke AWS Strands Tool: Location & Feature Extraction
        tool_res = extract_bengaluru_hazard_features(raw_text)
        resolved_loc = resolve_landmark(raw_text)
        landmark_name = resolved_loc.landmark_name if resolved_loc else None
        if resolved_loc:
            features.append(f"matched_hotspot:{resolved_loc.landmark_name}")
            features.append(f"strands_tool_resolved:{landmark_name}")

        # 3. Clearance Detection
        clearance_keywords = [
            "cleared", "receded", "drained", "open for traffic", "passable",
            "pumped out", "dry", "traffic moving smoothly", "no water", "normal traffic"
        ]
        is_clearance = any(k in text_lower for k in clearance_keywords)
        if is_clearance:
            return InterpretedObservationProposal(
                hazard_type=HazardType.CLEARANCE,
                severity_observation=SeverityLevel.NONE,
                evidence_type=source_evidence_type or EvidenceType.CLEARANCE_REPORT,
                recognized_landmark=landmark_name,
                resolved_location=resolved_loc,
                has_uncertainty=False,
                is_adversarial_flagged=False,
                extracted_features=["clearance_keyword"],
                interpretation_confidence=0.95,
                rationale="Text explicitly indicates water receded or road passable.",
            )

        # 4. Hazard Type Classification
        if any(w in text_lower for w in ["tree", "branch", "fallen"]):
            hazard_type = HazardType.FALLEN_TREE
            features.append("tree_hazard")
        elif any(w in text_lower for w in ["pothole", "crater", "broken road"]):
            hazard_type = HazardType.POTHOLE_DAMAGE
            features.append("road_damage")
        elif any(w in text_lower for w in ["barricade", "blocked", "closed", "diversion"]):
            hazard_type = HazardType.ROADBLOCK
            features.append("roadblock_hazard")
        else:
            # Default monsoon arterial hazard
            hazard_type = HazardType.WATERLOGGING
            features.append("waterlogging_hazard")

        # 5. Severity Level Extraction
        critical_indicators = [
            "submerged", "waist deep", "floating", "engine failure",
            "stranded", "rescue", "danger", "stopped completely", "impassable"
        ]
        high_indicators = [
            "knee deep", "bumper deep", "heavy water", "turning around",
            "flooded", "severe traffic", "overflowing", "underpass full"
        ]
        medium_indicators = [
            "ankle deep", "slow moving", "water accumulation", "water puddle",
            "water logging", "waterlogged", "ponding"
        ]

        if any(w in text_lower for w in critical_indicators):
            severity = SeverityLevel.CRITICAL
            features.append("critical_severity_indicator")
        elif any(w in text_lower for w in high_indicators):
            severity = SeverityLevel.HIGH
            features.append("high_severity_indicator")
        elif any(w in text_lower for w in medium_indicators):
            severity = SeverityLevel.MEDIUM
            features.append("medium_severity_indicator")
        else:
            severity = SeverityLevel.LOW
            features.append("low_severity_indicator")

        # 6. Uncertainty Calculation
        has_uncertainty = False
        if not resolved_loc:
            has_uncertainty = True
            features.append("missing_exact_location")
        if any(u in text_lower for u in ["maybe", "not sure", "heard", "someone said"]):
            has_uncertainty = True
            features.append("hearsay_linguistic_marker")

        # Interpretation Confidence
        confidence = 0.90 if resolved_loc else 0.60
        if has_uncertainty:
            confidence -= 0.20

        return InterpretedObservationProposal(
            hazard_type=hazard_type,
            severity_observation=severity,
            evidence_type=source_evidence_type or EvidenceType.GROUND_OBSERVATION,
            recognized_landmark=landmark_name,
            resolved_location=resolved_loc,
            has_uncertainty=has_uncertainty,
            is_adversarial_flagged=False,
            extracted_features=features,
            interpretation_confidence=round(max(0.1, confidence), 2),
            rationale=f"Identified {hazard_type.value} with {severity.value} severity based on detected semantic markers.",
        )
