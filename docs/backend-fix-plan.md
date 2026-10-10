# OpsMind AI — Backend Repair & Verification Plan

## 1. Executive Summary

This document details the defect audit, severity classification (P0, P1, P2), root-cause analysis, minimal repairs, and regression test plan for the OpsMind AI incident response platform backend (`C:\projects\opsmind-ai`).

OpsMind AI automates the end-to-end incident lifecycle:
$$\text{Incident} \to \text{Evidence Collection} \to \text{Timeline Construction} \to \text{Hypothesis Generation} \to \text{Diagnosis} \to \text{Remediation Planning} \to \text{Approval Gate} \to \text{Action Execution} \to \text{Verification} \to \text{Resolved}$$

All fixes preserve existing database models, table relationships, schemas, and public API contracts while ensuring data integrity, transaction atomicity, lifecycle state machine enforcement, and idempotent action gating.

---

## 2. Issue Inventory & Classification

### Issue 1: Non-Atomic Investigation Persistence Leaving Inconsistent Partial Data (P0)

- **File and Function:** `app/services/persistence.py` — `IncidentPersistenceService.persist_investigation_result`
- **Expected Behavior:** Persisting an investigation result (evidence records, hypothesis records, diagnosis record, and incident status/severity update) must succeed or fail as a single atomic transaction. If any entity fails to persist, all writes in that investigation cycle must roll back.
- **Actual Behavior:** The function called `session.commit()` four separate times (after evidence, after hypotheses, after diagnosis, and after incident update). If diagnosis generation or database constraints failed midway, evidence and hypothesis rows remained committed as orphaned records, but the incident status was not updated.
- **Root Cause:** Multiple intermediate `session.commit()` calls were issued before the full entity graph was staged.
- **Severity:** **P0** (Data corruption / Partial persistence state).
- **Minimal Proposed Fix:**
  - Replace intermediate `session.commit()` calls with `session.flush()` so database IDs (`id`) are generated for foreign key references.
  - Execute a single `session.commit()` at the very end of the unit of work.
  - Wrap in standard session context manager so exceptions trigger an immediate session rollback.
- **Regression Test Required:** `test_persist_investigation_result_is_atomic_on_failure` in `tests/test_persistence.py`.

---

### Issue 2: Re-investigation Created Duplicate Active Diagnoses Without Deactivating Prior Active Diagnosis (P0)

- **File and Function:** `app/services/persistence.py` — `IncidentPersistenceService.persist_investigation_result`
- **Expected Behavior:** An incident can have multiple historic diagnoses across re-investigation attempts, but only one diagnosis must be marked `is_active=True` at any time. When a new diagnosis is recorded, previous active diagnoses for that `incident_id` must have `is_active` set to `False`.
- **Actual Behavior:** `persist_investigation_result` created a new `Diagnosis` with `is_active=True` without checking or updating existing active diagnosis records, leaving multiple active diagnoses for a single incident.
- **Root Cause:** Missing query to deactivate predecessor diagnoses prior to inserting the new diagnosis record.
- **Severity:** **P0** (Data corruption / Inconsistent query results for active diagnosis).
- **Minimal Proposed Fix:**
  - Prior to adding the new `Diagnosis` record, query existing active diagnoses:
    ```python
    active_prior = session.exec(
        select(Diagnosis).where(Diagnosis.incident_id == incident_id, Diagnosis.is_active == True)
    ).all()
    for prior in active_prior:
        prior.is_active = False
        session.add(prior)
    ```
- **Regression Test Required:** `test_reinvestigation_deactivates_prior_diagnosis` in `tests/test_persistence.py`.

---

### Issue 3: Incident Lifecycle Transitions Allowed Arbitrary State Jumps & Out-of-Order Lifecycle Progression (P0)

- **File and Function:** `app/services/persistence.py` — `IncidentPersistenceService.update_incident_status`
- **Expected Behavior:** Incident status transitions must follow a strict directed state machine:
  - `NEW` $\to$ `INVESTIGATING`
  - `INVESTIGATING` $\to$ `DIAGNOSED` | `UNRESOLVED`
  - `DIAGNOSED` $\to$ `REMEDIATING` | `INVESTIGATING` | `RESOLVED` | `UNRESOLVED`
  - `REMEDIATING` $\to$ `VERIFYING` | `INVESTIGATING` | `RESOLVED` | `UNRESOLVED`
  - `VERIFYING` $\to$ `RESOLVED` | `INVESTIGATING` | `UNRESOLVED`
  - `RESOLVED` $\to$ terminal (cannot transition out)
  - `UNRESOLVED` $\to$ `INVESTIGATING` (re-open)
