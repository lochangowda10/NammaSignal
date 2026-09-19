# Project Context & Architecture Memory: First Commit Hackathon

## 1. Hackathon Overview & Objectives
* **Event**: First Commit | Bharat Builds Tour | WeMakeDevs (Sept 17 – 20, 2026)
* **Team**: Vertex
* **Participant**: Lochan Gowda T M (@lochangowda10)
* **Target Tracks**:
  1. **Build It (Track 1)**: Second Prize (₹1,50,000 cash + $2,000 AWS credits). Local-first open-source AWS stack (Cedar policy engine, Strands Agents SDK, OpenSearch, LocalStack). No AWS bills/account needed.
  2. **Best UI (Special Track)**: Third Prize (₹1,00,000 cash + $1,000 AWS credits). Modern, high-polish, dark-mode command center with interactive simulation, live Cedar policy traces, and granular evidence provenance.
  3. **Fast-Track Amazon Interviews**: Top 10 students skip screening for 6-month internships and full-time SDE roles.
  4. **Top 5 Blogs**: Logitech gaming keyboard for high-quality writeup on AWS Builder Center.

---

## 2. Product Identity: NammaSignal
* **One-Line Description**: NammaSignal converts fragmented official and citizen observations about Bengaluru road hazards into a unified, time-aware, evidence-backed hazard assessment.
* **Core Paradigm**: An **intelligence and fusion layer** above existing systems. It answers: *"Is there sufficiently fresh, corroborated, and authoritative evidence that a specific road segment is hazardous right now, how confident is the system, and why?"*

---

## 3. Implemented Architecture & Technology Mapping

```
                                  NammaSignal Architecture
 +-----------------------------------------------------------------------------------------+
 |                               Web Dashboard Command Center                              |
 |              (Glassmorphic Dark UI, Live Cedar Trace, Provenance Inspector)             |
 +-----------------------------------------------------------------------------------------+
                                              | (HTTP REST + X-Request-ID)
                                              v
 +-----------------------------------------------------------------------------------------+
 |                                FastAPI Gateway & Middleware                             |
 |            (Pydantic v2 validation, Structured JSON logging, Error boundaries)          |
 +-----------------------------------------------------------------------------------------+
                       |                                    |
                       v                                    v
     +-----------------------------------+   +------------------------------------+
     |    AWS Cedar Policy Engine        |   |    AWS Strands Agents SDK          |
     |  (cedarpy 4.12.0 Rust bindings)   |   |  - Agent 1: Observation Interpreter|
     |  - Deny-by-default RBAC/ABAC      |   |  - Agent 2: Evidence Analyst       |
     |  - Server-side token verification |   |  - Agent 3: Advisory Generator     |
     +-----------------------------------+   +------------------------------------+
                       \                                    /
                        v                                  v
 +-----------------------------------------------------------------------------------------+
 |                             Pure Domain & Math Fusion Core                              |
 |  - Deterministic Half-Life Time Decay (w_time = 2^(-dt / tau), tau=30m)                 |
 |  - Multi-Source Corroboration & Calibrated Confidence Tiers                             |
 |  - Haversine Spatial-Temporal-Semantic Event Correlation                                |
 |  - Bengaluru Landmark Gazetteer (11 canonical arterial hotspots)                        |
 +-----------------------------------------------------------------------------------------+
                       |                                    |
                       v                                    v
     +-----------------------------------+   +------------------------------------+
     |    Transactional Persistence      |   |    Geospatial & Semantic Search    |
     |  - SQLite with WAL Mode           |   |  - OpenSearch cluster (Docker)     |
     |  - Immutable Observation Log      |   |  - High-speed MemorySpatialIndex   |
     |  - Event Versioning & Audit Trail |   |    (Zero-dependency fallback)      |
     +-----------------------------------+   +------------------------------------+
```

---

