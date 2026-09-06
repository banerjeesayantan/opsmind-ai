"""Data structures for telemetry evidence collected during incident investigation.

These are plain pydantic models, not database tables - they represent the
shape of evidence as it comes out of a telemetry source (log system, metrics
system, deployment tracker), before a decision is made about which pieces
get persisted as app.models.evidence.Evidence rows. Keeping this layer
separate from the Evidence table means a telemetry source can be queried and
inspected freely without writing to the database every time.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class TimeWindow(BaseModel):
    """A bounded time range to filter telemetry queries by.

    Attributes:
        start: Start of the window, inclusive.
        end: End of the window, inclusive.
    """

    start: datetime
    end: datetime

    def contains(self, timestamp: datetime) -> bool:
        """Whether the given timestamp falls within this window."""
        return self.start <= timestamp <= self.end


class LogEntry(BaseModel):
    """A single log line retrieved from a log source.

    Attributes:
        timestamp: When the log line was emitted.
        service: Name of the service that emitted it.
        severity: Log level (e.g. "info", "warning", "error", "critical").
        message: The log message text.
        metadata: Optional structured fields attached to the log line
            (e.g. request_id, trace_id, status_code).
    """

    timestamp: datetime
    service: str
    severity: str
    message: str
    metadata: dict = Field(default_factory=dict)


class MetricPoint(BaseModel):
    """A single metric reading retrieved from a metrics source.

    Attributes:
        timestamp: When the metric was recorded.
        service: Name of the service the metric belongs to.
        metric_name: Name of the metric (e.g. "http_request_duration_seconds").
        value: The recorded numeric value.
        labels: Optional dimension labels (e.g. endpoint, status_code).
    """

    timestamp: datetime
    service: str
    metric_name: str
    value: float
    labels: dict = Field(default_factory=dict)


class DeploymentEvent(BaseModel):
    """A single deployment record retrieved from a deployment source.

    Attributes:
        timestamp: When the deployment occurred.
        service: Name of the service that was deployed.
        deployment_id: Identifier for this deployment.
        commit_sha: Git commit SHA that was deployed.
        environment: Which environment this deployment targeted
            (e.g. "production", "staging").
        change_summary: Human-readable summary of what changed.
    """

    timestamp: datetime
    service: str
    deployment_id: str
    commit_sha: str
    environment: str
    change_summary: str = ""


class EvidenceBundle(BaseModel):
    """The combined result of querying all telemetry sources for an incident.

    This is what app.telemetry.service.TelemetryService returns - a single
    structured object covering everything collected for a given service and
    time window, ready to be turned into app.models.evidence.Evidence rows
    or handed to the investigation graph.

    Attributes:
        service: The service the evidence was collected for.
        time_window: The time window the evidence was filtered to.
        logs: Matching log entries.
        metrics: Matching metric points.
        deployments: Matching deployment events.
    """

    service: str
    time_window: TimeWindow
    logs: list[LogEntry] = Field(default_factory=list)
    metrics: list[MetricPoint] = Field(default_factory=list)
    deployments: list[DeploymentEvent] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """Whether this bundle contains no evidence at all."""
        return not (self.logs or self.metrics or self.deployments)

    @property
    def total_count(self) -> int:
        """Total number of evidence items across all sources."""
        return len(self.logs) + len(self.metrics) + len(self.deployments)