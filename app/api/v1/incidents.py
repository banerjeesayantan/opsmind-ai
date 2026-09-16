"""Incident investigation/response API endpoints.

This is the demo surface for the whole OpsMind pipeline
(Incident -> Evidence -> Timeline -> Hypotheses -> Validation -> Impact ->
Diagnosis -> Remediation -> Approval -> Action -> Verification) - Swagger
(/docs) is the intended demo UI, per project convention, so every
endpoint here is written to be exercised directly from Swagger with no
separate frontend needed.

Route handlers stay thin: they translate HTTP <-> the persistence layer
(app.services.persistence.IncidentPersistenceService) and the graph
(app.investigation.graph), and never touch a DB session directly - that
rule holds for API routes exactly as it holds for LangGraph nodes.
"""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from langgraph.graph.state import CompiledStateGraph

from app.core.logging import logger
from app.investigation.graph import build_investigation_graph
from app.investigation.risk import classify_risk
from app.investigation.schemas import InvestigationState
from app.investigation.verification import VerificationService
from app.models.incident_enums import ExecutionStatus
from app.schemas.incident import (
    ActionExecutionResponse,
    ApprovalDecisionRequest,
    ApprovalResponse,
    DiagnosisResponse,
    HypothesisResponse,
    IncidentCreateRequest,
    IncidentResponse,
    IncidentResultsResponse,
    InvestigateRequest,
    InvestigateResponse,
    RemediationCreateRequest,
    RemediationResponse,
    TimelineEntryResponse,
    VerificationResponse,
    VerifyRequest,
)
from app.services.persistence import IncidentPersistenceService, incident_persistence_service
from app.telemetry.schemas import TimeWindow

router = APIRouter()

_investigation_graph: Optional[CompiledStateGraph] = None


def get_persistence_service() -> IncidentPersistenceService:
    """FastAPI dependency for the incident persistence layer.

    A plain function (not a class-bound method) so tests can override it
    via app.dependency_overrides to inject a service backed by an
    isolated test engine, without needing a real Postgres connection for
    API-layer tests.
    """
    return incident_persistence_service


def get_investigation_graph() -> CompiledStateGraph:
    """FastAPI dependency for the compiled investigation graph.

    Built once and cached at module scope (compiling the graph is pure
    wiring, not per-request work). Overridden in tests with a fake graph
    so the API layer can be exercised without calling the real, external
    $0 Groq LLM - matching the same fake-first-class-citizen testing
    convention already used for every LLM-calling node in
    app.investigation.nodes.
    """
    global _investigation_graph
    if _investigation_graph is None:
        _investigation_graph = build_investigation_graph()
    return _investigation_graph


def get_verification_service() -> VerificationService:
    """FastAPI dependency for the post-action verification service."""
    return VerificationService()


# -- Incident CRUD ---------------------------------------------------------


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    body: IncidentCreateRequest,
    persistence: IncidentPersistenceService = Depends(get_persistence_service),
) -> IncidentResponse:
    """Open a new incident.

    This is the entry point of the whole pipeline - everything else
    (investigate, approve, timeline) operates on the incident_id returned
    here.
    """
    incident = await persistence.create_incident(
        title=body.title,
        description=body.description,
        severity=body.severity,
    )
    await persistence.add_incident_event(
        incident.id,
        event_type="incident_created",
        description=f"Incident opened for service '{body.service}'.",
        event_metadata={"service": body.service},
    )
    logger.info("incident_created", incident_id=incident.id, service=body.service)
    return IncidentResponse(**incident.model_dump())


@router.get("", response_model=list[IncidentResponse])
async def list_incidents(
    persistence: IncidentPersistenceService = Depends(get_persistence_service),
) -> list[IncidentResponse]:
    """List all incidents, most recently created first."""
    incidents = await persistence.list_incidents()
    return [IncidentResponse(**i.model_dump()) for i in incidents]