- **Actual Behavior:** `update_incident_status` accepted any `IncidentStatus` value and wrote it to the database with no validation of current state vs target state. Additionally, `resolved_at` timestamps were not synchronized with status changes.
- **Root Cause:** Absence of state transition rules and transition guard checks in the persistence service.
- **Severity:** **P0** (Lifecycle consistency violation).
- **Minimal Proposed Fix:**
  - Define `VALID_TRANSITIONS` mapping in `app/services/persistence.py`.
  - In `update_incident_status(incident_id, status, force=False)`:
    - Return early on no-op (`current == target`).
    - Validate transition against `VALID_TRANSITIONS` (raise `ValueError` if invalid and `not force`).
    - Synchronize `incident.resolved_at`: set `datetime.now(UTC)` on entering `RESOLVED` or `UNRESOLVED`, and clear `resolved_at = None` if transitioned back to `INVESTIGATING`.
- **Regression Test Required:** `test_update_incident_status_validates_transitions` in `tests/test_persistence.py`.

---

### Issue 4: Investigation Crash Left Incident in Dangling In-Progress State (P1)

- **File and Function:** `app/api/v1/incidents.py` — `investigate_incident`
- **Expected Behavior:** If the LangGraph execution fails with an unhandled exception or LLM outage, the failure must be captured, logged, a timeline event recorded, and the incident moved to `UNRESOLVED` rather than staying permanently in `INVESTIGATING` or unhandled 500 without tracking.
- **Actual Behavior:** An unhandled exception in `graph.ainvoke()` crashed out with an unhandled HTTP 500 error, leaving the incident status inconsistent.
- **Root Cause:** Missing `try/except` around `graph.ainvoke()` with lifecycle cleanup and event recording.
- **Severity:** **P1** (Reliability & Lifecycle observability).
- **Minimal Proposed Fix:**
  - Transition incident status to `IncidentStatus.INVESTIGATING` before starting `graph.ainvoke()`.
  - Wrap `graph.ainvoke()` in `try ... except Exception as exc`.
  - On failure, record `investigation_failed` event on the incident timeline, transition status to `IncidentStatus.UNRESOLVED`, and raise `HTTPException(500, detail=f"Investigation failed: {exc}")`.
- **Regression Test Required:** `test_investigate_failure_records_event_and_sets_unresolved` in `tests/test_api_incidents.py`.

---

### Issue 5: Service Name Mismatch in Post-Action Telemetry Verification (P1)

- **File and Function:** `app/api/v1/incidents.py` — `verify_execution`
- **Expected Behavior:** When collecting telemetry to verify remediation impact, the telemetry service must query the target service name (e.g., `"checkout"`, `"payment"`, `"orders"`).
- **Actual Behavior:** `verify_execution` passed `service=incident.title` (e.g., `"Checkout latency spike"`) to `get_evidence_bundle` and `verification_service.verify()`.
- **Root Cause:** Passing human-readable incident title string where a canonical service key was expected.
- **Severity:** **P1** (Telemetry verification failure on live data).
- **Minimal Proposed Fix:**
  - Add helper `get_incident_service(incident_id)` in `IncidentPersistenceService` that resolves service from timeline events and evidence metadata.
  - In `verify_execution`, retrieve `service_name = await persistence.get_incident_service(incident_id) or incident.title`.
  - Make `service` optional in `get_evidence_bundle(incident_id, service=None)` so it falls back cleanly to the persisted service.
- **Regression Test Required:** `test_verify_execution_uses_service_from_evidence` in `tests/test_api_incidents.py`.

---

### Issue 6: Re-Execution of Already Completed Remediations Allowed Duplicate Runs (P1)

- **File and Function:** `app/api/v1/incidents.py` — `execute_remediation`
- **Expected Behavior:** A remediation action that has already completed (`SUCCEEDED` or `SIMULATED`) must not be re-executed. If an execution is in progress (`PENDING`), concurrent execution attempts must be rejected with 409 Conflict.
- **Actual Behavior:** Calling `POST /incidents/{id}/remediations/{remediation_id}/execute` created and completed another `ActionExecution` record regardless of prior executions.
- **Root Cause:** Absence of guard checking existing execution records for the targeted `remediation_id`.
- **Severity:** **P1** (Idempotency and safety violation).
- **Minimal Proposed Fix:**
  - In `execute_remediation`, check:
    ```python
    existing_executions = await persistence.list_action_executions(incident_id)
    remediation_executions = [e for e in existing_executions if e.remediation_id == remediation_id]
    if any(e.status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.SIMULATED) for e in remediation_executions):
        raise HTTPException(409, "This remediation action has already been executed successfully.")
    if any(e.status == ExecutionStatus.PENDING for e in remediation_executions):
        raise HTTPException(409, "An action execution for this remediation is already in progress.")
    ```
- **Regression Test Required:** `test_cannot_reexecute_already_completed_remediation` in `tests/test_api_incidents.py`.

---

### Issue 7: Verification Allowed on Failed Executions or Already-Verified Executions (P1)

