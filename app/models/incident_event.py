"""This file contains the IncidentEvent model - append-only timeline entries for an incident."""

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

if TYPE_CHECKING:
    from app.models.incident import Incident


class IncidentEvent(BaseModel, table=True):
    """A single append-only timeline entry for an incident.

    This is the raw chronological record ("10:02 deployment", "10:07
    investigation started", "10:10 rollback approved") that the incident
    timeline / postmortem is rendered from. Entries are never edited or
    deleted, only appended, so the timeline reflects what actually happened
    and when - not a reconstruction after the fact.

    Attributes:
        id: The primary key.
        incident_id: Foreign key to the parent incident.
        event_type: Free-text category of the event (e.g. "deployment",
            "alert_triggered", "investigation_started", "hypothesis_proposed",
            "approval_granted", "action_executed", "verification_passed").
            Deliberately not a closed enum - the set of things worth
            recording on a timeline grows over time and shouldn't require a
            schema migration every time.
        description: Human-readable summary of what happened.
        occurred_at: When the event actually occurred (may differ from
            created_at if the event is recorded slightly after the fact).
        event_metadata: Optional structured payload for the event (e.g. a
            deployment's commit SHA, a metric's threshold value). Named
            event_metadata rather than metadata because metadata is a
            reserved attribute on SQLModel/SQLAlchemy table classes.
        incident: Relationship back to the parent incident.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str = Field(foreign_key="incident.id", index=True)
    event_type: str = Field(index=True)
    description: str = Field(default="")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    event_metadata: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    incident: "Incident" = Relationship(back_populates="events")