## 4. Test Suite Execution Metrics (100% Green)
* Total Tests: **41 passed, 0 failed** (executed in 41s)
  - `tests/test_acceptance_criteria.py`: 19 tests covering AC-001 through AC-024.
  - `tests/unit/test_domain_math.py`: 5 tests (Time decay half-life, Haversine distance, corroboration confidence, clearance hazard reduction, gazetteer resolution).
  - `tests/unit/test_agents.py`: 3 tests (Vernacular/slang interpretation, prompt injection neutralization, evidence analysis report).
  - `tests/authorization/test_cedar_policies.py`: 8 tests (Citizen submissions, Citizen verification forbidden, Responder permissions, Authority overrides, System role least-privilege).
  - `tests/integration/test_api_pipeline.py`: 2 tests (Health check, full incident lifecycle).
  - `tests/adversarial/test_adversarial.py`: 4 tests (Prompt injection interception, empty payload rejection, invalid coordinates rejection, oversized payload rejection).

---

## 5. Completed Deliverables

| Deliverable | Location | Status | Description |
| :--- | :--- | :--- | :--- |
| **Acceptance Criteria Test Suite** | [`tests/test_acceptance_criteria.py`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/tests/test_acceptance_criteria.py) | ✅ Complete | 19 tests verifying AC-001 through AC-024. |
| **Demo Video Script** | [`docs/DEMO_VIDEO_SCRIPT.md`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/docs/DEMO_VIDEO_SCRIPT.md) | ✅ Complete | Second-by-second 180s video guide matching AC-027 to AC-038. |
| **Research Doc** | [`docs/RESEARCH.md`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/docs/RESEARCH.md) | ✅ Complete | Analysis of KSNDMC, Sahaaya, BTP, mathematical formulations. |
| **Architecture Doc** | [`docs/ARCHITECTURE.md`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/docs/ARCHITECTURE.md) | ✅ Complete | Hexagonal boundaries, domain models, and API contracts. |
| **Threat Model** | [`docs/THREAT_MODEL.md`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/docs/THREAT_MODEL.md) | ✅ Complete | STRIDE analysis, prompt injection defense, untrusted LLM boundaries. |
| **Decisions (ADRs)** | [`docs/DECISIONS.md`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/docs/DECISIONS.md) | ✅ Complete | 5 Architecture Decision Records and trade-offs. |
| **Domain Layer** | [`domain/`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/domain) | ✅ Complete | Entities, half-life time decay, evidence fusion, correlation, gazetteer. |
| **Cedar Authorization** | [`authorization/`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/authorization) | ✅ Complete | `policies.cedar`, `schema.cedarschema`, `evaluator.py`. |
| **Strands Agents** | [`agents/`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/agents) | ✅ Complete | Interpreter, Evidence Analyst, Advisory Generator with `@tool` decorator. |
| **Storage & Search** | [`persistence/`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/persistence), [`search/`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/search) | ✅ Complete | SQLite ACID store, OpenSearch geo_point, MemorySpatialIndex fallback. |
| **Simulation Engine** | [`simulation/`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/simulation), [`scripts/demo_simulation.py`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/scripts/demo_simulation.py) | ✅ Complete | 5-step Silk Board cloudburst interactive scenario. |
| **REST API Gateway** | [`apps/api/`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/apps/api) | ✅ Complete | FastAPI with root + `/api/v1` compatibility. |
| **Web Dashboard** | [`apps/web/index.html`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/apps/web/index.html) | ✅ Complete | Modern responsive UI, live Cedar trace, provenance matrix, simulation stepper. |
| **Container & Ops** | [`docker-compose.yml`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/docker-compose.yml), [`Dockerfile`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/Dockerfile), [`.env.example`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/.env.example) | ✅ Complete | OpenSearch cluster, single-command run scripts (`run_dev.ps1`). |
| **README Documentation** | [`README.md`](file:///c:/Users/Lochan%20Gowda/Hackathons/first%20commit/README.md) | ✅ Complete | Executive-grade product overview, math formulas, quickstart, test guide. |
