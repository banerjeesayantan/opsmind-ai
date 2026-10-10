# OpsMind AI — Backend Engine Design & Fix Specification

## 1. Executive Summary & Objective

**Project:** OpsMind AI  
**Scope:** Complete the backend engine and data persistence foundation for incident investigation, root cause diagnosis, remediation planning, approval gating, action execution, and post-action verification.  
**Guiding Principle:** Inspect actual repository implementation, reuse existing schemas, models, and interfaces, avoid unnecessary migrations or architecture rewrites, ensure atomic transactions, enforce strict state machine lifecycle transitions, and validate via automated tests.

---

## 2. Current Architecture & File Paths

### Architecture Map
The OpsMind backend consists of four primary tiers:
1. **API Tier (FastAPI):** Exposes RESTful endpoints for incident lifecycle and Swagger demo surface (`/docs`).
   - `app/main.py`: Application entry point, middleware, exception handlers.
   - `app/api/v1/api.py`: Top-level v1 router (`/auth`, `/chatbot`, `/incidents`).
   - `app/api/v1/incidents.py`: Incident endpoints for creation, investigation, remediation, approval, execution, verification, and inspection.
   - `app/api/v1/auth.py`: JWT-based authentication and user context (`get_current_user`).
   - `app/schemas/incident.py`: Pydantic request and response schemas for all incident APIs.

2. **Investigation & Execution Engine (LangGraph & Control Layer):**
   - `app/investigation/graph.py`: StateGraph assembling the linear investigation pipeline.
   - `app/investigation/schemas.py`: Ephemeral graph state schemas (`InvestigationState`, `HypothesisCandidate`, `DiagnosisResult`, `RemediationCandidate`, `TimelineEntry`, `EvidenceCitation`).
   - `app/investigation/nodes/`:
     - `evidence_collector.py`: Calls telemetry service to gather logs, metrics, deployments.
     - `timeline_builder.py`: Converts discrete logs and deployments into chronological events.
     - `hypothesis_generator.py`: Structured LLM proposing candidate causes citing timeline indices.
     - `evidence_validator.py`: Structured LLM evaluating evidentiary justification for claims.
     - `impact_analyzer.py`: Structured LLM assessing business impact severity and summary.
     - `diagnosis.py`: Selects highest-confidence validated hypothesis or reports inconclusive.
     - `remediation_planner.py`: Recommends 1 of 4 closed remediation actions with strict parameter validation and grounding.
   - `app/investigation/risk.py`: Deterministic risk classifier (`classify_risk`, `requires_human_approval`).
   - `app/investigation/action_executor.py`: Controlled action execution simulator (`ControlledActionExecutor`).
   - `app/investigation/verification.py`: Post-action metric/log comparison service (`VerificationService`).

3. **Persistence & Data Store Tier (SQLModel / SQLAlchemy):**
   - `app/services/persistence.py`: `IncidentPersistenceService` — single authoritative read/write repository for incident domain entities.
   - `app/services/database.py`: `DatabaseService` — SQLAlchemy engine setup with connection pooling.
   - `app/models/`:
     - `base.py`: `BaseModel` providing `created_at` timestamp.
     - `incident_enums.py`: Domain enums (`IncidentStatus`, `Severity`, `EvidenceSource`, `HypothesisStatus`, `RemediationActionType`, `RiskLevel`, `ApprovalStatus`, `ExecutionStatus`).
     - `incident.py`: `Incident` table model (root aggregate).
     - `evidence.py`: `Evidence` table model.
     - `hypothesis.py`: `Hypothesis` table model.
     - `diagnosis.py`: `Diagnosis` table model.
     - `remediation.py`: `Remediation` table model.
     - `approval.py`: `Approval` table model.
     - `action_execution.py`: `ActionExecution` table model.
     - `verification.py`: `Verification` table model.
     - `incident_event.py`: `IncidentEvent` table model (append-only timeline).
     - `user.py`: `User` table model.
     - `database.py`: Central model registry for SQLAlchemy metadata.

