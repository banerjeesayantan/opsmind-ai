"""Tests for the incident investigation/response API (app.api.v1.incidents).

Exercises the real FastAPI app + real routing + the real persistence
layer (against the isolated test_engine fixture) end-to-end via
TestClient. The one dependency overridden is the investigation graph
itself: app.investigation.graph.build_investigation_graph ultimately
calls the real, external $0 Groq LLM, which this sandbox has no network
access to and which would make these tests flaky/non-deterministic
regardless - so a fake graph stands in, exactly the same
fake-the-external-LLM-call convention already used for every node test
in tests/test_*.py (see e.g. HypothesisGeneratorNode's StructuredLLM
Protocol). Every other layer (HTTP routing, request/response schemas,
persistence, risk classification, approval gating, action execution,
verification) is exercised for real.

Run with: pytest tests/test_api_incidents.py -v
"""

from datetime import datetime, timedelta, UTC

import pytest
from fastapi.testclient import TestClient

from app.api.v1.incidents import (
    get_investigation_graph,
    get_persistence_service,
    get_verification_service,
)
from app.investigation.schemas import (
    DiagnosisResult,
    EvidenceCitation,
    HypothesisCandidate,
    ImpactAssessment,
    InvestigationState,
    RemediationCandidate,
)
from app.investigation.verification import VerificationService
from app.main import app
from app.models.incident_enums import RemediationActionType, Severity
from app.services.persistence import IncidentPersistenceService, incident_persistence_service


class _FakeGraph:
    """Stands in for the compiled LangGraph, skipping the real LLM calls.

    Returns a deterministic, fully-diagnosed InvestigationState so API
    tests can exercise everything downstream (persistence, remediation,
    approval, execution, verification) without a live Groq connection.
    """

    async def ainvoke(self, state: InvestigationState) -> dict:
        citation = EvidenceCitation(
            source="log",
            content="Timeout calling downstream",
            timestamp=state.time_window.start + timedelta(minutes=5),
        )
        hypothesis = HypothesisCandidate(
            statement="A downstream dependency regression caused the incident",
            reasoning="Timeouts began right after deploy",
            confidence=0.9,
            supporting_evidence=[citation],
            validated=True,
        )
        diagnosis = DiagnosisResult(
            probable_cause=hypothesis.statement,
            confidence=0.9,
            supporting_evidence=[citation],
            impact=ImpactAssessment(description="Elevated latency", severity=Severity.HIGH),
        )
        updated = state.model_copy(
            update={
                "hypotheses": [hypothesis],
                "validated_hypotheses": [hypothesis],
                "diagnosis": diagnosis,
            }
        )
        # evidence_collector/timeline_builder still need to have run for a
        # realistic result - reuse the real, deterministic mock telemetry
        # sources rather than fabricating evidence by hand.
        from app.telemetry.service import TelemetryService as _TS

        bundle = await _TS.with_mock_sources().collect_evidence(state.service, state.time_window)
        updated = updated.model_copy(update={"evidence": bundle})
        return updated.model_dump()


class _FakeGraphWithRemediation(_FakeGraph):
    """Same as _FakeGraph, but also sets a grounded remediation.

    Kept as a separate subclass rather than changing _FakeGraph's default
    behavior - every other test in this file uses _FakeGraph via the
    `client` fixture below and asserts on exact approval/remediation
    counts (e.g. test_recommend_remediation_classifies_risk_and_creates_approval
    expects exactly one approval after its own POST /remediations); if
    _FakeGraph itself always produced a remediation, /investigate would
    silently create an extra Remediation + Approval row in front of
    those tests and break their counts. Only the test that specifically
    verifies the investigate -> remediation -> approval wiring opts into
    this subclass.
    """

    async def ainvoke(self, state: InvestigationState) -> dict:
        base = await super().ainvoke(state)
        final_state = InvestigationState.model_validate(base)
        real_deployment_id = final_state.evidence.deployments[0].deployment_id
        remediation = RemediationCandidate(
            action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
            parameters={"deployment_id": real_deployment_id},
            rationale="Roll back the release that introduced the regression",
        )
        return final_state.model_copy(update={"remediation": remediation}).model_dump()


