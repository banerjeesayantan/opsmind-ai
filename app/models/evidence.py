"""This file contains the Evidence model - observed facts collected during incident investigation."""

from datetime import datetime, UTC
from typing import (
    TYPE_CHECKING,
    Optional,
)

from sqlmodel import (
    Column,
    Field,
    JSON,
    Relationship,
)

from app.models.base import BaseModel
from app.models.incident_enums import EvidenceSource

if TYPE_CHECKING:
    from app.models.incident import Incident


class Evidence(BaseModel, table=True):
    """A single piece of observed evidence collected during investigation.

    This table holds only what was actually observed - a log line, a metric
    reading, a deployment record, a runbook excerpt. It never holds an AI's
    interpretation of that data; interpretation belongs to Hypothesis and
    Diagnosis, which reference evidence rather than contain it. This
    separation is what lets a diagnosis be checked against what was really
    observed instead of taking the model's word for it.

    Attributes:
        id: The primary key.
        incident_id: Foreign key to the parent incident.
        source: Which telemetry category this evidence came from.
        source_reference: Pointer back to the raw source for traceability
            (e.g. a log line id, a metric name, a deployment id). Optional
            because not every source has a stable reference.
        content: Human-readable description of what was observed.
        raw_data: Optional structured payload for the underlying data point,
            when the source provides one (e.g. a metric's numeric series).
        occurred_at: When the underlying event actually happened. This is
            what time-window filtering during investigation is based on -
            deliberately separate from collected_at.
        collected_at: When this evidence was pulled into the system.
        incident: Relationship back to the parent incident.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str = Field(foreign_key="incident.id", index=True)
    source: EvidenceSource = Field(index=True)
    source_reference: Optional[str] = Field(default=None)
    content: str
    raw_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    occurred_at: datetime = Field(index=True)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    incident: "Incident" = Relationship(back_populates="evidence")