4. **Telemetry & Mock Integrations:**
   - `app/telemetry/schemas.py`: `EvidenceBundle`, `LogEntry`, `MetricPoint`, `DeploymentEvent`, `TimeWindow`.
   - `app/telemetry/mock_sources.py`: In-memory mock sources for `$0` local development and testing.

---

## 3. Database Entities & Relationship Model

```
                    +-------------------+
                    |       User        |
                    +-------------------+
                              | 1
                              |
                              | 0..* (created_by)
+-------------------+         v
|   IncidentEvent   |* <--- [Incident] 1 -------------> 0..* [Evidence]
| (append timeline) |           | 1
+-------------------+           |
                                | 1..*
                                v
                         [Hypothesis] 1 <----+
                                |            | (hypothesis_id)
                                | 1..*       |
                                v            |
                           [Diagnosis] 1 ----+
                                | 1
                                |
                                | 0..*
                                v
                          [Remediation] 1
                                |
             +------------------+------------------+
             | 1                                   | 1
             v 1..*                                v 1..*
        [Approval]                          [ActionExecution] 1
                                                   |
                                                   | 0..*
                                                   v
                                             [Verification]
```

### Entity Responsibilities & Foreign Key Mapping:
1. **Incident (`incident` table):**
   - PK: `id` (UUID str). Fields: `title`, `description`, `severity`, `status`, `created_by` (FK -> `user.id`), `resolved_at`, `created_at`.
   - Relationships: `events`, `evidence`, `hypotheses`, `diagnoses`, `remediations`, `approvals`, `action_executions`, `verifications`.
2. **Evidence (`evidence` table):**
   - PK: `id` (int). FK: `incident_id` (FK -> `incident.id`). Fields: `source`, `source_reference`, `content`, `raw_data` (JSON), `occurred_at`, `collected_at`.
3. **IncidentEvent (`incidentevent` table):**
   - PK: `id` (int). FK: `incident_id` (FK -> `incident.id`). Fields: `event_type`, `description`, `occurred_at`, `event_metadata` (JSON). Append-only timeline.
4. **Hypothesis (`hypothesis` table):**
   - PK: `id` (int). FK: `incident_id` (FK -> `incident.id`). Fields: `statement`, `reasoning`, `confidence`, `status`, `supporting_evidence_ids` (JSON list[int]).
5. **Diagnosis (`diagnosis` table):**
   - PK: `id` (int). FK: `incident_id` (FK -> `incident.id`), `hypothesis_id` (FK -> `hypothesis.id`). Fields: `probable_cause`, `confidence`, `impact`, `is_active`, `diagnosed_at`.
6. **Remediation (`remediation` table):**
   - PK: `id` (int). FK: `incident_id` (FK -> `incident.id`), `diagnosis_id` (FK -> `diagnosis.id`). Fields: `action_type`, `parameters` (JSON), `risk_level`, `rationale`, `is_selected`, `recommended_at`.
7. **Approval (`approval` table):**
   - PK: `id` (int). FK: `incident_id` (FK -> `incident.id`), `remediation_id` (FK -> `remediation.id`), `decided_by` (FK -> `user.id`, nullable). Fields: `status`, `requested_at`, `decided_at`, `reason`.
8. **ActionExecution (`actionexecution` table):**
   - PK: `id` (int). FK: `incident_id` (FK -> `incident.id`), `remediation_id` (FK -> `remediation.id`). Fields: `status`, `executed_at`, `result` (JSON), `error_message`.
9. **Verification (`verification` table):**
   - PK: `id` (int). FK: `incident_id` (FK -> `incident.id`), `action_execution_id` (FK -> `actionexecution.id`). Fields: `checked_at`, `recovered` (bool, nullable), `evidence_after_ids` (JSON list[int]), `notes`.

---

## 4. Engine Execution Flow & Node Contracts

### Execution Pipeline

