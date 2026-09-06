"""Deterministic mock telemetry sources for local development and testing.

Each mock simulates the same story - a deployment shortly before an
incident's time window, followed by rising latency and timeouts inside
it - anchored to relative offsets from time_window.start rather than fixed
calendar timestamps. This means the same time_window always produces the
same evidence regardless of what actual date an incident is created on,
which is what makes automated tests against these mocks reproducible.

These are the $0/local default. A real implementation (Prometheus, Loki,
GitHub, a cloud logging API) can replace any of these without changing
app.telemetry.service.TelemetryService, since it depends only on the
interfaces in app.telemetry.interfaces.
"""

from datetime import timedelta

from app.telemetry.interfaces import (
    DeploymentSource,
    LogSource,
    MetricSource,
)
from app.telemetry.schemas import (
    DeploymentEvent,
    LogEntry,
    MetricPoint,
    TimeWindow,
)


class MockLogSource(LogSource):
    """Simulates log output during a deployment-induced latency regression."""

    async def fetch(self, service: str, time_window: TimeWindow) -> list[LogEntry]:
        """Return simulated log entries falling within the given time window."""
        base = time_window.start
        candidates = [
            LogEntry(
                timestamp=base - timedelta(minutes=2),
                service=service,
                severity="info",
                message=f"Deployment completed for {service}",
            ),
            LogEntry(
                timestamp=base + timedelta(minutes=2),
                service=service,
                severity="warning",
                message="Slow response from downstream dependency: 2400ms",
            ),
            LogEntry(
                timestamp=base + timedelta(minutes=5),
                service=service,
                severity="error",
                message="Timeout calling downstream dependency after 3000ms",
            ),
            LogEntry(
                timestamp=base + timedelta(minutes=7),
                service=service,
                severity="error",
                message="Timeout calling downstream dependency after 3200ms",
            ),
            LogEntry(
                timestamp=base + timedelta(minutes=10),
                service=service,
                severity="warning",
                message="High latency observed: p95=2800ms",
            ),
        ]
        return [entry for entry in candidates if time_window.contains(entry.timestamp)]


class MockMetricSource(MetricSource):
    """Simulates a latency metric climbing after a deployment."""

    async def fetch(self, service: str, time_window: TimeWindow) -> list[MetricPoint]:
        """Return simulated metric points falling within the given time window."""
        base = time_window.start
        offsets_and_values = [
            (timedelta(minutes=-2), 0.3),
            (timedelta(minutes=0), 0.4),
            (timedelta(minutes=5), 1.8),
            (timedelta(minutes=10), 2.4),
            (timedelta(minutes=14), 2.6),
        ]
        candidates = [
            MetricPoint(
                timestamp=base + offset,
                service=service,
                metric_name="http_request_duration_seconds",
                value=value,
            )
            for offset, value in offsets_and_values
        ]
        return [point for point in candidates if time_window.contains(point.timestamp)]


class MockDeploymentSource(DeploymentSource):
    """Simulates a single deployment shortly before an incident's time window.

    The deployment is generated at a fixed offset (2 minutes) before
    time_window.start, so it always falls just outside the incident window
    itself but is still returned - this models the realistic case where the
    deployment that caused an incident happened slightly before the
    incident's own time window starts, unlike logs and metrics, which are
    filtered strictly to the incident window. Because the deployment's
    position is always defined relative to whichever window is queried,
    this mock has no "deployment not found" case to simulate; a real
    deployment source, querying a fixed deployment history against an
    arbitrary window, would.
    """

    async def fetch(self, service: str, time_window: TimeWindow) -> list[DeploymentEvent]:
        """Return the simulated deployment, positioned 2 minutes before the window starts."""
        deployment_time = time_window.start - timedelta(minutes=2)
        return [
            DeploymentEvent(
                timestamp=deployment_time,
                service=service,
                deployment_id="dep-42",
                commit_sha="a1b2c3d",
                environment="production",
                change_summary="Updated downstream dependency timeout handling",
            )
        ]