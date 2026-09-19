# NammaSignal: Architecture Decision Records (ADR) & Trade-Offs

## ADR-001: Local-First AWS Open-Source Stack (Build It Track)
* **Context**: The hackathon offers the *Build It* track for running AWS open-source tooling locally without requiring cloud account credentials or incurring unexpected billing.
* **Decision**: Build NammaSignal using local AWS open-source technologies: **AWS Cedar** (`cedarpy`), **AWS Strands Agents SDK** (`strands-agents`), and **OpenSearch** in Docker with an in-memory spatial index fallback.
* **Consequences**: Enables 100% offline development, reproducible local testing, zero-cost execution for any judge, and directly aligns with the Build It judging criteria.

---

## ADR-002: Authorization as Code via AWS Cedar
* **Context**: Authorization in incident reporting must distinguish between public report submission, verified responder confirmation, and official government advisories.
* **Decision**: Enforce fine-grained authorization with AWS Cedar policies (`.cedar`), evaluated on the backend for every privileged operation.
* **Rejected Alternatives**:
  - *Hardcoded Python `if/else` role checks*: Fragile, un-auditable, prone to logic bugs and privilege escalation.
  - *OPA (Open Policy Agent) / Rego*: Cedar provides formal verification semantics, mathematical soundness, and is an AWS open-source flagship standard.
* **Trade-off**: Requires maintaining Cedar entity schemas alongside Pydantic models, but guarantees mathematical authorization correctness.

---

## ADR-003: Deterministic Evidence Fusion vs. Black-Box LLM Scoring
* **Context**: Road hazards involve real-world physical safety. Commuters make travel decisions based on reported risk.
* **Decision**: All risk scores, half-life time-decay evaluations, corroboration weights, and confidence levels are calculated via **deterministic mathematical algorithms**, not opaque LLM outputs.
* **Role of AI**: Strands Agents are restricted to semantic translation (extracting structured entities from informal vernacular text), nuance analysis (detecting contradictions), and advisory phrasing.
* **Rejected Alternative**: Letting an LLM directly generate a "Risk: 91%" score. LLMs hallucinate numbers, are non-deterministic, and cannot be statistically calibrated or audited.

---

## ADR-004: Dual-Store Strategy (Relational Canonical State + OpenSearch Spatial Index)
* **Context**: The system requires transactional consistency for immutable audit trails and observations, plus fast spatial-temporal bounding queries.
* **Decision**: Use SQLite / relational DB as the canonical source of truth for transactional entities (`Observation`, `HazardEvent`, `AuditLog`), and mirror active events to OpenSearch for spatial indexing (`geo_point`) and semantic retrieval. Provide an in-memory spatial index fallback when OpenSearch is not running.
* **Rejected Alternative**: Using OpenSearch as the sole primary database. OpenSearch is not an ACID-compliant transactional database and can suffer from eventual consistency latency during rapid updates.

---

## ADR-005: Honest Simulation Mode for Official Government Integrations
* **Context**: Official Bengaluru systems (KSNDMC Varunamitra, Megha Sandesha, BBMP Sahaaya, BTP) do not expose public developer streaming APIs.
* **Decision**: Implement an explicit `ExternalSourceAdapter` pattern. Clearly label simulated/seeded telemetry as `SIMULATED_KSNDMC` or `SIMULATED_BTP`. Never claim to have live private government connections when none exist.
* **Consequences**: Preserves scientific credibility and integrity in front of judges, while providing realistic demonstration scenarios (e.g., Silk Board cloudburst).

---

## Limitations of the System
1. **GPS Drift & Coarse Landmark Names**: Citizen reports often state "near Silk Board" without exact GPS coordinates. The system uses a landmark gazetteer to resolve common Bengaluru junctions, which has a ~100m spatial variance.
2. **Offline-First Synchronous vs Distributed Event Streaming**: For the hackathon MVP, event correlation executes within the service worker / FastAPI thread rather than a multi-node Kafka/Kinesis stream.
