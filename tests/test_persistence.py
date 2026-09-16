"""Regression tests for app.services.persistence.IncidentPersistenceService.

Each test drives the async persistence API via asyncio.run() from a plain
sync pytest function (see tests/test_telemetry.py for the same
convention), against the isolated real-database engine provided by the
test_engine fixture in tests/conftest.py.

Run with: pytest tests/test_persistence.py -v
"""

import asyncio
from datetime import datetime, timedelta, UTC

from app.investigation.schemas import (
    DiagnosisResult,
    EvidenceCitation,
    HypothesisCandidate,
    ImpactAssessment,
    InvestigationState,
    TimelineEntry,
)
from app.models.incident_enums import (
    ApprovalStatus,
    ExecutionStatus,
    IncidentStatus,
    RemediationActionType,
    RiskLevel,
    Severity,
)
from app.services.persistence import IncidentPersistenceService
from app.telemetry.schemas import (
    DeploymentEvent,
    EvidenceBundle,
    LogEntry,
    TimeWindow,
)


def _window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 9, 6, 10, 0, tzinfo=UTC),
        end=datetime(2026, 9, 6, 10, 15, tzinfo=UTC),
    )


def _investigation_state_with_diagnosis() -> InvestigationState:
    """A realistic completed investigation state with a confirmed diagnosis."""
    window = _window()
    log_ts = window.start + timedelta(minutes=5)
    deploy_ts = window.start - timedelta(minutes=2)

    evidence = EvidenceBundle(
        service="checkout",
        time_window=window,
        logs=[
            LogEntry(timestamp=log_ts, service="checkout", severity="error", message="Timeout calling downstream"),
        ],
        deployments=[
            DeploymentEvent(
                timestamp=deploy_ts,
                service="checkout",
                deployment_id="dep-42",
                commit_sha="a1b2c3d",
                environment="production",
                change_summary="Updated downstream dependency timeout handling",
            )
        ],
    )
    timeline = [
        TimelineEntry(timestamp=deploy_ts, event_type="deployment", description="Updated downstream dependency timeout handling"),
        TimelineEntry(timestamp=log_ts, event_type="log_error", description="Timeout calling downstream"),
    ]
    citation = EvidenceCitation(source="log", content="Timeout calling downstream", timestamp=log_ts)
    hypothesis = HypothesisCandidate(
        statement="The deployment introduced a downstream timeout regression",
        reasoning="Errors began right after the deployment",
        confidence=0.6,
        supporting_evidence=[citation],
    )
    validated_hypothesis = hypothesis.model_copy(update={"validated": True, "confidence": 0.85})

    diagnosis = DiagnosisResult(
        probable_cause=validated_hypothesis.statement,
        confidence=0.85,
        supporting_evidence=[citation],
        impact=ImpactAssessment(description="Checkout latency rose sharply", severity=Severity.HIGH),
    )

    return InvestigationState(
        incident_id="unused-here",
        service="checkout",
        time_window=window,
        evidence=evidence,
        timeline=timeline,
        hypotheses=[hypothesis],
        validated_hypotheses=[validated_hypothesis],
        diagnosis=diagnosis,
    )


def _investigation_state_inconclusive() -> InvestigationState:
    """A completed investigation with no confirmed hypothesis."""
    window = _window()
    return InvestigationState(
        incident_id="unused-here",
        service="checkout",
        time_window=window,
        evidence=EvidenceBundle(service="checkout", time_window=window),
        timeline=[],
        hypotheses=[],
        validated_hypotheses=[],
        diagnosis=DiagnosisResult(
            probable_cause="No root cause could be confirmed from the available evidence.",
            confidence=0.0,
        ),
    )


# --- Incident CRUD -----------------------------------------------------------


