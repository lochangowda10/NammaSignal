# NammaSignal: System Architecture & Design Specification

## 1. Architectural Style & Design Principles
NammaSignal is architected following **Clean / Hexagonal Architecture** (Ports and Adapters) with strict boundaries:
- **Domain Layer**: Pure business logic (Entities, Value Objects, Time Decay Functions, Correlation Algorithms, Evidence Aggregators). Zero framework dependencies.
- **Application Layer (Use Cases)**: Orchestrates workflows (IngestObservation, CorrelateEvent, EvaluateAssessment, VerifyEvidence).
- **Ports (Interfaces)**: Abstract contracts for persistence, search, policy evaluation, and agent interpretation.
- **Adapters (Infrastructure)**:
  - *Cedar Policy Adapter*: Evaluates Cedar AST via `cedarpy`.
  - *Search Adapter*: Local OpenSearch cluster (with in-memory geospatial fallback for offline zero-docker execution).
  - *Persistence Adapter*: SQLite / relational datastore with immutable audit log and schema migrations.
  - *Agent Adapter*: Strands Agents SDK harnesses with deterministic JSON output validation.
  - *External Feeds Adapter*: Abstract simulator interface for KSNDMC rainfall telemetry and BTP traffic advisories.
- **Presentation Layer**:
  - *REST API*: FastAPI with strict Pydantic v2 schemas and correlation ID middleware.
  - *Web UI*: Modern Next.js / Vite dashboard designed for clarity, provenance inspection, and the Best UI track.

```
                  +----------------------------------------------+
                  |              Web UI / API Clients            |
                  +----------------------------------------------+
                                         |
                                         v
                         +-------------------------------+
                         |      FastAPI REST Layer       |
                         |  (Validation, Rate Limiting)  |
                         +-------------------------------+
                                         |
                                         v
                         +-------------------------------+
                         |    Application Use Cases      |
                         +-------------------------------+
                                  /      |      \
                                 /       |       \
                                v        v        v
                         +---------+ +-------+ +---------+
                         | Domain  | | Cedar | | Strands |
                         | Logic & | | Policy| | Agent   |
                         | Fusion  | | Engine| | Harness |
                         +---------+ +-------+ +---------+
                                  \      |      /
                                   \     |     /
                                    v    v    v
                         +-------------------------------+
                         |       Storage & Indexing      |
                         | (SQLite State + OpenSearch)   |
                         +-------------------------------+
```

---

## 2. Core Domain Model Entities

### 2.1 Observation (Immutable Atomic Fact)
```python
class Observation:
    id: UUID
    source_id: str
    source_type: SourceType  # CITIZEN, VERIFIED_RESPONDER, OFFICIAL_AUTHORITY, SENSOR
    location: GeoPoint       # latitude, longitude, landmark_name
    timestamp: datetime      # observation time
    ingested_at: datetime    # system intake time
    raw_content: str
    hazard_type: HazardType  # WATERLOGGING, ROADBLOCK, DAMAGE, CLEARANCE
    severity_observation: SeverityLevel # LOW, MEDIUM, HIGH, CRITICAL, NONE
    evidence_type: EvidenceType # TEXT, PHOTO, ADVISORY, SENSOR_READING
    media_url: Optional[str]
    metadata: Dict[str, Any]
```

### 2.2 HazardEvent (Correlated Spatial-Temporal Cluster)
```python
class HazardEvent:
    id: UUID
    primary_location: GeoPoint
    boundary_radius_meters: float
    hazard_type: HazardType
    status: EventStatus       # ACTIVE, MONITORING, RESOLVED, DISMISSED
    first_observed_at: datetime
    last_observed_at: datetime
    observation_ids: List[UUID]
    correlation_reason: str
    version: int
    created_at: datetime
    updated_at: datetime
```

### 2.3 Assessment (Time-Decayed Evaluated State)
```python
class Assessment:
    event_id: UUID
    hazard_type: HazardType
    risk_level: RiskLevel         # LOW, ELEVATED, HIGH, CRITICAL, UNCERTAIN
    confidence_level: ConfidenceLevel # LOW, MEDIUM, HIGH, VERY_HIGH
    confidence_score: float       # [0.0, 1.0] (deterministic evidence weight)
    freshness_status: FreshnessLevel # FRESH (<15m), MODERATE (<45m), STALE (>90m)
    active_evidence_count: int
    supporting_observations: List[UUID]
    contradicting_observations: List[UUID]
    summary_advisory: str
    provenance_breakdown: ProvenanceSummary
    evaluated_at: datetime
```

---

## 3. End-to-End Processing Pipeline

1. **Ingress**: Observation submitted via `POST /api/v1/observations` with caller's Principal identity.
2. **Authorization Boundary #1**: Cedar evaluates whether caller can submit an observation of this source type.
3. **Structured Interpretation**: Observation Interpreter (Strands Agent) extracts normalized hazard type, reported severity, landmark, and certainty flags.
4. **Geospatial & Temporal Retrieval**: OpenSearch queries candidate events within 500m active within last 2 hours.
5. **Deterministic Correlation**:
   - If distance $\le 300\text{m}$ and hazard is compatible $\rightarrow$ attach observation to existing `HazardEvent`.
   - If observation indicates clearance ("water drained, road open") $\rightarrow$ attach as clearance evidence.
   - Otherwise $\rightarrow$ spawn new `HazardEvent`.
6. **Evidence Fusion & Time-Decay Computation**:
   - Compute current age for all observations linked to the event.
   - Apply half-life decay $w_{\text{time}} = 2^{-\Delta t / \tau}$.
   - Aggregate weighted authority, count independent principals, apply corroboration bonus.
   - Compute risk score and map to calibrated `RiskLevel` and `ConfidenceLevel`.
7. **Advisory Synthesis**: Advisory Generator produces concise, evidence-backed commuter bulletin.
8. **Persistence & Search Sync**: Transactional state committed to SQLite; event index updated in OpenSearch.

---

## 4. API Specification Contracts

### Endpoints
* `POST /api/v1/observations` — Ingest observation (Citizen / Responder / Authority)
* `GET /api/v1/hazards` — List active hazard events (filtered by bbox, severity, freshness)
* `GET /api/v1/hazards/{id}` — Get single hazard event with full assessment
* `GET /api/v1/hazards/{id}/evidence` — Get granular evidence provenance chain
* `POST /api/v1/hazards/{id}/verify` — Official verification / status override (Cedar enforced)
* `POST /api/v1/simulation/time` — Advance simulated time clock to demonstrate decay
* `POST /api/v1/simulation/scenarios/{name}` — Seed deterministic real-world scenario (e.g., Silk Board Storm)
* `GET /api/v1/audit/logs` — Trace inspection for Cedar decisions and agent reasoning

---

## 5. Local-First & Zero-Cost Cloud Strategy
1. **Zero External Billing**: Everything executes locally on the developer machine using Docker (for OpenSearch / LocalStack) and native Python/Node runtimes.
2. **In-Memory Fallback Mode**: If Docker is not running or OpenSearch is unavailable, the system transparently falls back to an embedded SQLite + in-memory Spatial R-Tree engine so tests and local evaluation run in $< 2$ seconds.
3. **One-Command Setup**: `docker-compose.yml` and automated startup script.
