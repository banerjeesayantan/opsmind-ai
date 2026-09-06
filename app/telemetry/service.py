"""Orchestrates the telemetry sources into a single evidence bundle for an incident."""

import asyncio

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
    EvidenceBundle,
    TimeWindow,
)


class TelemetryService:
    """Collects evidence from all telemetry sources for a service and time window.

    Depends only on the LogSource / MetricSource / DeploymentSource
    interfaces, never on a concrete implementation - a real adapter
    (Prometheus, Loki, GitHub, a cloud logging API) is a drop-in
    replacement via the constructor, with no change to this class or
    anything that calls it.
    """

    def __init__(
        self,
        log_source: LogSource,
        metric_source: MetricSource,
        deployment_source: DeploymentSource,
    ):
        """Initialize the service with concrete telemetry source adapters.

        Args:
            log_source: Adapter for retrieving log entries.
            metric_source: Adapter for retrieving metric points.
            deployment_source: Adapter for retrieving deployment events.
        """
        self._log_source = log_source
        self._metric_source = metric_source
        self._deployment_source = deployment_source

    @classmethod
    def with_mock_sources(cls) -> "TelemetryService":
        """Build a TelemetryService wired with the deterministic $0/local mock sources.

        This is the default for development, testing, and any environment
        where real telemetry integrations haven't been configured yet.
        """
        return cls(
            log_source=MockLogSource(),
            metric_source=MockMetricSource(),
            deployment_source=MockDeploymentSource(),
        )

    async def collect_evidence(self, service: str, time_window: TimeWindow) -> EvidenceBundle:
        """Collect evidence from all three sources concurrently.

        Args:
            service: Name of the service under investigation.
            time_window: The incident's time window to filter evidence to.

        Returns:
            EvidenceBundle: The combined, structured evidence from all
            three sources.
        """
        logs, metrics, deployments = await asyncio.gather(
            self._log_source.fetch(service, time_window),
            self._metric_source.fetch(service, time_window),
            self._deployment_source.fetch(service, time_window),
        )
        return EvidenceBundle(
            service=service,
            time_window=time_window,
            logs=logs,
            metrics=metrics,
            deployments=deployments,
        )

    