@pytest.fixture()
def client(test_engine, monkeypatch):
    """A TestClient wired to the isolated test_engine and a fake investigation graph.

    Both the FastAPI dependency override AND the module-level
    incident_persistence_service singleton are pointed at test_engine, so
    every request reaches the same isolated, StaticPool-backed SQLite (or
    real opsmind_test Postgres) engine regardless of which resolution
    path FastAPI takes: app.dependency_overrides is the normal mechanism
    for tests/get_persistence_service, but pinning the singleton's own
    .engine attribute too (via pytest's monkeypatch, so it's
    automatically restored after the test) removes any dependency on
    that override matching correctly, and guards against anything that
    reaches incident_persistence_service directly rather than through
    Depends(get_persistence_service).
    """
    service = IncidentPersistenceService(engine=test_engine)
    monkeypatch.setattr(incident_persistence_service, "engine", test_engine)
    app.dependency_overrides[get_persistence_service] = lambda: service
    app.dependency_overrides[get_investigation_graph] = lambda: _FakeGraph()
    app.dependency_overrides[get_verification_service] = lambda: VerificationService()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def client_with_remediation(test_engine, monkeypatch):
    """Same as `client`, but the investigation graph also produces a
    grounded remediation - used only by the test verifying the
    investigate -> remediation -> approval wiring, so every other test's
    approval/remediation-count assertions against the plain `client`
    fixture (backed by _FakeGraph, which never sets remediation) are
    unaffected.
    """
    service = IncidentPersistenceService(engine=test_engine)
    monkeypatch.setattr(incident_persistence_service, "engine", test_engine)
    app.dependency_overrides[get_persistence_service] = lambda: service
    app.dependency_overrides[get_investigation_graph] = lambda: _FakeGraphWithRemediation()
    app.dependency_overrides[get_verification_service] = lambda: VerificationService()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _create_incident(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/incidents",
        json={"title": "Checkout latency spike", "service": "checkout", "severity": "high"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _investigate(client: TestClient, incident_id: str) -> dict:
    window_start = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    window_end = window_start + timedelta(minutes=15)
    response = client.post(
        f"/api/v1/incidents/{incident_id}/investigate",
        json={
            "service": "checkout",
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- Incident CRUD ------------------------------------------------------------


def test_create_incident_returns_201_with_new_status(client):
    body = _create_incident(client)
    assert body["status"] == "new"
    assert body["severity"] == "high"
    assert body["title"] == "Checkout latency spike"


def test_list_incidents_includes_created_incident(client):
    created = _create_incident(client)
    response = client.get("/api/v1/incidents")
    assert response.status_code == 200
    assert any(i["id"] == created["id"] for i in response.json())


def test_get_incident_results_404_for_unknown_incident(client):
    response = client.get("/api/v1/incidents/does-not-exist")
    assert response.status_code == 404


def test_get_incident_timeline_includes_creation_event(client):
    created = _create_incident(client)
    response = client.get(f"/api/v1/incidents/{created['id']}/timeline")
    assert response.status_code == 200
    event_types = [e["event_type"] for e in response.json()]
    assert "incident_created" in event_types


# --- Investigation ------------------------------------------------------------


def test_investigate_persists_diagnosis_and_advances_status(client):
    created = _create_incident(client)
    result = _investigate(client, created["id"])

    assert result["status"] == "diagnosed"
    assert result["diagnosis_id"] is not None
    assert result["probable_cause"] == "A downstream dependency regression caused the incident"
    assert result["hypothesis_count"] == 1

    full = client.get(f"/api/v1/incidents/{created['id']}").json()
    assert full["diagnosis"]["probable_cause"] == result["probable_cause"]
    assert len(full["hypotheses"]) == 1


def test_investigate_404_for_unknown_incident(client):
    response = client.post(
        "/api/v1/incidents/does-not-exist/investigate",
        json={
            "service": "checkout",
            "window_start": "2026-09-06T10:00:00Z",
            "window_end": "2026-09-06T10:15:00Z",
        },
    )
    assert response.status_code == 404


# --- Remediation + Approval (Phase 3) -----------------------------------------


def test_recommend_remediation_classifies_risk_and_creates_approval(client):
    created = _create_incident(client)
    investigation = _investigate(client, created["id"])

    response = client.post(
        f"/api/v1/incidents/{created['id']}/remediations",
        json={
            "diagnosis_id": investigation["diagnosis_id"],
            "action_type": "rollback_deployment",
            "parameters": {"deployment_id": "dep-42"},
            "rationale": "Roll back the regression",
        },
    )
    assert response.status_code == 201, response.text
    remediation = response.json()
    assert remediation["risk_level"] == "high"  # rollback_deployment in production defaults to HIGH

    approvals = client.get(f"/api/v1/incidents/{created['id']}/approvals").json()
    assert len(approvals) == 1
    assert approvals[0]["status"] == "pending"


def test_low_risk_remediation_is_auto_approved(client):
    created = _create_incident(client)
    investigation = _investigate(client, created["id"])

    response = client.post(
        f"/api/v1/incidents/{created['id']}/remediations",
        json={
            "diagnosis_id": investigation["diagnosis_id"],
            "action_type": "restart_service",
            "parameters": {"instance_count": 1},
        },
    )
    assert response.status_code == 201
    approvals = client.get(f"/api/v1/incidents/{created['id']}/approvals").json()
    assert approvals[0]["status"] == "not_required"


def test_execute_blocked_until_approved(client):
    created = _create_incident(client)
    investigation = _investigate(client, created["id"])
    remediation = client.post(
        f"/api/v1/incidents/{created['id']}/remediations",
        json={
            "diagnosis_id": investigation["diagnosis_id"],
            "action_type": "rollback_deployment",
            "parameters": {"deployment_id": "dep-42"},
        },
    ).json()

    response = client.post(f"/api/v1/incidents/{created['id']}/remediations/{remediation['id']}/execute")
    assert response.status_code == 409


def test_decide_approval_then_execute_succeeds(client):
    created = _create_incident(client)
    investigation = _investigate(client, created["id"])
    remediation = client.post(
        f"/api/v1/incidents/{created['id']}/remediations",
        json={
            "diagnosis_id": investigation["diagnosis_id"],
            "action_type": "rollback_deployment",
            "parameters": {"deployment_id": "dep-42"},
        },
    ).json()
    approvals = client.get(f"/api/v1/incidents/{created['id']}/approvals").json()
    approval_id = approvals[0]["id"]

    decision = client.post(
        f"/api/v1/incidents/{created['id']}/approvals/{approval_id}/decision",
        json={"approved": True, "reason": "Looks safe"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"

    execution = client.post(f"/api/v1/incidents/{created['id']}/remediations/{remediation['id']}/execute")
    assert execution.status_code == 201, execution.text
    assert execution.json()["status"] == "simulated"


def test_deciding_already_decided_approval_returns_409(client):
    created = _create_incident(client)
    investigation = _investigate(client, created["id"])
    remediation = client.post(
        f"/api/v1/incidents/{created['id']}/remediations",
        json={
            "diagnosis_id": investigation["diagnosis_id"],
            "action_type": "rollback_deployment",
            "parameters": {"deployment_id": "dep-42"},
        },
    ).json()
    approvals = client.get(f"/api/v1/incidents/{created['id']}/approvals").json()
    approval_id = approvals[0]["id"]

    client.post(f"/api/v1/incidents/{created['id']}/approvals/{approval_id}/decision", json={"approved": True})
    second = client.post(f"/api/v1/incidents/{created['id']}/approvals/{approval_id}/decision", json={"approved": True})
    assert second.status_code == 409


# --- Verification (Phase 5) ---------------------------------------------------


def test_full_pipeline_through_verification(client):
    created = _create_incident(client)
    investigation = _investigate(client, created["id"])
    remediation = client.post(
        f"/api/v1/incidents/{created['id']}/remediations",
        json={
            "diagnosis_id": investigation["diagnosis_id"],
            "action_type": "restart_service",
            "parameters": {"instance_count": 1},
        },
    ).json()

    execution = client.post(
        f"/api/v1/incidents/{created['id']}/remediations/{remediation['id']}/execute"
    ).json()
    assert execution["status"] == "simulated"

    verify_response = client.post(
        f"/api/v1/incidents/{created['id']}/executions/{execution['id']}/verify",
        json={},
    )
    assert verify_response.status_code == 200, verify_response.text
    body = verify_response.json()
    assert body["recovered"] in (True, False)

    full = client.get(f"/api/v1/incidents/{created['id']}").json()
    assert len(full["verifications"]) == 1
    assert len(full["action_executions"]) == 1


# --- Investigation-produced remediation reaches persistence + downstream flow --


def test_investigate_persists_graph_remediation_and_feeds_existing_approval_flow(client_with_remediation):
    """The graph's remediation_planner output must not be silently
    discarded by POST /investigate: it must reach the same persistence,
    risk classification, and approval flow POST /remediations uses -
    proven here by driving the full pipeline

        Investigation -> Diagnosis -> Remediation -> Risk/Approval -> Action -> Verification

    entirely from the automatic /investigate call, with no manual
    POST /remediations anywhere in this test (unlike
    test_full_pipeline_through_verification above, which exercises the
    same downstream chain starting from the manual endpoint).
    """
    client = client_with_remediation
    created = _create_incident(client)
    investigation = _investigate(client, created["id"])

    # The remediation the fake graph produced (ROLLBACK_DEPLOYMENT in
    # production) must already be persisted and risk-classified by the
    # time /investigate returns - not require a separate call.
    assert investigation["remediation_id"] is not None
    assert investigation["risk_level"] == "high"

    full_after_investigate = client.get(f"/api/v1/incidents/{created['id']}").json()
    assert len(full_after_investigate["remediations"]) == 1
    remediation = full_after_investigate["remediations"][0]
    assert remediation["id"] == investigation["remediation_id"]
    assert remediation["action_type"] == "rollback_deployment"
    assert remediation["risk_level"] == "high"
    assert remediation["diagnosis_id"] == investigation["diagnosis_id"]

    # It went through create_approval_request exactly like the manual
    # endpoint does - HIGH risk means PENDING, not auto-approved.
    approvals = client.get(f"/api/v1/incidents/{created['id']}/approvals").json()
    assert len(approvals) == 1
    assert approvals[0]["status"] == "pending"
    assert approvals[0]["remediation_id"] == investigation["remediation_id"]

    # Blocked until approved - same guard the manual-remediation flow has.
    blocked = client.post(
        f"/api/v1/incidents/{created['id']}/remediations/{remediation['id']}/execute"
    )
    assert blocked.status_code == 409

    decision = client.post(
        f"/api/v1/incidents/{created['id']}/approvals/{approvals[0]['id']}/decision",
        json={"approved": True, "reason": "Confirmed safe to roll back"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"

    execution = client.post(f"/api/v1/incidents/{created['id']}/remediations/{remediation['id']}/execute")
    assert execution.status_code == 201, execution.text
    execution_body = execution.json()
    assert execution_body["status"] == "simulated"

    verify_response = client.post(
        f"/api/v1/incidents/{created['id']}/executions/{execution_body['id']}/verify",
        json={},
    )
    assert verify_response.status_code == 200, verify_response.text
    assert verify_response.json()["recovered"] in (True, False)

    full_final = client.get(f"/api/v1/incidents/{created['id']}").json()
    assert len(full_final["remediations"]) == 1
    assert len(full_final["approvals"]) == 1
    assert len(full_final["action_executions"]) == 1
    assert len(full_final["verifications"]) == 1


def test_investigate_without_remediation_leaves_remediation_id_none(client):
    """Sanity check on the other side of the same wiring: when the graph
    does NOT produce a remediation (the plain _FakeGraph, used by every
    other test in this file), /investigate must not fabricate one -
    remediation_id and risk_level stay None, and no Remediation/Approval
    row is created."""
    created = _create_incident(client)
    investigation = _investigate(client, created["id"])

    assert investigation["remediation_id"] is None
    assert investigation["risk_level"] is None

    full = client.get(f"/api/v1/incidents/{created['id']}").json()
    assert full["remediations"] == []
    assert full["approvals"] == []
    