```
[Incident Created] (status: NEW)
       |
       v (POST /investigate)
[Set status: INVESTIGATING]
       |
       +---> [evidence_collector]
       |            |
       |            v
       +---> [timeline_builder]
       |            |
       |            v
       +---> [hypothesis_generator] (LLM)
       |            |
       |            v
       +---> [evidence_validator] (LLM)
       |            |
       |            v
       +---> [impact_analyzer] (LLM)
       |            |
       |            v
       +---> [diagnosis]
       |            |
       |            v
       +---> [remediation_planner] (LLM)
       |
       v
[Atomic Persistence: Evidence + Events + Hypotheses + Diagnosis + Remediation + Approval]
       |
       +--> Outcome A: Valid diagnosis -> status: DIAGNOSED (or AWAITING_APPROVAL if medium/high risk remediation attached)
       +--> Outcome B: Inconclusive -> status: UNRESOLVED
```

### Detailed Node Contract Specification

| Node Name | Input State | DB Reads | Processing Logic | DB Writes | Output State |
|---|---|---|---|---|---|
| `evidence_collector` | `service`, `time_window` | None | Queries `TelemetryService` for logs, metrics, deployments in `time_window` | None | `evidence: EvidenceBundle` |
| `timeline_builder` | `evidence` | None | Extracts logs and deployments, sorts chronologically by timestamp | None | `timeline: list[TimelineEntry]` |
| `hypothesis_generator` | `service`, `timeline` | None | Formats numbered prompt; calls structured LLM; validates indices 1..N against real entries; drops ungrounded candidates | None | `hypotheses: list[HypothesisCandidate]` |
| `evidence_validator` | `hypotheses` | None | Prompts structured LLM per hypothesis to confirm cited evidence genuinely supports claim; updates confidence | None | `validated_hypotheses: list[HypothesisCandidate]` |
| `impact_analyzer` | `service`, `evidence`, `timeline`, `validated_hypotheses` | None | Prompts structured LLM to evaluate concrete metrics & log counts; determines severity | None | `impact: ImpactAssessment` |
| `diagnosis` | `validated_hypotheses`, `impact` | None | Chooses hypothesis with `max(confidence)`; if none, generates inconclusive diagnosis with confidence 0.0 | None | `diagnosis: DiagnosisResult` |
| `remediation_planner` | `service`, `diagnosis`, `evidence` | None | Prompts structured LLM for 1 of 4 closed actions; validates schema (`extra="forbid"`) and grounds parameters (`deployment_id`, `service`) against evidence | None | `remediation: Optional[RemediationCandidate]` |

---

## 5. Confirmed Bugs & Root Cause Analysis

### Bug 1: Verification Service Name Mismatch
- **File & Function:** `app/api/v1/incidents.py` (`verify_execution`, lines 482 & 491)
- **Defect:** `persistence.get_evidence_bundle(incident_id, service=incident.title)` passes `incident.title` (e.g., `"Checkout latency spike"`) rather than the service name (`"checkout"`). `verification_service.verify()` receives the incident title as the service name, causing mock or real telemetry collection to fail or return empty data for the after-window.
- **Root Cause:** `Incident` model does not persist `service` as a dedicated column; `service` was only recorded in `incident_created` and `investigation_started` timeline events. The route author fallback was to pass `incident.title`.

### Bug 2: Unenforced Incident Lifecycle State Machine Transitions
- **File & Function:** `app/services/persistence.py` (`update_incident_status`, lines 125-152) and `app/api/v1/incidents.py` (lines 223, 403-453, 458-510)
- **Defect:** `update_incident_status()` permits any transition without validation (e.g. `NEW` -> `RESOLVED` directly). In `investigate_incident`, the status is touched with `incident.status` rather than being set to `INVESTIGATING`. Actions can be executed or verified on incidents that are already terminal (`RESOLVED`) or uninvestigated.
- **Root Cause:** No transition matrix or validation guard was implemented in `IncidentPersistenceService.update_incident_status`.

### Bug 3: Non-Atomic Multi-Commit Persistence in `persist_investigation_result`
- **File & Function:** `app/services/persistence.py` (`persist_investigation_result`, lines 268, 302, 327, 335)
- **Defect:** Four separate `session.commit()` calls occur in sequence. If hypothesis insertion, diagnosis mapping, or incident updating fails, preceding evidence and timeline rows remain committed. This produces partial persistence and orphan records.
- **Root Cause:** Commits were placed after individual loops rather than wrapping the entire operation in a single atomic transaction.

