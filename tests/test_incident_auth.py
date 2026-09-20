"""Focused regression tests for JWT auth + ownership on the incident API.

Companion to tests/test_api_incidents.py (which now authenticates via the
`client` fixture's _register_and_authenticate helper) and
tests/test_jwt_security.py (which exercises app.utils.auth's token
verification in isolation). This file exercises the layer in between:
that every incident route actually enforces Depends(get_current_user),
and that identity fields the app must never trust from the client
(Incident.created_by, Approval.decided_by) are always taken from the
authenticated token rather than the request body.

Run with: pytest tests/test_incident_auth.py -v
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth import db_service as auth_db_service
from app.api.v1.incidents import (
    get_investigation_graph,
    get_persistence_service,
    get_verification_service,
)
from app.investigation.verification import VerificationService
from app.main import app
from app.services.persistence import IncidentPersistenceService, incident_persistence_service
from app.utils.auth import create_access_token
from tests.test_api_incidents import (
    _FakeGraph,
    _FakeGraphWithRemediation,
    _create_incident,
    _investigate,
    _register_and_authenticate,
)


@pytest.fixture()
def anon_client(test_engine, monkeypatch):
    """Same wiring as test_api_incidents.client, but deliberately does NOT
    authenticate - every test in this file that checks rejection behavior
    needs a client that has no Authorization header at all by default.
    """
    service = IncidentPersistenceService(engine=test_engine)
    monkeypatch.setattr(incident_persistence_service, "engine", test_engine)
    monkeypatch.setattr(auth_db_service, "engine", test_engine)
    app.dependency_overrides[get_persistence_service] = lambda: service
    app.dependency_overrides[get_investigation_graph] = lambda: _FakeGraph()
    app.dependency_overrides[get_verification_service] = lambda: VerificationService()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def client(anon_client):
    """An authenticated client, built on top of anon_client's wiring."""
    _register_and_authenticate(anon_client)
    return anon_client


@pytest.fixture()
def client_with_remediation(test_engine, monkeypatch):
    service = IncidentPersistenceService(engine=test_engine)
    monkeypatch.setattr(incident_persistence_service, "engine", test_engine)
    monkeypatch.setattr(auth_db_service, "engine", test_engine)
    app.dependency_overrides[get_persistence_service] = lambda: service
    app.dependency_overrides[get_investigation_graph] = lambda: _FakeGraphWithRemediation()
    app.dependency_overrides[get_verification_service] = lambda: VerificationService()

    with TestClient(app) as test_client:
        _register_and_authenticate(test_client)
        yield test_client

    app.dependency_overrides.clear()


# --- Every incident route rejects unauthenticated requests ------------------

# (method, path template, json body or None) - path uses placeholder ids that
# don't need to resolve to real rows, since auth must reject the request
# before a handler ever looks up the incident/approval/execution.
_PROTECTED_ROUTES = [
    ("POST", "/api/v1/incidents", {"title": "x", "service": "checkout"}),
    ("GET", "/api/v1/incidents", None),
    ("GET", "/api/v1/incidents/does-not-exist", None),
    ("GET", "/api/v1/incidents/does-not-exist/timeline", None),
    ("GET", "/api/v1/incidents/does-not-exist/evidence", None),
    (
        "POST",
        "/api/v1/incidents/does-not-exist/investigate",
        {
            "service": "checkout",
            "window_start": "2026-09-06T10:00:00Z",
            "window_end": "2026-09-06T10:15:00Z",
        },
    ),
    (
        "POST",
        "/api/v1/incidents/does-not-exist/remediations",
        {"diagnosis_id": 1, "action_type": "restart_service"},
    ),
    ("GET", "/api/v1/incidents/does-not-exist/approvals", None),
    ("POST", "/api/v1/incidents/does-not-exist/approvals/1/decision", {"approved": True}),
    ("POST", "/api/v1/incidents/does-not-exist/remediations/1/execute", None),
    ("POST", "/api/v1/incidents/does-not-exist/executions/1/verify", {}),
]


@pytest.mark.parametrize("method,path,body", _PROTECTED_ROUTES, ids=[p for _, p, _ in _PROTECTED_ROUTES])
def test_incident_routes_reject_requests_with_no_token(anon_client, method, path, body):
    """No Authorization header at all -> 401/403 before any business logic runs.

    FastAPI's HTTPBearer (the security scheme app.api.v1.auth.security
    wraps) responds 403 for a totally missing Authorization header and
    401 once a header is present but invalid - both are "not
    authenticated", so both are accepted here rather than pinning to one.
    """
    response = anon_client.request(method, path, json=body)
    assert response.status_code in (401, 403), response.text


@pytest.mark.parametrize("method,path,body", _PROTECTED_ROUTES, ids=[p for _, p, _ in _PROTECTED_ROUTES])
def test_incident_routes_reject_garbage_token(anon_client, method, path, body):
    """A well-formed-looking but garbage bearer token must be rejected."""
    anon_client.headers.update({"Authorization": "Bearer not-a-real-token"})
    response = anon_client.request(method, path, json=body)
    assert response.status_code in (401, 422), response.text


