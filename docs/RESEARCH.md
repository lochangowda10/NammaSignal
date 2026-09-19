# NammaSignal: Comprehensive Domain & Technical Research

## 1. Executive Summary & Problem Context
During monsoon surges and localized flash floods in Bengaluru (Bangalore), road conditions degrade rapidly. Major arterial roads (Outer Ring Road, Silk Board, Bellandur, Ecospace, Hebbal flyover, Bannerghatta Road, Majestic underpasses) become impassable within 15–30 minutes of cloudburst activity.

Today, critical information exists in fragments across official agencies and citizen networks. The challenge is not an absence of data, but a severe lack of **spatial, temporal, and semantic evidence fusion**. 

NammaSignal does not replace existing monitoring or complaint systems. Instead, it operates as an **intelligence and fusion layer** above them: converting fragmented, multi-fidelity observations into evolving, time-aware, verifiable **Hazard Events**.

---

## 2. Existing Bengaluru Systems & Official Infrastructure Analysis

| System / Channel | Agency / Authority | Real-Time Availability | Public Machine API? | Nature of Data | Specific Gaps & Limitations |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Varunamitra** | KSNDMC | Near real-time (15-min sensor pulses) | ❌ **No public API** (Internal dashboard / web portal only) | Telemetry: Automated Weather Stations (AWS), Telemetric Rain Gauges (ARG). | Macro rainfall metrics; lacks localized road-level inundation observations or lane-level hazards. |
| **Bengaluru Megha Sandesha** | KSNDMC & IISc (Urban Flood Model) | Hourly / Periodic | ❌ **No public developer API** (Closed mobile app) | Ward-level alerts, storm-water drain (SWD) sensor levels, flood zone maps. | Coarse ward-level boundaries (243 wards); cannot pinpoint whether a specific underpass is submerged right now. |
| **BBMP Sahaaya 2.0** | BBMP / GBA (Greater Bengaluru Authority) | Ticket-based (delayed) | ❌ **No public streaming stream** (Grievance ticketing portal) | Civic grievance reports with tracking IDs (potholes, fallen trees, SWD overflow). | Workflow-oriented ticketing (24–72 hr SLA); completely unsuitable for rapid transit decisions or immediate hazard warning. |
| **Bengaluru Traffic Police (BTP)** | BTP Social Media / Control Room | Ad-hoc (Minutes to hours) | ❌ **No structured feed** (Disseminated via X/Twitter `@blrcitytraffic`, WhatsApp broadcasts) | Unstructured text advisories ("Water logging near Silk Board, traffic slow moving"). | Highly authoritative, but unstructured text without geo-coordinates, easily lost in social media noise, no decay/clearance signal. |
| **Citizen Social Media & Crowdsourcing** | X/Twitter, Reddit (`r/bangalore`), WhatsApp groups | Immediate to real-time | ❌ Unstructured & unverified | Citizen text posts, smartphone videos, photos, complaints. | Noisy, unverified, prone to viral amplification of stale/outdated floods, lacking structured provenance. |

### Architectural Conclusion on Existing Systems:
No single official system provides a **streaming, machine-readable, time-decaying road hazard intelligence feed**. Official systems are authoritative but lack hyper-local ground truth; citizen systems have hyper-local ground truth but lack verification and structure. 
*Decision*: NammaSignal will implement an adapter interface (`ExternalSourceAdapter`) featuring clearly labeled simulated/demo providers for KSNDMC telemetry and BTP traffic advisories, alongside real ingestion endpoints for citizen observations. We will never fabricate or claim live government API connectivity where none exists.

---

## 3. Evidence Fusion & Mathematical Time-Decay Formulation

### 3.1 The Time-Decay Imperative
A road hazard is inherently dynamic:
1. Water accumulates rapidly during high-intensity cloudbursts.
2. Inundation persists depending on stormwater drain absorption capacity.
3. Once rainfall stops and drains clear, hazards recede, yet outdated social media reports continue to mislead commuters for hours.

### 3.2 Time-Decay Function (Exponential Half-Life)
Let $t$ be the current evaluation timestamp, and $t_i$ be the timestamp of observation $i$.
The age $\Delta t_i = t - t_i$.
The time-decay weight $w_{\text{time}}(i)$ is modeled using half-life decay:
$$w_{\text{time}}(i) = 2^{-\frac{\Delta t_i}{\tau_{h}}}$$
where $\tau_h$ is the characteristic half-life for hazard type $h$.
* Waterlogging / Flash flood half-life: $\tau = 30 \text{ minutes}$
* Fallen tree / Roadblock half-life: $\tau = 180 \text{ minutes}$
* Pothole / Road damage half-life: $\tau = 4320 \text{ minutes (3 days)}$