### Bug 4: Superseded Diagnosis Not Deactivated
- **File & Function:** `app/services/persistence.py` (`persist_investigation_result`, lines 304-328)
- **Defect:** When an incident is re-investigated (e.g., after failed verification where status returned to `INVESTIGATING`), a new `Diagnosis` row is inserted with `is_active=True`, but existing active diagnoses are not deactivated (`is_active=False`). `get_active_diagnosis` subsequently returns arbitrary rows via `.first()`.
- **Root Cause:** Omission of a deactivation query before inserting a new active diagnosis (in contrast to `persist_remediation`, which correctly unselects previous remediations).

### Bug 5: Duplicate and Invalid Action Executions & Verifications
- **File & Function:** `app/api/v1/incidents.py` (`execute_remediation` line 403, `verify_execution` line 458)
- **Defect:**
  - `execute_remediation` permits repeated execution calls even when an execution for that remediation has already completed with `SIMULATED` or `SUCCEEDED`.
  - `verify_execution` does not check whether the target execution succeeded or failed (allowing verification of `FAILED` executions).
  - `verify_execution` allows repeated verifications on the same execution attempt, leading to redundant verification rows and conflicting resolution metrics.
- **Root Cause:** Missing idempotency / guard checks on `ActionExecution.status` and existing `Verification` records.

### Bug 6: Inadequate Exception Boundaries Around Graph Invocation
- **File & Function:** `app/api/v1/incidents.py` (`investigate_incident`, lines 233-238)
- **Defect:** `await graph.ainvoke(initial_state)` is unhandled. If the LLM throws an API error, rate limit, or network error, an unhandled exception bubbles up as HTTP 500, leaving the incident stuck without an error event on its timeline or updated recoverable state.
- **Root Cause:** Lack of controlled exception handling around AI execution boundary.

---

## 6. Minimal Proposed Fixes

### Fix 1: Service Name Resolution for Evidence Bundle & Verification
- In `IncidentPersistenceService`: Add helper `get_incident_service(incident_id: str) -> str` that inspects the incident's timeline events (`incident_created`, `investigation_started`) to locate `event_metadata["service"]`. If not found, safely falls back to `incident.title`.
- In `app/api/v1/incidents.py` (`verify_execution`): Use `service_name = await persistence.get_incident_service(incident_id)` and pass `service=service_name` to `get_evidence_bundle` and `verification_service.verify()`.

### Fix 2: Strict Lifecycle State Machine & Transition Validation
- In `app/models/incident_enums.py` or `app/services/persistence.py`: Define valid lifecycle transitions:
  ```python
  VALID_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
      IncidentStatus.NEW: {IncidentStatus.INVESTIGATING},
      IncidentStatus.INVESTIGATING: {IncidentStatus.DIAGNOSED, IncidentStatus.UNRESOLVED},
      IncidentStatus.DIAGNOSED: {IncidentStatus.AWAITING_APPROVAL, IncidentStatus.REMEDIATING, IncidentStatus.INVESTIGATING},
      IncidentStatus.AWAITING_APPROVAL: {IncidentStatus.REMEDIATING, IncidentStatus.DIAGNOSED},
      IncidentStatus.REMEDIATING: {IncidentStatus.VERIFYING, IncidentStatus.REMEDIATING, IncidentStatus.DIAGNOSED},
      IncidentStatus.VERIFYING: {IncidentStatus.RESOLVED, IncidentStatus.INVESTIGATING},
      IncidentStatus.RESOLVED: set(),
      IncidentStatus.UNRESOLVED: {IncidentStatus.INVESTIGATING},
  }
  ```
- In `IncidentPersistenceService.update_incident_status(incident_id, status)`:
  Validate `current_status == new_status` (no-op) OR `new_status in VALID_TRANSITIONS.get(current_status, set())`. If invalid, raise `ValueError(f"Invalid transition from {current_status.value} to {status.value}")`.
- In `investigate_incident`:
  Check that the incident is in a state eligible for investigation (`NEW`, `INVESTIGATING`, `UNRESOLVED`, or `INVESTIGATING` following non-recovery). Transition status to `INVESTIGATING` immediately at the start of the investigation.

