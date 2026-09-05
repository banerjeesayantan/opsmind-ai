"""This file contains the Postmortem model - the written retrospective for a resolved incident."""

from datetime import datetime, UTC
from typing import (
    TYPE_CHECKING,
    List,
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
    from app.models.user import User


class Postmortem(BaseModel, table=True):
    """The written retrospective for an incident, produced after resolution.

    One postmortem per incident (incident_id is unique) - this is the
    document a team would actually read afterward, distinct from the raw
    IncidentEvent timeline it's derived from. All measured figures it cites
    should come from the incident's actual recorded data (evidence,
    diagnosis, execution, verification), never invented after the fact.

    Attributes:
        id: The primary key.
        incident_id: Foreign key to the incident this postmortem covers.
            Unique - an incident has at most one postmortem.
        summary: High-level summary of what happened and how it was
            resolved.
        root_cause_summary: Plain-language write-up of the final root
            cause, drawn from the incident's active Diagnosis.
        timeline_summary: Narrative walk-through of the incident timeline,
            drawn from the incident's IncidentEvent rows.
        lessons_learned: What the team is taking away from the incident.
        action_items: Follow-up items to prevent recurrence, as a JSON
            list of short strings.
        written_by: Foreign key to the user who authored the postmortem.
            Nullable since a first draft may be system-generated before a
            human reviews and finalizes it.
        written_at: When the postmortem was written.
        incident: Relationship to the incident this postmortem covers.
        author: Relationship to the user who wrote it, if any.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str = Field(foreign_key="incident.id", unique=True, index=True)
    summary: str = Field(default="")
    root_cause_summary: str = Field(default="")
    timeline_summary: str = Field(default="")
    lessons_learned: str = Field(default="")
    action_items: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    written_by: Optional[int] = Field(default=None, foreign_key="user.id")
    written_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    incident: "Incident" = Relationship(back_populates="postmortem")
    author: Optional["User"] = Relationship()