@router.get("/{incident_id}", response_model=IncidentResultsResponse)
async def get_incident_results(
    incident_id: str,
    persistence: IncidentPersistenceService = Depends(get_persistence_service),
) -> IncidentResultsResponse:
    """Get the full investigation/response picture for a single incident.

    Everything the pipeline has produced so far for this incident:
    hypotheses (validated and rejected), the active diagnosis if any,
    every recommended remediation, every approval decision, every action
    execution attempt, and every verification check - the single "give me
    the whole story" endpoint for the Swagger demo.
    """
    incident = await persistence.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No incident found with id {incident_id!r}")

    hypotheses = await persistence.list_hypotheses(incident_id)
    diagnosis = await persistence.get_active_diagnosis(incident_id)
    remediations = await persistence.list_remediations(incident_id)
    approvals = await persistence.list_approvals(incident_id)
    executions = await persistence.list_action_executions(incident_id)
    verifications = await persistence.list_verifications(incident_id)

    return IncidentResultsResponse(
        incident=IncidentResponse(**incident.model_dump()),
        hypotheses=[HypothesisResponse(**h.model_dump()) for h in hypotheses],
        diagnosis=DiagnosisResponse(**diagnosis.model_dump()) if diagnosis else None,
        remediations=[RemediationResponse(**r.model_dump()) for r in remediations],
        approvals=[ApprovalResponse(**a.model_dump()) for a in approvals],
        action_executions=[ActionExecutionResponse(**e.model_dump()) for e in executions],
        verifications=[VerificationResponse(**v.model_dump()) for v in verifications],
    )


@router.get("/{incident_id}/timeline", response_model=list[TimelineEntryResponse])
async def get_incident_timeline(
    incident_id: str,
    persistence: IncidentPersistenceService = Depends(get_persistence_service),
) -> list[TimelineEntryResponse]:
    """Get an incident's append-only timeline, in chronological order."""
    incident = await persistence.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No incident found with id {incident_id!r}")

    timeline = await persistence.get_timeline(incident_id)
    return [TimelineEntryResponse(**event.model_dump()) for event in timeline]


# -- Investigation -----------------------------------------------------------


@router.post("/{incident_id}/investigate", response_model=InvestigateResponse)
async def investigate_incident(
    incident_id: str,
    body: InvestigateRequest,
    persistence: IncidentPersistenceService = Depends(get_persistence_service),
    graph: CompiledStateGraph = Depends(get_investigation_graph),
) -> InvestigateResponse:
    """Run the investigation graph for an incident and persist the result.

    Drives the full Evidence -> Timeline -> Hypotheses -> Validation ->
    Impact -> Diagnosis pipeline (app.investigation.graph) for the given
    service and time window, then persists everything it produced via
    IncidentPersistenceService.persist_investigation_result.
    """
    incident = await persistence.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No incident found with id {incident_id!r}")

    await persistence.update_incident_status(incident_id, incident.status)  # no-op touch; keeps status explicit
    await persistence.add_incident_event(
        incident_id, event_type="investigation_started", description=f"Investigating service '{body.service}'."
    )

    initial_state = InvestigationState(
        incident_id=incident_id,
        service=body.service,
        time_window=TimeWindow(start=body.window_start, end=body.window_end),
    )
    result = await graph.ainvoke(initial_state)
    final_state = InvestigationState.model_validate(result)

    persisted = await persistence.persist_investigation_result(incident_id, final_state)
    updated_incident = await persistence.get_incident(incident_id)

    logger.info(
        "investigation_completed",
        incident_id=incident_id,
        diagnosis_id=persisted["diagnosis_id"],
        hypothesis_count=len(persisted["hypothesis_ids"]),
    )

    # If the graph's remediation_planner node reached a grounded
    # recommendation, carry it through the same persist -> classify_risk
    # -> approval flow POST /remediations uses below - not a second
    # system, the identical three calls, just triggered automatically
    # here instead of requiring a separate manual request. Only proceeds
    # when a Diagnosis row actually exists to attach it to: remediation
    # can be non-None while diagnosis_id is None if the diagnosis's
    # probable_cause didn't trace back to a persisted hypothesis (see
    # persist_investigation_result's grounding rule), and persist_remediation
    # requires a real diagnosis_id (NOT NULL FK).
    remediation_id: Optional[int] = None
    remediation_risk_level = None
    if final_state.remediation is not None and persisted["diagnosis_id"] is not None:
        remediation_risk_level = classify_risk(
            final_state.remediation.action_type, final_state.remediation.parameters
        )
        remediation_row = await persistence.persist_remediation(
            incident_id,
            persisted["diagnosis_id"],
            action_type=final_state.remediation.action_type,
            parameters=final_state.remediation.parameters,
            risk_level=remediation_risk_level,
            rationale=final_state.remediation.rationale,
        )
        remediation_id = remediation_row.id
        await persistence.create_approval_request(incident_id, remediation_row.id, remediation_risk_level)
        await persistence.add_incident_event(
            incident_id,
            event_type="remediation_recommended",
            description=(
                f"Recommended {final_state.remediation.action_type.value} "
                f"(risk={remediation_risk_level.value})."
            ),
            event_metadata={"remediation_id": remediation_row.id, "risk_level": remediation_risk_level.value},
        )
        updated_incident = await persistence.get_incident(incident_id)
        logger.info(
            "investigation_produced_remediation",
            incident_id=incident_id,
            remediation_id=remediation_id,
            risk_level=remediation_risk_level.value,
        )

    return InvestigateResponse(
        incident_id=incident_id,
        status=updated_incident.status,
        evidence_count=len(persisted["evidence_ids"]),
        hypothesis_count=len(persisted["hypothesis_ids"]),
        diagnosis_id=persisted["diagnosis_id"],
        probable_cause=final_state.diagnosis.probable_cause if final_state.diagnosis else None,
        confidence=final_state.diagnosis.confidence if final_state.diagnosis else None,
        remediation_id=remediation_id,
        risk_level=remediation_risk_level,
    )


