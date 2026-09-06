"""Abstract adapter interfaces for telemetry sources.

Each interface defines a single contract - fetch(service, time_window) -
that any concrete source must implement. app.telemetry.mock_sources
provides deterministic local implementations for development and testing;
a real implementation (Prometheus, Loki, GitHub, a cloud logging API) is a
drop-in replacement for a mock, since app.telemetry.service.TelemetryService
depends only on these interfaces, never on a concrete source.
"""

from abc import ABC, abstractmethod

from app.telemetry.schemas import (
    DeploymentEvent,
    LogEntry,
    MetricPoint,
    TimeWindow,
)


class LogSource(ABC):
    """Adapter interface for retrieving log entries for a service."""

    @abstractmethod
    async def fetch(self, service: str, time_window: TimeWindow) -> list[LogEntry]:
        """Fetch log entries for a service within a time window.

        Args:
            service: Name of the service to fetch logs for.
            time_window: The time range to filter logs to.

        Returns:
            list[LogEntry]: Matching log entries, in any order - callers
            that need a specific order should sort explicitly.
        """
        raise NotImplementedError


class MetricSource(ABC):
    """Adapter interface for retrieving metric readings for a service."""

    @abstractmethod
    async def fetch(self, service: str, time_window: TimeWindow) -> list[MetricPoint]:
        """Fetch metric points for a service within a time window.

        Args:
            service: Name of the service to fetch metrics for.
            time_window: The time range to filter metrics to.

        Returns:
            list[MetricPoint]: Matching metric points, in any order.
        """
        raise NotImplementedError


class DeploymentSource(ABC):
    """Adapter interface for retrieving deployment history for a service."""

    @abstractmethod
    async def fetch(self, service: str, time_window: TimeWindow) -> list[DeploymentEvent]:
        """Fetch deployment events for a service within a time window.

        Args:
            service: Name of the service to fetch deployments for.
            time_window: The time range to filter deployments to.

        Returns:
            list[DeploymentEvent]: Matching deployment events, in any order.
        """
        raise NotImplementedError