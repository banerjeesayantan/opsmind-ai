"""Telemetry layer: collects investigation evidence for an incident.

Public surface of this package - everything else (interfaces.py,
mock_sources.py, service.py, schemas.py, prometheus_source.py) is an
implementation detail that callers outside this package shouldn't need to import directly.
"""

from app.telemetry.interfaces import (
    DeploymentSource,
    LogSource,
    MetricSource,
)
from app.telemetry.prometheus_source import PrometheusMetricSource
from app.telemetry.schemas import (
    DeploymentEvent,
    EvidenceBundle,
    LogEntry,
    MetricPoint,
    TimeWindow,
)
from app.telemetry.service import TelemetryService

__all__ = [
    "DeploymentEvent",
    "DeploymentSource",
    "EvidenceBundle",
    "LogEntry",
    "LogSource",
    "MetricPoint",
    "MetricSource",
    "PrometheusMetricSource",
    "TelemetryService",
    "TimeWindow",
]