### Fix 3: Atomic Transaction for `persist_investigation_result`
- Remove intermediate `session.commit()` calls at lines 268, 302, 327.
- Use `session.flush()` after adding rows so that generated primary keys (`row.id`) are populated for downstream references (`hypothesis.supporting_evidence_ids`, `diagnosis.hypothesis_id`).
- Execute a single `session.commit()` after all entities (evidence, events, hypotheses, diagnosis, incident status update) are added. If any exception occurs, SQLAlchemy session context manager rolls back the transaction automatically.

### Fix 4: Deactivate Superseded Diagnoses
- In `persist_investigation_result`, before creating a new `Diagnosis` with `is_active=True`, query:
  ```python
  active_stmt = select(Diagnosis).where(
      Diagnosis.incident_id == incident_id, Diagnosis.is_active == True
  )
  for prev in session.exec(active_stmt).all():
      prev.is_active = False
      session.add(prev)
  ```
- Ensure only the latest confirmed diagnosis remains active.

### Fix 5: Action Execution & Verification Guards
- In `execute_remediation`:
  - Check whether an execution already succeeded or simulated:
    ```python
    existing = await persistence.list_action_executions(incident_id)
    if any(e.remediation_id == remediation_id and e.status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.SIMULATED) for e in existing):
        raise HTTPException(status_code=409, detail="Remediation action has already been executed.")
    ```
- In `verify_execution`:
  - Verify that `execution.status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.SIMULATED)`. If not, raise `409 Conflict`.
  - Check whether a verification has already been recorded for `execution_id`. If so, raise `409 Conflict`.

### Fix 6: AI / Graph Exception Handling Boundary
- Wrap `await graph.ainvoke(initial_state)` in `try/except Exception as exc`:
  - Log error with context.
  - Append timeline event `investigation_failed` with error summary.
  - Surface a clean HTTP 502 / 500 error: `"Investigation graph failed: ..."` without leaking raw internals.

---

## 7. Required Tests

1. **State Machine Transitions (`test_state_machine.py`):**
   - Valid progression: `NEW` -> `INVESTIGATING` -> `DIAGNOSED` -> `AWAITING_APPROVAL` -> `REMEDIATING` -> `VERIFYING` -> `RESOLVED`.
   - Inconclusive path: `NEW` -> `INVESTIGATING` -> `UNRESOLVED`.
   - Recovery failure retry path: `VERIFYING` -> `INVESTIGATING` -> `DIAGNOSED`.
   - Invalid jumps rejected with `ValueError`: `NEW` -> `RESOLVED`, `NEW` -> `REMEDIATING`, `RESOLVED` -> `INVESTIGATING`.
2. **Atomic Persistence & Rollback (`test_atomic_persistence.py`):**
   - Verify all evidence, hypotheses, diagnosis, timeline events commit atomically.
   - Verify simulated failure during persistence leaves no orphan evidence or half-persisted hypotheses.
3. **Diagnosis Deactivation on Re-investigation:**
   - Run investigation 1 -> diagnosis A active.
   - Re-investigate -> diagnosis B active, diagnosis A has `is_active == False`.
   - `get_active_diagnosis` unambiguously returns diagnosis B.
4. **Execution & Verification Guards:**
   - Executing an already executed action raises 409 Conflict.
   - Verifying a failed action execution raises 409 Conflict.
   - Verifying the same execution twice raises 409 Conflict.
5. **End-to-End Incident Workflow:**
   - Full flow from incident creation to verification with mock telemetry, asserting every entity and relationship is written and retrievable via fresh sessions.

---

## 8. Risks and Dependencies
- **External LLM Dependency ($0 Free Tier):** Unit and integration tests must run against injectable stubs/fakes (`FakeStructuredLLM`) to guarantee zero flakes and zero reliance on external network/API quotas.
- **Database Engine Parity:** Postgres 16 in production with automatic fallback to file-backed SQLite with `PRAGMA foreign_keys=ON` in testing. All queries and transactions must work identically on both.
- **Backward Compatibility:** All existing endpoints, response models, and method signatures must be preserved.
