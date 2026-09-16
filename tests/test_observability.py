"""Tests for the incident observability metrics recorded by IncidentPersistenceService.

Prometheus Counter/Histogram objects accumulate for the lifetime of the
process (that's the point - they're scraped, not reset per-request), so
these tests read each metric's value before and after the action under
test and assert on the delta, rather than asserting an absolute value -
that keeps them independent of test execution order and of whatever
other tests ran earlier in the same process.

Run with: pytest tests/test_observability.py -v
"""

import asyncio

from app.core.metrics import (
    action_executions_total,
    approvals_total,
    investigations_completed_total,
    remediations_by_risk_total,
    verifications_total,
)
from app.models.incident_enums import (
    ExecutionStatus,
    RemediationActionType,
    RiskLevel,
)
from app.services.persistence import IncidentPersistenceService
from tests.test_persistence import _investigation_state_with_diagnosis, _investigation_state_inconclusive


def _counter_value(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


def test_persist_investigation_result_increments_diagnosed_counter(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    before = _counter_value(investigations_completed_total, outcome="diagnosed")

    async def run():
        incident = await service.create_incident(title="X")
        await service.persist_investigation_result(incident.id, _investigation_state_with_diagnosis())

    asyncio.run(run())
    after = _counter_value(investigations_completed_total, outcome="diagnosed")
    assert after == before + 1


def test_persist_investigation_result_increments_unresolved_counter(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    before = _counter_value(investigations_completed_total, outcome="unresolved")

    async def run():
        incident = await service.create_incident(title="X")
        await service.persist_investigation_result(incident.id, _investigation_state_inconclusive())

    asyncio.run(run())
    after = _counter_value(investigations_completed_total, outcome="unresolved")
    assert after == before + 1


def test_persist_remediation_increments_risk_counter(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    before = _counter_value(
        remediations_by_risk_total, action_type="restart_service", risk_level="low"
    )

    async def run():
        incident = await service.create_incident(title="X")
        result = await service.persist_investigation_result(incident.id, _investigation_state_with_diagnosis())
        await service.persist_remediation(
            incident.id, result["diagnosis_id"], RemediationActionType.RESTART_SERVICE, {}, RiskLevel.LOW
        )

    asyncio.run(run())
    after = _counter_value(remediations_by_risk_total, action_type="restart_service", risk_level="low")
    assert after == before + 1


def test_approval_lifecycle_increments_status_counters(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    before_pending = _counter_value(approvals_total, status="pending")
    before_approved = _counter_value(approvals_total, status="approved")

    async def run():
        incident = await service.create_incident(title="X")
        result = await service.persist_investigation_result(incident.id, _investigation_state_with_diagnosis())
        remediation = await service.persist_remediation(
            incident.id, result["diagnosis_id"], RemediationActionType.ROLLBACK_DEPLOYMENT, {}, RiskLevel.HIGH
        )
        approval = await service.create_approval_request(incident.id, remediation.id, RiskLevel.HIGH)
        await service.decide_approval(approval.id, approved=True)

    asyncio.run(run())
    assert _counter_value(approvals_total, status="pending") == before_pending + 1
    assert _counter_value(approvals_total, status="approved") == before_approved + 1


def test_action_execution_increments_status_counter(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    before = _counter_value(action_executions_total, action_type="restart_service", status="simulated")

    async def run():
        incident = await service.create_incident(title="X")
        result = await service.persist_investigation_result(incident.id, _investigation_state_with_diagnosis())
        remediation = await service.persist_remediation(
            incident.id, result["diagnosis_id"], RemediationActionType.RESTART_SERVICE, {}, RiskLevel.LOW
        )
        execution = await service.create_action_execution(incident.id, remediation.id)
        await service.complete_action_execution(execution.id, ExecutionStatus.SIMULATED, result={"ok": True})

    asyncio.run(run())
    after = _counter_value(action_executions_total, action_type="restart_service", status="simulated")
    assert after == before + 1


def test_verification_increments_recovered_counter(test_engine):
    service = IncidentPersistenceService(engine=test_engine)
    before_true = _counter_value(verifications_total, recovered="true")
    before_false = _counter_value(verifications_total, recovered="false")

    async def run():
        incident = await service.create_incident(title="X")
        result = await service.persist_investigation_result(incident.id, _investigation_state_with_diagnosis())
        remediation = await service.persist_remediation(
            incident.id, result["diagnosis_id"], RemediationActionType.RESTART_SERVICE, {}, RiskLevel.LOW
        )
        execution = await service.create_action_execution(incident.id, remediation.id)
        await service.complete_action_execution(execution.id, ExecutionStatus.SIMULATED)
        await service.create_verification(incident.id, execution.id, recovered=True)

        incident2 = await service.create_incident(title="Y")
        result2 = await service.persist_investigation_result(incident2.id, _investigation_state_with_diagnosis())
        remediation2 = await service.persist_remediation(
            incident2.id, result2["diagnosis_id"], RemediationActionType.RESTART_SERVICE, {}, RiskLevel.LOW
        )
        execution2 = await service.create_action_execution(incident2.id, remediation2.id)
        await service.complete_action_execution(execution2.id, ExecutionStatus.SIMULATED)
        await service.create_verification(incident2.id, execution2.id, recovered=False)

    asyncio.run(run())
    assert _counter_value(verifications_total, recovered="true") == before_true + 1
    assert _counter_value(verifications_total, recovered="false") == before_false + 1