- **File and Function:** `app/api/v1/incidents.py` — `verify_execution`
- **Expected Behavior:** Only `SUCCEEDED` or `SIMULATED` executions can be verified. An execution that `FAILED` must not trigger recovery verification. An execution that has already been verified must reject re-verification with 409 Conflict.
- **Actual Behavior:** Any `action_execution_id` could be verified, even if the action failed or had already been verified.
- **Root Cause:** Missing status check and missing uniqueness check on `action_execution_id` across existing verifications.
- **Severity:** **P1** (Integrity of verification records).
- **Minimal Proposed Fix:**
  - In `verify_execution`:
    ```python
    if execution.status not in (ExecutionStatus.SUCCEEDED, ExecutionStatus.SIMULATED):
        raise HTTPException(409, f"Cannot verify execution with status {execution.status.value!r}.")
    existing_verifications = await persistence.list_verifications(incident_id)
    if any(v.action_execution_id == execution_id for v in existing_verifications):
        raise HTTPException(409, "Action execution has already been verified.")
    ```
- **Regression Test Required:** `test_cannot_verify_failed_or_duplicate_execution` in `tests/test_api_incidents.py`.

---

### Issue 8: Operations Allowed on Already-Resolved Incidents (P1)

- **File and Function:** `app/api/v1/incidents.py` — `investigate_incident`, `recommend_remediation`, `execute_remediation`
- **Expected Behavior:** An incident in `RESOLVED` status is closed. Further investigations, new remediations, and action executions must be rejected with 409 Conflict.
- **Actual Behavior:** An incident in `RESOLVED` status could still accept new `/investigate`, `/remediations`, and `/execute` calls.
- **Root Cause:** Missing check for `incident.status == IncidentStatus.RESOLVED` on mutation endpoints.
- **Severity:** **P1** (Incident lifecycle integrity).
- **Minimal Proposed Fix:**
  - Add explicit guard in `investigate_incident`, `recommend_remediation`, and `execute_remediation`:
    ```python
    if incident.status == IncidentStatus.RESOLVED:
        raise HTTPException(409, detail=f"Incident {incident_id!r} is already resolved.")
    ```
- **Regression Test Required:** `test_resolved_incident_rejects_further_mutations` in `tests/test_api_incidents.py`.

---

### Issue 9: Unused or Redundant Foreign Key Indexes on Query-Heavy Aggregates (P2)

- **File and Function:** `app/models/evidence.py`, `app/models/hypothesis.py`, `app/models/remediation.py`
- **Expected Behavior:** Indexing foreign keys `incident_id` allows rapid filtering on large incident histories.
- **Actual Behavior:** SQLite development mode handles these via table scans; PostgreSQL production benefits from explicit indexes on `incident_id` and `action_execution_id`.
- **Root Cause:** Standard SQLModel foreign keys index by default on primary keys, but secondary lookups on `incident_id` benefit from indexed foreign keys.
- **Severity:** **P2** (Maintainability & Query performance under high volume).
- **Minimal Proposed Fix:** Existing `Field(foreign_key=..., index=True)` is present on most models; verified models are optimized without requiring schema migrations.
- **Regression Test Required:** Existing test suite performance assertion.

---

## 3. Repair Execution Status

| Issue | Severity | Status | Files Modified |
|---|---|---|---|
| Issue 1: Atomic Persistence | P0 | **Fixed** | `app/services/persistence.py` |
| Issue 2: Active Diagnosis Deactivation | P0 | **Fixed** | `app/services/persistence.py` |
| Issue 3: Lifecycle State Machine Transitions | P0 | **Fixed** | `app/services/persistence.py` |
| Issue 4: Investigation Crash Handling | P1 | **Fixed** | `app/api/v1/incidents.py` |
| Issue 5: Telemetry Service Resolution | P1 | **Fixed** | `app/services/persistence.py`, `app/api/v1/incidents.py` |
| Issue 6: Re-Execution Duplicate Guards | P1 | **Fixed** | `app/api/v1/incidents.py` |
| Issue 7: Verification Duplicate & Status Guards | P1 | **Fixed** | `app/api/v1/incidents.py` |
| Issue 8: Resolved Incident Mutation Guards | P1 | **Fixed** | `app/api/v1/incidents.py` |
| Issue 9: Model Indexes & Relationships | P2 | **Verified** | `app/models/*` |

---

## 4. Verification & Testing Strategy

The test suite will verify all repaired paths using isolated test sessions:
1. `tests/test_persistence.py`:
   - Valid lifecycle transitions (`NEW` $\to$ `INVESTIGATING` $\to$ `DIAGNOSED` $\to$ `REMEDIATING` $\to$ `VERIFYING` $\to$ `RESOLVED`).
   - Invalid lifecycle transition rejection (`NEW` $\to$ `RESOLVED` raises `ValueError`).
   - Atomic rollback upon failure during investigation persistence.
   - Superseding active diagnosis on re-investigation.
2. `tests/test_api_incidents.py`:
   - End-to-end incident lifecycle test.
   - Investigation crash transitions incident to `UNRESOLVED` and records timeline event.
   - Resolved incident rejects `/investigate`, `/remediations`, and `/execute` with 409 Conflict.
   - Duplicate execution prevention (409 Conflict on re-execution).
   - Duplicate verification prevention (409 Conflict on re-verifying).
   - Service name resolution from evidence metadata.