Any observation where $\Delta t_i > 4\tau$ decays to $< 6.25\%$ weight and is considered stale.

### 3.3 Source Reliability & Authority Weighting
Observations are weighted by source provenance:
* **Official Authority** (KSNDMC, BTP advisories): $W_{\text{src}} = 1.00$
* **Verified Responder** (On-ground traffic warden, BBMP field engineer): $W_{\text{src}} = 0.90$
* **Authenticated Citizen with Media Evidence** (Cryptographically signed / validated photo): $W_{\text{src}} = 0.75$
* **Authenticated Citizen Text Observation**: $W_{\text{src}} = 0.50$
* **Anonymous Citizen Observation**: $W_{\text{src}} = 0.25$

### 3.4 Corroboration & Multi-Modal Diversity
Independent corroboration increases confidence non-linearly:
* $N_{\text{indep}}$: Number of independent reporting principals.
* Modality Bonus: Diversity of evidence modalities (e.g., sensor telemetry + ground photo + text report).
* Contradiction Penalty: Observations reporting "Road clear / Traffic moving normally" directly diminish the hazard evidence pool.

### 3.5 Calibrated Confidence Levels
Rather than presenting arbitrary pseudo-probabilities (e.g., "91.4% flooded"), NammaSignal provides an **Evidence Confidence Level**:
* **VERY_HIGH**: Authoritative confirmation OR $\ge 3$ independent corroborating sources with at least one photo/sensor within the last 15 minutes.
* **HIGH**: $\ge 2$ independent fresh observations agreeing on severity within 30 minutes.
* **MEDIUM**: Single unverified report with corroborating official weather conditions (e.g. active cloudburst in ward).
* **LOW / UNCERTAIN**: Isolated unverified citizen observation or conflicting reports.
* **CLEARED**: Recent verified observation or multiple independent reports confirming the road is passable.

---

## 4. AWS Open-Source Stack Research & Evaluation

### 4.1 AWS Cedar Policy Engine
* **Technology**: Cedar is an open-source policy language and evaluation engine written in Rust with formal mathematical verification roots.
* **Relevance**: In NammaSignal, authorization is a first-class security boundary. Only `VerifiedResponder` and `OfficialAuthority` can mark an event as verified or resolved; `Citizen` principals can submit raw observations; `SystemAgent` processes pipelines under least-privilege constraints.
* **Integration**: Native integration via `cedarpy` (Rust Python bindings, precompiled CPython 3.13 wheel). Cedar policies are stored as formal `.cedar` files with strong schemas.

### 4.2 AWS Strands Agents SDK
* **Technology**: Strands Agents (`strands-agents`) is the open-source AWS framework for building model-driven agent harnesses.
* **Relevance**: Used for structured extraction and multi-agent workflows. 
  - *Agent 1 (Observation Interpreter)*: Parses unstructured Kannada/English/Hinglish citizen reports into structured schemas with explicit uncertainty flags.
  - *Agent 2 (Evidence Analyst)*: Detects contradictions, duplicate nuance, and generates natural-language provenance summaries.
  - *Agent 3 (Advisory Generator)*: Synthesizes high-clarity, action-oriented commuter bulletins.
* **Security Guardrail**: Model outputs are treated as **untrusted data**. Structured outputs are validated against strict Pydantic v2 schemas; LLM outputs NEVER mutate transactional state directly or bypass Cedar authorization.

### 4.3 OpenSearch (Local & Vector)
* **Technology**: OpenSearch provides distributed full-text, geospatial (`geo_point`, `geo_shape`), and temporal search.
* **Relevance**: Efficiently queries active hazard clusters within a bounding radius (e.g., $500\text{m}$ buffer around Silk Board) within a sliding time window (e.g., last 2 hours).

---

## 5. Event Correlation & Spatial-Temporal Clustering

Two observations $O_A$ and $O_B$ belong to the same Hazard Event $E$ if and only if:
1. **Geographic Proximity**: $\text{HaversineDist}(O_A.\text{loc}, O_B.\text{loc}) \le R_{\text{threshold}}$ (typically $250\text{m}$ for urban road segments; $500\text{m}$ for major junctions).
2. **Temporal Window**: $|O_A.\text{timestamp} - O_B.\text{timestamp}| \le T_{\text{window}}$ (typically $120\text{ minutes}$).
3. **Semantic Hazard Compatibility**: $\text{HazardType}(O_A) \equiv \text{HazardType}(O_B)$ (or complementary, e.g., "heavy water accumulation" and "traffic stand-still due to water").
4. **Non-Contradiction**: Clearance observations do not merge as new hazard points; they update the assessment state of the active event.