def test_create_and_get_incident(test_engine):
    service = IncidentPersistenceService(engine=test_engine)

    async def run():
        incident = await service.create_incident(title="Checkout latency spike", description="p95 rose to 2.6s")
        assert incident.id is not None
        assert incident.status == IncidentStatus.NEW

        fetched = await service.get_incident(incident.id)
        assert fetched is not None
        assert fetched.title == "Checkout latency spike"

    asyncio.run(run())


def test_get_incident_returns_none_when_missing(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    result = asyncio.run(service.get_incident("does-not-exist"))
    assert result is None


def test_update_incident_status_sets_resolved_at_on_terminal_status(test_engine):
    service = IncidentPersistenceService(engine=test_engine)

    async def run():
        incident = await service.create_incident(title="Test incident")
        assert incident.resolved_at is None

        updated = await service.update_incident_status(incident.id, IncidentStatus.RESOLVED)
        assert updated.status == IncidentStatus.RESOLVED
        assert updated.resolved_at is not None

    asyncio.run(run())


def test_list_incidents_returns_most_recent_first(test_engine):
    service = IncidentPersistenceService(engine=test_engine)

    async def run():
        first = await service.create_incident(title="First")
        second = await service.create_incident(title="Second")
        incidents = await service.list_incidents()
        ids = [i.id for i in incidents]
        assert ids.index(second.id) < ids.index(first.id)

    asyncio.run(run())


def test_add_and_get_timeline(test_engine):
    service = IncidentPersistenceService(engine=test_engine)

    async def run():
        incident = await service.create_incident(title="Test incident")
        await service.add_incident_event(incident.id, "alert_triggered", "PagerDuty alert fired")
        await service.add_incident_event(incident.id, "investigation_started", "Agent started investigating")

        timeline = await service.get_timeline(incident.id)
        assert [e.event_type for e in timeline] == ["alert_triggered", "investigation_started"]

    asyncio.run(run())


# --- persist_investigation_result --------------------------------------------


def test_persist_investigation_result_with_confirmed_diagnosis(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    state = _investigation_state_with_diagnosis()

    async def run():
        incident = await service.create_incident(title="Checkout latency spike")
        result = await service.persist_investigation_result(incident.id, state)

        assert len(result["evidence_ids"]) == 2  # 1 log + 1 deployment
        assert len(result["hypothesis_ids"]) == 1
        assert result["diagnosis_id"] is not None

        updated_incident = await service.get_incident(incident.id)
        assert updated_incident.status == IncidentStatus.DIAGNOSED
        assert updated_incident.severity == Severity.HIGH

    asyncio.run(run())


def test_persist_investigation_result_hypothesis_is_grounded_in_real_evidence_ids(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    state = _investigation_state_with_diagnosis()

    async def run():
        incident = await service.create_incident(title="Checkout latency spike")
        await service.persist_investigation_result(incident.id, state)

        with service._session() as session:
            from app.models.hypothesis import Hypothesis
            from sqlmodel import select

            hyp = session.exec(select(Hypothesis).where(Hypothesis.incident_id == incident.id)).one()
            assert hyp.status.value == "validated"
            assert len(hyp.supporting_evidence_ids) == 1

            from app.models.evidence import Evidence

            evidence_row = session.get(Evidence, hyp.supporting_evidence_ids[0])
            assert evidence_row is not None
            assert evidence_row.content == "Timeout calling downstream"

    asyncio.run(run())


def test_persist_investigation_result_inconclusive_marks_incident_unresolved(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    state = _investigation_state_inconclusive()

    async def run():
        incident = await service.create_incident(title="Mystery blip")
        result = await service.persist_investigation_result(incident.id, state)

        assert result["diagnosis_id"] is None
        updated_incident = await service.get_incident(incident.id)
        assert updated_incident.status == IncidentStatus.UNRESOLVED

    asyncio.run(run())


# --- Remediation / Approval (Phase 3) ----------------------------------------


def _diagnosed_incident(service: IncidentPersistenceService):
    async def run():
        incident = await service.create_incident(title="Checkout latency spike")
        state = _investigation_state_with_diagnosis()
        result = await service.persist_investigation_result(incident.id, state)
        return incident, result["diagnosis_id"]

    return asyncio.run(run())


def test_persist_remediation_and_low_risk_auto_approves(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    incident, diagnosis_id = _diagnosed_incident(service)

    async def run():
        remediation = await service.persist_remediation(
            incident.id,
            diagnosis_id,
            action_type=RemediationActionType.RESTART_SERVICE,
            parameters={"instance_count": 1},
            risk_level=RiskLevel.LOW,
            rationale="A single restart should clear the stuck connection pool",
        )
        assert remediation.id is not None
        assert remediation.risk_level == RiskLevel.LOW

        approval = await service.create_approval_request(incident.id, remediation.id, RiskLevel.LOW)
        assert approval.status == ApprovalStatus.NOT_REQUIRED
        assert approval.decided_at is None

        # Low risk shouldn't move the incident to AWAITING_APPROVAL.
        updated_incident = await service.get_incident(incident.id)
        assert updated_incident.status == IncidentStatus.DIAGNOSED

    asyncio.run(run())


def test_high_risk_remediation_requires_approval_and_blocks_incident(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    incident, diagnosis_id = _diagnosed_incident(service)

    async def run():
        remediation = await service.persist_remediation(
            incident.id,
            diagnosis_id,
            action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
            parameters={"deployment_id": "dep-42"},
            risk_level=RiskLevel.HIGH,
            rationale="Roll back the deployment that introduced the regression",
        )
        approval = await service.create_approval_request(incident.id, remediation.id, RiskLevel.HIGH)
        assert approval.status == ApprovalStatus.PENDING

        updated_incident = await service.get_incident(incident.id)
        assert updated_incident.status == IncidentStatus.AWAITING_APPROVAL

    asyncio.run(run())


def test_decide_approval_approve_moves_incident_to_remediating(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    incident, diagnosis_id = _diagnosed_incident(service)

    async def run():
        remediation = await service.persist_remediation(
            incident.id,
            diagnosis_id,
            action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
            parameters={"deployment_id": "dep-42"},
            risk_level=RiskLevel.HIGH,
        )
        approval = await service.create_approval_request(incident.id, remediation.id, RiskLevel.HIGH)

        decided = await service.decide_approval(approval.id, approved=True, decided_by=None, reason="Looks safe")
        assert decided.status == ApprovalStatus.APPROVED
        assert decided.decided_at is not None

        updated_incident = await service.get_incident(incident.id)
        assert updated_incident.status == IncidentStatus.REMEDIATING

    asyncio.run(run())


def test_decide_approval_reject_returns_incident_to_diagnosed(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    incident, diagnosis_id = _diagnosed_incident(service)

    async def run():
        remediation = await service.persist_remediation(
            incident.id,
            diagnosis_id,
            action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
            parameters={"deployment_id": "dep-42"},
            risk_level=RiskLevel.HIGH,
        )
        approval = await service.create_approval_request(incident.id, remediation.id, RiskLevel.HIGH)

        decided = await service.decide_approval(approval.id, approved=False, reason="Too risky right now")
        assert decided.status == ApprovalStatus.REJECTED

        updated_incident = await service.get_incident(incident.id)
        assert updated_incident.status == IncidentStatus.DIAGNOSED

    asyncio.run(run())


def test_decide_approval_twice_raises(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    incident, diagnosis_id = _diagnosed_incident(service)

    async def run():
        remediation = await service.persist_remediation(
            incident.id,
            diagnosis_id,
            action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
            parameters={},
            risk_level=RiskLevel.HIGH,
        )
        approval = await service.create_approval_request(incident.id, remediation.id, RiskLevel.HIGH)
        await service.decide_approval(approval.id, approved=True)

        try:
            await service.decide_approval(approval.id, approved=True)
            assert False, "expected ValueError deciding an already-decided approval"
        except ValueError:
            pass

    asyncio.run(run())


def test_persist_remediation_unselects_previous_selected_remediation(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    incident, diagnosis_id = _diagnosed_incident(service)

    async def run():
        first = await service.persist_remediation(
            incident.id, diagnosis_id, RemediationActionType.RESTART_SERVICE, {}, RiskLevel.LOW
        )
        second = await service.persist_remediation(
            incident.id, diagnosis_id, RemediationActionType.ROLLBACK_DEPLOYMENT, {}, RiskLevel.HIGH
        )

        first_reloaded = await service.get_remediation(first.id)
        second_reloaded = await service.get_remediation(second.id)
        assert first_reloaded.is_selected is False
        assert second_reloaded.is_selected is True

    asyncio.run(run())


# --- Action execution (Phase 4) ----------------------------------------------


def test_action_execution_lifecycle_success_moves_incident_to_verifying(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    incident, diagnosis_id = _diagnosed_incident(service)

    async def run():
        remediation = await service.persist_remediation(
            incident.id, diagnosis_id, RemediationActionType.RESTART_SERVICE, {}, RiskLevel.LOW
        )
        execution = await service.create_action_execution(incident.id, remediation.id)
        assert execution.status == ExecutionStatus.PENDING

        completed = await service.complete_action_execution(
            execution.id, ExecutionStatus.SIMULATED, result={"simulated": True}
        )
        assert completed.status == ExecutionStatus.SIMULATED
        assert completed.result == {"simulated": True}

        updated_incident = await service.get_incident(incident.id)
        assert updated_incident.status == IncidentStatus.VERIFYING

    asyncio.run(run())


def test_action_execution_failure_leaves_incident_remediating(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    incident, diagnosis_id = _diagnosed_incident(service)

    async def run():
        remediation = await service.persist_remediation(
            incident.id, diagnosis_id, RemediationActionType.RESTART_SERVICE, {}, RiskLevel.LOW
        )
        await service.update_incident_status(incident.id, IncidentStatus.REMEDIATING)
        execution = await service.create_action_execution(incident.id, remediation.id)

        await service.complete_action_execution(execution.id, ExecutionStatus.FAILED, error_message="timed out")

        updated_incident = await service.get_incident(incident.id)
        assert updated_incident.status == IncidentStatus.REMEDIATING

    asyncio.run(run())


# --- Verification (Phase 5) ---------------------------------------------------


def test_verification_recovered_true_resolves_incident(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    incident, diagnosis_id = _diagnosed_incident(service)

    async def run():
        remediation = await service.persist_remediation(
            incident.id, diagnosis_id, RemediationActionType.RESTART_SERVICE, {}, RiskLevel.LOW
        )
        execution = await service.create_action_execution(incident.id, remediation.id)
        await service.complete_action_execution(execution.id, ExecutionStatus.SIMULATED)

        verification = await service.create_verification(
            incident.id, execution.id, recovered=True, notes="Latency back to baseline"
        )
        assert verification.recovered is True

        updated_incident = await service.get_incident(incident.id)
        assert updated_incident.status == IncidentStatus.RESOLVED
        assert updated_incident.resolved_at is not None

    asyncio.run(run())


def test_verification_recovered_false_returns_to_investigating(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    incident, diagnosis_id = _diagnosed_incident(service)

    async def run():
        remediation = await service.persist_remediation(
            incident.id, diagnosis_id, RemediationActionType.RESTART_SERVICE, {}, RiskLevel.LOW
        )
        execution = await service.create_action_execution(incident.id, remediation.id)
        await service.complete_action_execution(execution.id, ExecutionStatus.SIMULATED)

        verification = await service.create_verification(
            incident.id, execution.id, recovered=False, notes="Latency still elevated"
        )
        assert verification.recovered is False

        updated_incident = await service.get_incident(incident.id)
        assert updated_incident.status == IncidentStatus.INVESTIGATING

    asyncio.run(run())
