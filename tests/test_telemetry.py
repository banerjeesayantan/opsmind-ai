"""Automated tests for the telemetry layer (app.telemetry).

Each test is a plain synchronous function that drives the async telemetry
API via asyncio.run(), so no additional test dependency (e.g.
pytest-asyncio) is needed beyond the pytest already declared in
pyproject.toml.

Run with: pytest tests/test_telemetry.py -v
"""

import asyncio
from datetime import datetime, timedelta, UTC

from app.telemetry import TelemetryService, TimeWindow
from app.telemetry.interfaces import (
    DeploymentSource,
    LogSource,
    MetricSource,
)
from app.telemetry.mock_sources import (
    MockDeploymentSource,
    MockLogSource,
    MockMetricSource,
)
from app.telemetry.schemas import (
    DeploymentEvent,
    EvidenceBundle,
    LogEntry,
    MetricPoint,
)


def _incident_window() -> TimeWindow:
    """The MVP scenario's time window: checkout, 10:00-10:15."""
    return TimeWindow(
        start=datetime(2026, 9, 6, 10, 0, tzinfo=UTC),
        end=datetime(2026, 9, 6, 10, 15, tzinfo=UTC),
    )


# --- TimeWindow -------------------------------------------------------------


def test_time_window_contains_boundaries_inclusive():
    """start and end themselves should be considered inside the window."""
    tw = _incident_window()
    assert tw.contains(tw.start) is True
    assert tw.contains(tw.end) is True


def test_time_window_excludes_outside_timestamps():
    tw = _incident_window()
    assert tw.contains(tw.start - timedelta(seconds=1)) is False
    assert tw.contains(tw.end + timedelta(seconds=1)) is False


# --- EvidenceBundle helpers ---------------------------------------------------


def test_evidence_bundle_is_empty_when_nothing_collected():
    bundle = EvidenceBundle(service="checkout", time_window=_incident_window())
    assert bundle.is_empty is True
    assert bundle.total_count == 0


def test_evidence_bundle_total_count_sums_all_sources():
    tw = _incident_window()
    bundle = EvidenceBundle(
        service="checkout",
        time_window=tw,
        logs=[LogEntry(timestamp=tw.start, service="checkout", severity="info", message="x")],
        metrics=[MetricPoint(timestamp=tw.start, service="checkout", metric_name="m", value=1.0)],
        deployments=[
            DeploymentEvent(
                timestamp=tw.start,
                service="checkout",
                deployment_id="d1",
                commit_sha="sha1",
                environment="production",
            )
        ],
    )
    assert bundle.total_count == 3
    assert bundle.is_empty is False


# --- Mock sources: filtering behavior ----------------------------------------


def test_mock_log_source_filters_to_time_window():
    tw = _incident_window()
    logs = asyncio.run(MockLogSource().fetch("checkout", tw))
    assert len(logs) == 4
    assert all(tw.contains(log.timestamp) for log in logs)
    assert all(log.service == "checkout" for log in logs)


def test_mock_log_source_narrower_window_returns_fewer_results():
    tw = TimeWindow(start=_incident_window().start, end=_incident_window().start + timedelta(minutes=3))
    logs = asyncio.run(MockLogSource().fetch("checkout", tw))
    assert len(logs) == 1


def test_mock_metric_source_filters_to_time_window():
    tw = _incident_window()
    metrics = asyncio.run(MockMetricSource().fetch("checkout", tw))
    assert len(metrics) == 4
    assert all(tw.contains(m.timestamp) for m in metrics)


def test_mock_deployment_source_found_via_lookback():
    """The deployment sits 2 minutes before time_window.start, outside the
    incident window itself but still returned - this is the whole point of
    this source modeling deployments that happen slightly before an
    incident starts, unlike logs/metrics which are filtered strictly to
    the incident window."""
    tw = _incident_window()
    deployments = asyncio.run(MockDeploymentSource().fetch("checkout", tw))
    assert len(deployments) == 1
    assert deployments[0].timestamp < tw.start
    assert tw.start - deployments[0].timestamp == timedelta(minutes=2)


def test_mock_deployment_source_repositions_relative_to_any_window():
    """Because this mock defines the deployment's position relative to
    whichever window is queried (by design, so results are deterministic
    regardless of calendar date), it has no real 'not found' case - a
    query for any window, including one far in the future, still finds a
    deployment positioned 2 minutes before that window's start. This is a
    property of the mock's generation strategy, not a bug: a real
    deployment source, querying a fixed deployment history, would behave
    differently and could legitimately return an empty list."""
    far_future_start = _incident_window().start + timedelta(days=1)
    tw = TimeWindow(start=far_future_start, end=far_future_start + timedelta(minutes=15))
    deployments = asyncio.run(MockDeploymentSource().fetch("checkout", tw))
    assert len(deployments) == 1
    assert deployments[0].timestamp == far_future_start - timedelta(minutes=2)


def test_mock_sources_are_deterministic():
    """The same time window queried twice must produce identical results."""
    tw = _incident_window()
    first = asyncio.run(MockLogSource().fetch("checkout", tw))
    second = asyncio.run(MockLogSource().fetch("checkout", tw))
    assert [entry.model_dump() for entry in first] == [entry.model_dump() for entry in second]


