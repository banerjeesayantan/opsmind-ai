# Incident Flow

This document walks through OpsMind's full pipeline, stage by stage, and
maps each stage to the code that implements it and the API endpoint that
drives it.

```
Incident → Evidence → Timeline → Hypotheses → Validation → Impact → Diagnosis
        → Remediation → Approval → Action → Verification
```

Every arrow above is a real `IncidentStatus` transition, persisted by
`app.services.persistence.IncidentPersistenceService` - nothing in this
pipeline is implicit or in-memory-only. The full enum
(`app.models.incident_enums.IncidentStatus`) is:

```
NEW → INVESTIGATING → DIAGNOSED → AWAITING_APPROVAL → REMEDIATING
    → VERIFYING → RESOLVED
                → UNRESOLVED   (if investigation can't confirm a cause)
```

---

## 1. Incident

**Endpoint:** `POST /api/v1/incidents`
**Model:** `app.models.incident.Incident`

An incident starts as just a title, description, severity, and the name of
the affected service. Status begins at `NEW`. Creating an incident also
appends an `incident_created` entry to its timeline
(`IncidentPersistenceService.add_incident_event`).

## 2. Evidence → Timeline → Hypotheses → Validation → Impact → Diagnosis

**Endpoint:** `POST /api/v1/incidents/{id}/investigate`
**Code:** `app.investigation.graph.build_investigation_graph`,
`app.investigation.nodes.*`

This is a single LangGraph pipeline, run in one call:

| Node | What it does | LLM call? |
|---|---|---|
| `evidence_collector` | Pulls logs/metrics/deployments for the service + time window via `app.telemetry.TelemetryService` (mock sources by default - a real Prometheus/Loki/GitHub adapter is a drop-in swap) | No |
| `timeline_builder` | Turns discrete evidence (logs, deployments) into a sorted `TimelineEntry` list | No |
| `hypothesis_generator` | Proposes up to 3 candidate root causes, each citing timeline entries by index | Yes |
| `evidence_validator` | Judges whether each hypothesis's cited evidence actually supports its specific claim (not just "evidence exists") | Yes |
| `impact_analyzer` | Assesses concrete business impact from the metrics/timeline | Yes |
| `diagnosis` | Picks the highest-confidence validated hypothesis as the working diagnosis, or honestly reports "no root cause confirmed" if none survived validation | No |

Every hypothesis citation is checked against real evidence indices before
being trusted - an LLM claim that doesn't resolve to something actually
observed is dropped, never persisted as if it were grounded.

**Persistence:** `IncidentPersistenceService.persist_investigation_result`
writes every log/metric/deployment as an `Evidence` row, every timeline
entry as an `IncidentEvent`, every hypothesis (validated or rejected) as a
`Hypothesis` row, and - if one was reached - the final `Diagnosis` row
linked back to its source hypothesis. The incident moves to `DIAGNOSED` on
success or `UNRESOLVED` if no hypothesis survived validation.

## 3. Remediation

**Endpoint:** `POST /api/v1/incidents/{id}/remediations`
**Model:** `app.models.remediation.Remediation`
**Risk:** `app.investigation.risk.classify_risk`

A remediation names one of four fixed, closed action types - never a
free-form command:

- `rollback_deployment`
- `restart_service`
- `scale_service`
- `switch_feature_flag`

`classify_risk(action_type, parameters)` is **deterministic, not an LLM
call** - a safety-critical gate needs to give the same answer every time,
not vary with model sampling. The rules:

| Action | LOW | MEDIUM | HIGH |
|---|---|---|---|
| `rollback_deployment` | - | outside production | in production |
| `restart_service` | single instance / small subset | fleet-wide (`scope="all_instances"` or ≥3 instances) | - |
| `scale_service` | scaling up | scaling down (nonzero target) | scaling down to zero replicas |
| `switch_feature_flag` | disabling, or a ≤10% canary rollout | enabling >10% rollout in production | - |

`requires_human_approval(risk_level)` is `True` for MEDIUM/HIGH, `False`
for LOW.

## 4. Approval

**Endpoints:** `GET /api/v1/incidents/{id}/approvals`,
`POST /api/v1/incidents/{id}/approvals/{approval_id}/decision`
**Model:** `app.models.approval.Approval`

Every remediation gets exactly one `Approval` row, regardless of risk -
this keeps the audit trail complete even for auto-approved actions:

- **LOW risk** → `Approval.status = NOT_REQUIRED` immediately. The incident
  stays wherever it was (no human gate).
- **MEDIUM/HIGH risk** → `Approval.status = PENDING`, and the incident
  moves to `AWAITING_APPROVAL`. A human must call the decision endpoint:
  - **Approve** → `APPROVED`, incident moves to `REMEDIATING`.
  - **Reject** → `REJECTED`, incident returns to `DIAGNOSED` (so a
    different remediation can be proposed).
- Deciding an already-decided approval raises (surfaced as `409 Conflict`
  from the API) - a decision is made once.

## 5. Action

**Endpoint:** `POST /api/v1/incidents/{id}/remediations/{remediation_id}/execute`
**Model:** `app.models.action_execution.ActionExecution`
**Code:** `app.investigation.action_executor.ControlledActionExecutor`

Blocked with `409 Conflict` unless the remediation's approval is
`APPROVED` or `NOT_REQUIRED` - a `PENDING` or `REJECTED` approval can never
reach execution, regardless of what's requested.

For this $0/local deployment, every branch is **simulated**
(`ExecutionStatus.SIMULATED`) rather than calling a real orchestrator -
there's no Kubernetes cluster or cloud deployment API behind this. Each of
the four action types validates its own required parameters before
"running" anything (e.g. `rollback_deployment` requires `deployment_id`;
`scale_service` requires a non-negative `target_replicas`); a malformed
remediation fails validation (`ExecutionStatus.FAILED`) rather than
silently no-op'ing. The `ActionBackend` protocol in the same module
documents the interface a future real adapter would implement, with no
change needed to `ActionExecution`'s schema.

On success, the incident moves to `VERIFYING`. On failure, it stays in
`REMEDIATING` so it can be retried or re-planned.

## 6. Verification

**Endpoint:** `POST /api/v1/incidents/{id}/executions/{execution_id}/verify`
**Model:** `app.models.verification.Verification`
**Code:** `app.investigation.verification.VerificationService`

An incident is **not** considered resolved just because an action executed
successfully - this stage collects fresh telemetry and compares it against
the incident's originally-persisted evidence
(`IncidentPersistenceService.get_evidence_bundle` reconstructs that
baseline from the `Evidence` rows written back in step 2).

Recovery is judged from concrete numbers, deliberately not an LLM call:

1. **Any error/critical-severity log line in the "after" window** → not
   recovered, full stop, regardless of the metric trend. A lingering error
   is exactly what a metric average can mask.
2. With a clean "after" window, recovery additionally requires the average
   metric value (e.g. latency) to have **improved by at least 20%**
   relative to the "before" baseline - or unconditional recovery if there's
   no usable baseline to compare against (nothing to compare, and nothing
   currently wrong).

- **Recovered** → incident moves to `RESOLVED`, `resolved_at` is set.
- **Not recovered** → incident moves back to `INVESTIGATING` - the fix
  didn't work, so it needs another look, not a false "resolved".

---

## Reading back the full picture

- **`GET /api/v1/incidents/{id}`** - hypotheses, active diagnosis,
  remediations, approvals, action executions, and verifications for one
  incident, in one response.
- **`GET /api/v1/incidents/{id}/timeline`** - the append-only
  `IncidentEvent` log: `incident_created`, `investigation_started`,
  `remediation_recommended`, `approval_granted`/`approval_rejected`,
  `action_executed`, `verification_completed`, in chronological order.
- **`GET /api/v1/incidents`** - all incidents, most recent first.

## Observability

Every transition above also increments a Prometheus metric (see
`app/core/metrics.py`, prefix `opsmind_`), recorded from the same
`IncidentPersistenceService` methods that perform the writes:

- `opsmind_investigations_completed_total{outcome}` - `diagnosed` vs `unresolved`
- `opsmind_diagnosis_confidence` - histogram of reached diagnoses' confidence
- `opsmind_remediations_by_risk_total{action_type,risk_level}`
- `opsmind_approvals_total{status}`
- `opsmind_action_executions_total{action_type,status}`
- `opsmind_verifications_total{recovered}`
- `opsmind_incident_time_to_resolution_seconds` - creation → `RESOLVED`

These are exposed at `/metrics` for Prometheus/Grafana scraping.