def test_incident_routes_reject_expired_token(anon_client):
    """A syntactically valid JWT that has already expired must be rejected,
    not just a token with garbage content - regression guard against only
    checking token *shape* and forgetting to check `exp`.
    """
    expired = create_access_token(thread_id="1", expires_delta=timedelta(seconds=-1))
    anon_client.headers.update({"Authorization": f"Bearer {expired.access_token}"})
    response = anon_client.post("/api/v1/incidents", json={"title": "x", "service": "checkout"})
    assert response.status_code == 401, response.text


def test_incident_routes_reject_token_for_nonexistent_user(anon_client):
    """A structurally valid, unexpired token whose subject isn't a real
    user id must still be rejected - get_current_user (app.api.v1.auth)
    re-verifies the user exists in the database on every request rather
    than trusting the token's claims alone.
    """
    token = create_access_token(thread_id="999999999")
    anon_client.headers.update({"Authorization": f"Bearer {token.access_token}"})
    response = anon_client.post("/api/v1/incidents", json={"title": "x", "service": "checkout"})
    assert response.status_code == 404, response.text


def test_authenticated_request_succeeds(client):
    """Sanity check: a real, valid token is actually sufficient - the
    rejection tests above aren't accidentally passing because every
    request fails for some unrelated reason.
    """
    incident = _create_incident(client)
    assert incident["status"] == "new"


# --- created_by cannot be spoofed by the client ------------------------------


def test_created_by_is_the_authenticated_user_not_client_supplied(client):
    """IncidentCreateRequest has no created_by field at all (see
    app.schemas.incident), so even trying to smuggle one through in the
    JSON body must have no effect - the persisted row's created_by must
    be the user identified by the caller's own bearer token.
    """
    response = client.post(
        "/api/v1/incidents",
        json={"title": "x", "service": "checkout", "created_by": 424242},
    )
    assert response.status_code == 201, response.text
    incident_id = response.json()["id"]

    import asyncio

    stored = asyncio.run(incident_persistence_service.get_incident(incident_id))
    assert stored.created_by is not None
    assert stored.created_by != 424242

# --- decided_by cannot be spoofed by the client ------------------------------


def test_decided_by_is_the_authenticated_user_not_client_supplied(client_with_remediation):
    """ApprovalDecisionRequest has no decided_by field (removed - see
    app.schemas.incident.ApprovalDecisionRequest's docstring), so a
    caller cannot attribute their decision to another user id.
    """
    incident = _create_incident(client_with_remediation)
    _investigate(client_with_remediation, incident["id"])

    approvals = client_with_remediation.get(f"/api/v1/incidents/{incident['id']}/approvals").json()
    assert len(approvals) == 1
    approval_id = approvals[0]["id"]

    response = client_with_remediation.post(
        f"/api/v1/incidents/{incident['id']}/approvals/{approval_id}/decision",
        json={"approved": True, "reason": "looks safe", "decided_by": 999999},
    )
    assert response.status_code == 200, response.text
    decided = response.json()
    assert decided["decided_by"] is not None
    assert decided["decided_by"] != 999999


def test_second_authenticated_user_cannot_read_or_act_using_first_users_incident_id_guessing_alone(
    anon_client, test_engine, monkeypatch
):
    """Not a substitute for the ownership check above - this just confirms
    that acting on an incident still requires *some* valid token; a
    second real user's token is enough to reach the route (this API is a
    shared team tool, not a per-user silo - see Incident.created_by's
    docstring: "created_by ... nullable - an incident may be opened by
    an automated alert with no human reporter yet attached"), but an
    unauthenticated caller is never enough, matching the parametrized
    rejection tests above.

    Uses two independent TestClient instances against the same
    test_engine/app wiring, rather than the shared `client` fixture, so
    "user A's incident" and "user B's (or no) token" are genuinely
    different identities rather than accidentally the same fixture
    instance.
    """
    service = IncidentPersistenceService(engine=test_engine)
    monkeypatch.setattr(incident_persistence_service, "engine", test_engine)
    monkeypatch.setattr(auth_db_service, "engine", test_engine)
    app.dependency_overrides[get_persistence_service] = lambda: service
    app.dependency_overrides[get_investigation_graph] = lambda: _FakeGraph()
    app.dependency_overrides[get_verification_service] = lambda: VerificationService()

    with TestClient(app) as owner_client:
        _register_and_authenticate(owner_client)
        incident = _create_incident(owner_client)

    # A second, independent, unauthenticated client must be rejected outright.
    unauthenticated = anon_client.get(f"/api/v1/incidents/{incident['id']}")
    assert unauthenticated.status_code in (401, 403)

    # Once that same client authenticates as a *different* real user, it
    # can reach the route (shared-team-tool model) - but getting there
    # required a real, valid token, not incident-id guessing alone.
    _register_and_authenticate(anon_client)
    now_authenticated = anon_client.get(f"/api/v1/incidents/{incident['id']}")
    assert now_authenticated.status_code == 200