# -- Remediation + Approval (Phase 3) -----------------------------------------


@router.post("/{incident_id}/remediations", response_model=RemediationResponse, status_code=status.HTTP_201_CREATED)
async def recommend_remediation(
    incident_id: str,
    body: RemediationCreateRequest,
    persistence: IncidentPersistenceService = Depends(get_persistence_service),
) -> RemediationResponse:
    """Recommend a remediation for a diagnosis, and open its approval request.

    risk_level is always computed server-side via
    app.investigation.risk.classify_risk - never accepted from the
    client - since trusting a client-supplied risk level would defeat
    the entire point of the approval gate.
    """
    incident = await persistence.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No incident found with id {incident_id!r}")

    risk_level = classify_risk(body.action_type, body.parameters, environment=body.environment)
    remediation = await persistence.persist_remediation(
        incident_id,
        body.diagnosis_id,
        action_type=body.action_type,
        parameters=body.parameters,
        risk_level=risk_level,
        rationale=body.rationale,
    )
    await persistence.create_approval_request(incident_id, remediation.id, risk_level)
    await persistence.add_incident_event(
        incident_id,
        event_type="remediation_recommended",
        description=f"Recommended {body.action_type.value} (risk={risk_level.value}).",
        event_metadata={"remediation_id": remediation.id, "risk_level": risk_level.value},
    )
    return RemediationResponse(**remediation.model_dump())


@router.get("/{incident_id}/approvals", response_model=list[ApprovalResponse])
async def list_approvals(
    incident_id: str,
    persistence: IncidentPersistenceService = Depends(get_persistence_service),
) -> list[ApprovalResponse]:
    """List every approval request raised for an incident."""
    approvals = await persistence.list_approvals(incident_id)
    return [ApprovalResponse(**a.model_dump()) for a in approvals]


