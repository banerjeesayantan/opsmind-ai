"""Regression test for the Prometheus metrics / nested-router interaction.

Guards against a specific incompatibility: the third-party
starlette_prometheus.PrometheusMiddleware walks request.app.routes and reads
`.path` directly off whatever route.matches() returns. Newer Starlette
versions wrap an app.include_router()'d router in an internal object with no
`.path` attribute, so that middleware raises AttributeError on every request
handled through a nested router - which is every /api/v1/... endpoint here
(incidents_router is included under api_router, which is included under
app).

The fix removes that middleware registration entirely rather than
replacing it with an equivalent: app.core.middleware.MetricsMiddleware
(registered separately in app.main) already records http_requests_total /
http_request_duration_seconds per request using the plain request path -
no router traversal, never affected by this bug - so re-adding another
middleware to do the same job would only double-count every request.
app.core.metrics.setup_metrics now only registers the /metrics scrape
endpoint itself.

This test exercises the real app, the real middleware stack, and a real
nested-router endpoint end-to-end via TestClient - it would have failed
with the reported AttributeError against the old
starlette_prometheus-based implementation.

Run with: pytest tests/test_metrics_middleware.py -v
"""

from fastapi.testclient import TestClient

from app.core.metrics import http_requests_total
from app.main import app


def _counter_value(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


def test_metrics_endpoint_returns_prometheus_text_with_phase6_metrics():
    """GET /metrics must keep working and expose the Phase 6 metric names."""
    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "opsmind_approvals_total" in body
    assert "opsmind_action_executions_total" in body
    assert "opsmind_verifications_total" in body


def test_request_through_nested_incidents_router_does_not_raise():
    """A request to a nested-router endpoint must not raise AttributeError.

    Regression guard for the exact reported failure: POST
    /api/v1/incidents is served by incidents_router, included under
    api_router, included under app - the specific nesting shape that broke
    starlette_prometheus's route-path lookup.

    Asserts 401, not 201: incident routes now require
    Depends(get_current_user) (see app.api.v1.incidents), so an
    unauthenticated request correctly gets rejected by auth rather than
    reaching persistence - but the point of this regression guard is
    just that the middleware itself doesn't raise AttributeError while
    routing through the nested router, and a clean 401 is just as much
    evidence of that as a 201 would be.
    """
    with TestClient(app) as client:
        response = client.post("/api/v1/incidents", json={"title": "Metrics regression check", "service": "checkout"})

    assert response.status_code == 401


def test_request_through_nested_router_increments_http_requests_total_exactly_once():
    """Per-request metrics (from app.core.middleware.MetricsMiddleware) still work,
    and aren't double-counted by a second, redundant middleware.
    """
    before = _counter_value(http_requests_total, method="GET", endpoint="/api/v1/health", status=200)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    after = _counter_value(http_requests_total, method="GET", endpoint="/api/v1/health", status=200)
    assert after == before + 1