"""This file contains the Incident model - the root aggregate of the incident investigation domain."""

from datetime import datetime
from typing import (
    TYPE_CHECKING,
    List,
    Optional,
)
from uuid import uuid4

from sqlmodel import (
    Field,
    Relationship,
)

from app.models.base import BaseModel
from app.models.incident_enums import (
    IncidentStatus,
    Severity,
)

if TYPE_CHECKING:
    from app.models.action_execution import ActionExecution
    from app.models.approval import Approval
    from app.models.diagnosis import Diagnosis
    from app.models.evidence import Evidence
    from app.models.hypothesis import Hypothesis
    from app.models.incident_event import IncidentEvent
    from app.models.postmortem import Postmortem
    from app.models.remediation import Remediation
    from app.models.user import User
    from app.models.verification import Verification


class Incident(BaseModel, table=True):
    """The root aggregate for a single production incident under investigation.

    Attributes:
        id: The primary key (UUID string).
        title: Short human-readable summary of the incident.
        description: Longer free-text description of what was observed.
        severity: Business impact severity.
        status: Current position in the incident lifecycle state machine.
        created_by: Foreign key to the user who opened the incident (nullable -
            an incident may be opened by an automated alert with no human
            reporter yet attached).
        resolved_at: When the incident reached a terminal state
            (RESOLVED or UNRESOLVED). Null while still open.
        events: Timeline entries for this incident.
        evidence: Observed evidence collected during investigation.
        hypotheses: AI-generated candidate root causes.
        diagnoses: Validated diagnoses derived from hypotheses.
        remediations: Recommended remediation actions.
        approvals: Human approval decisions for remediations.
        action_executions: Records of remediation actions actually taken.
        verifications: Post-action verification checks.
        postmortem: The incident's postmortem, if one has been written.
    """

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    title: str = Field(index=True)
    description: str = Field(default="")
    severity: Severity = Field(default=Severity.MEDIUM, index=True)
    status: IncidentStatus = Field(default=IncidentStatus.NEW, index=True)
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    resolved_at: Optional[datetime] = Field(default=None)

    reporter: Optional["User"] = Relationship()
    events: List["IncidentEvent"] = Relationship(
        back_populates="incident",
        sa_relationship_kwargs={"order_by": "IncidentEvent.occurred_at"},
    )
    evidence: List["Evidence"] = Relationship(back_populates="incident")
    hypotheses: List["Hypothesis"] = Relationship(back_populates="incident")
    diagnoses: List["Diagnosis"] = Relationship(back_populates="incident")
    remediations: List["Remediation"] = Relationship(back_populates="incident")
    approvals: List["Approval"] = Relationship(back_populates="incident")
    action_executions: List["ActionExecution"] = Relationship(back_populates="incident")
    verifications: List["Verification"] = Relationship(back_populates="incident")
    postmortem: Optional["Postmortem"] = Relationship(back_populates="incident")