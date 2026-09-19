// ==============================================================================
// NammaSignal - AWS Cedar Authorization Policies
// Zero-Trust Security as Code for Physical Hazard Intelligence & Response
// ==============================================================================

// ------------------------------------------------------------------------------
// 1. PUBLIC CITIZEN POLICIES
// ------------------------------------------------------------------------------
// Citizens can submit ground observations and view public hazard assessments.
permit (
    principal in Role::"Citizen",
    action in [Action::"SubmitObservation", Action::"ViewHazards", Action::"ViewEvidence"],
    resource
);

// ------------------------------------------------------------------------------
// 2. VERIFIED RESPONDER POLICIES (Traffic Police field officers, BBMP Ward Wardens)
// ------------------------------------------------------------------------------
// Verified Responders can submit observations, verify hazard severity, and submit clearance notices.
permit (
    principal in Role::"VerifiedResponder",
    action in [
        Action::"SubmitObservation",
        Action::"ViewHazards",
        Action::"ViewEvidence",
        Action::"VerifyHazard",
        Action::"SubmitClearance"
    ],
    resource
);

// ------------------------------------------------------------------------------
// 3. OFFICIAL AUTHORITY POLICIES (BTP Control Room, KSNDMC Disaster Officers)
// ------------------------------------------------------------------------------
// Authorities have full operational privileges: official advisories, overrides, dismissals.
permit (
    principal in Role::"OfficialAuthority",
    action in [
        Action::"SubmitObservation",
        Action::"ViewHazards",
        Action::"ViewEvidence",
        Action::"VerifyHazard",
        Action::"SubmitClearance",
        Action::"PublishAdvisory",
        Action::"DismissHazard",
        Action::"AdvanceSimulationTime"
    ],
    resource
);

// ------------------------------------------------------------------------------
// 4. SYSTEM AGENT POLICIES
// ------------------------------------------------------------------------------
// Automated background processing: can evaluate evidence, never impersonates authority.
permit (
    principal in Role::"System",
    action in [
        Action::"EvaluateAssessment",
        Action::"CorrelateEvent",
        Action::"IndexSearch",
        Action::"ViewHazards"
    ],
    resource
);

// ------------------------------------------------------------------------------
// 5. EXPLICIT RESTRICTIONS & DEFENSE-IN-DEPTH
// ------------------------------------------------------------------------------
// Citizens and untrusted actors are explicitly forbidden from official verifications.
forbid (
    principal in Role::"Citizen",
    action in [
        Action::"VerifyHazard",
        Action::"PublishAdvisory",
        Action::"DismissHazard",
        Action::"AdvanceSimulationTime"
    ],
    resource
);