def test_mock_sources_work_for_any_service_name():
    """Mocks are not hardcoded to the 'checkout' example service."""
    tw = _incident_window()
    logs = asyncio.run(MockLogSource().fetch("payments-api", tw))
    assert len(logs) == 4
    assert all(log.service == "payments-api" for log in logs)


# --- TelemetryService: end-to-end orchestration ------------------------------


def test_telemetry_service_collects_full_mvp_scenario():
    """The exact scenario from the telemetry spec: checkout, 10:00-10:15."""
    service = TelemetryService.with_mock_sources()
    bundle = asyncio.run(service.collect_evidence("checkout", _incident_window()))

    assert bundle.service == "checkout"
    assert len(bundle.logs) == 4
    assert len(bundle.metrics) == 4
    assert len(bundle.deployments) == 1
    assert bundle.total_count == 9
    assert bundle.is_empty is False


def test_telemetry_service_is_deterministic_across_calls():
    service = TelemetryService.with_mock_sources()
    tw = _incident_window()
    first = asyncio.run(service.collect_evidence("checkout", tw))
    second = asyncio.run(service.collect_evidence("checkout", tw))
    assert first.model_dump() == second.model_dump()


def test_telemetry_service_depends_only_on_interfaces_not_mock_classes():
    """Injecting a completely different implementation (not Mock*) must
    work identically - this is what proves real telemetry adapters
    (Prometheus, Loki, GitHub) can replace mocks with zero changes to
    TelemetryService or callers of it."""

    class FakeLogSource(LogSource):
        async def fetch(self, service, time_window):
            return [
                LogEntry(
                    timestamp=time_window.start,
                    service=service,
                    severity="debug",
                    message="injected fake, not a Mock* class",
                )
            ]

    class EmptyMetricSource(MetricSource):
        async def fetch(self, service, time_window):
            return []

    class EmptyDeploymentSource(DeploymentSource):
        async def fetch(self, service, time_window):
            return []

    service = TelemetryService(
        log_source=FakeLogSource(),
        metric_source=EmptyMetricSource(),
        deployment_source=EmptyDeploymentSource(),
    )
    bundle = asyncio.run(service.collect_evidence("checkout", _incident_window()))

    assert len(bundle.logs) == 1
    assert bundle.logs[0].message == "injected fake, not a Mock* class"
    assert len(bundle.metrics) == 0
    assert len(bundle.deployments) == 0


def test_telemetry_service_narrower_window_returns_fewer_results():
    """Proves the service's filtering is real end-to-end, not just at the
    individual mock-source level tested above."""
    service = TelemetryService.with_mock_sources()
    narrow = TimeWindow(start=_incident_window().start, end=_incident_window().start + timedelta(minutes=3))
    bundle = asyncio.run(service.collect_evidence("checkout", narrow))
    assert bundle.total_count < 9


# --- PrometheusMetricSource --------------------------------------------------


def test_prometheus_metric_source_parses_matrix_response():
    """Validates that standard Prometheus query_range responses are mapped to MetricPoints."""
    import httpx
    from app.telemetry.prometheus_source import PrometheusMetricSource

    mock_resp_data = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {
                        "__name__": "http_requests_total",
                        "service": "checkout",
                        "status": "500",
                    },
                    "values": [
                        [1788775200.0, "12.5"],
                        [1788775260.0, "18.2"],
                    ],
                }
            ],
        },
    }

    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, json=mock_resp_data)

    client = httpx.AsyncClient(transport=MockTransport())
    source = PrometheusMetricSource(base_url="http://prom-test:9090", client=client)

    tw = _incident_window()
    points = asyncio.run(source.fetch("checkout", tw))

    assert len(points) == 2
    assert points[0].metric_name == "http_requests_total"
    assert points[0].value == 12.5
    assert points[0].service == "checkout"
    assert points[0].labels["status"] == "500"
    assert points[1].value == 18.2


def test_prometheus_metric_source_handles_http_errors_gracefully():
    """Prometheus 500/unreachable errors must return an empty list without crashing."""
    import httpx
    from app.telemetry.prometheus_source import PrometheusMetricSource

    class ErrorTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(503, text="Service Unavailable")

    client = httpx.AsyncClient(transport=ErrorTransport())
    source = PrometheusMetricSource(base_url="http://prom-error:9090", client=client)

    points = asyncio.run(source.fetch("checkout", _incident_window()))
    assert points == []


def test_prometheus_metric_source_handles_network_exceptions_gracefully():
    """Network connection drop / timeout must return empty list safely."""
    import httpx
    from app.telemetry.prometheus_source import PrometheusMetricSource

    class FaultyTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            raise httpx.ConnectError("Connection refused by host")

    client = httpx.AsyncClient(transport=FaultyTransport())
    source = PrometheusMetricSource(base_url="http://prom-dead:9090", client=client)

    points = asyncio.run(source.fetch("checkout", _incident_window()))
    assert points == []