@router.post("/{incident_id}/approvals/{approval_id}/decision", response_model=ApprovalResponse)
async def decide_approval(
    incident_id: str,
    approval_id: int,
    body: ApprovalDecisionRequest,
    persistence: IncidentPersistenceService = Depends(get_persistence_service),
) -> ApprovalResponse:
    """Approve or reject a pending remediation.

    This is the human-in-the-loop gate: MEDIUM/HIGH risk remediations
    cannot execute until this endpoint records an APPROVED decision.
    """
    approval = await persistence.get_approval(approval_id)
    if approval is None or approval.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No approval {approval_id!r} found for incident {incident_id!r}",
        )

    try:
        decided = await persistence.decide_approval(
            approval_id, approved=body.approved, decided_by=body.decided_by, reason=body.reason
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await persistence.add_incident_event(
        incident_id,
        event_type="approval_granted" if body.approved else "approval_rejected",
        description=body.reason or ("Approved" if body.approved else "Rejected"),
        event_metadata={"approval_id": approval_id},
    )
    return ApprovalResponse(**decided.model_dump())


# -- Controlled action execution (Phase 4) ------------------------------------


@router.post(
    "/{incident_id}/remediations/{remediation_id}/execute",
    response_model=ActionExecutionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def execute_remediation(
    incident_id: str,
    remediation_id: int,
    persistence: IncidentPersistenceService = Depends(get_persistence_service),
) -> ActionExecutionResponse:
    """Execute (simulate) a remediation's recommended action.

    Blocked unless the remediation's approval is APPROVED or
    NOT_REQUIRED - a PENDING or REJECTED approval must never reach
    execution, regardless of what the caller asks for.
    """
    from app.investigation.action_executor import ControlledActionExecutor
    from app.models.incident_enums import ApprovalStatus

    remediation = await persistence.get_remediation(remediation_id)
    if remediation is None or remediation.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No remediation {remediation_id!r} found for incident {incident_id!r}",
        )

    approvals = await persistence.list_approvals(incident_id)
    matching = [a for a in approvals if a.remediation_id == remediation_id]
    if not matching or not any(a.status in (ApprovalStatus.APPROVED, ApprovalStatus.NOT_REQUIRED) for a in matching):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This remediation has not been approved (or auto-approved) yet.",
        )

    execution = await persistence.create_action_execution(incident_id, remediation_id)
    outcome = await ControlledActionExecutor().execute(remediation)
    completed = await persistence.complete_action_execution(
        execution.id,
        status=ExecutionStatus.SIMULATED if outcome.succeeded else ExecutionStatus.FAILED,
        result=outcome.result or None,
        error_message=outcome.error_message or None,
    )
    await persistence.add_incident_event(
        incident_id,
        event_type="action_executed",
        description=f"Executed {remediation.action_type.value} (simulated): "
        + ("succeeded" if outcome.succeeded else f"failed - {outcome.error_message}"),
        event_metadata={"remediation_id": remediation_id, "execution_id": completed.id},
    )
    return ActionExecutionResponse(**completed.model_dump())


# -- Verification (Phase 5) ---------------------------------------------------


@router.post("/{incident_id}/executions/{execution_id}/verify", response_model=VerificationResponse)
async def verify_execution(
    incident_id: str,
    execution_id: int,
    body: VerifyRequest,
    persistence: IncidentPersistenceService = Depends(get_persistence_service),
    verification_service: VerificationService = Depends(get_verification_service),
) -> VerificationResponse:
    """Collect fresh telemetry and check whether the incident actually recovered.

    Compares against the incident's originally-persisted Evidence as the
    "before" baseline, per app.services.persistence.IncidentPersistenceService.get_evidence_bundle
    - an incident is not marked resolved on the strength of the executed
    action alone.
    """
    execution = await persistence.get_action_execution(execution_id)
    if execution is None or execution.incident_id != incident_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No action execution {execution_id!r} found for incident {incident_id!r}",
        )

    incident = await persistence.get_incident(incident_id)
    before_evidence = await persistence.get_evidence_bundle(incident_id, service=incident.title)

    if body.after_window_start and body.after_window_end:
        after_window = TimeWindow(start=body.after_window_start, end=body.after_window_end)
    else:
        now = before_evidence.time_window.end
        after_window = TimeWindow(start=now, end=now + timedelta(minutes=15))

    comparison = await verification_service.verify(
        service=before_evidence.service or incident.title,
        before_evidence=before_evidence,
        after_window=after_window,
    )

    evidence_after_ids: list[int] = []  # fresh telemetry isn't persisted as Evidence by default; see notes for detail
    verification = await persistence.create_verification(
        incident_id,
        execution_id,
        recovered=comparison.recovered,
        evidence_after_ids=evidence_after_ids,
        notes=comparison.notes,
    )
    await persistence.add_incident_event(
        incident_id,
        event_type="verification_completed",
        description=comparison.notes,
        event_metadata={"execution_id": execution_id, "recovered": comparison.recovered},
    )
    return VerificationResponse(**verification.model_dump())