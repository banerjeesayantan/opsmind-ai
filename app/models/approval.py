"""This file contains the Approval model - human sign-off on a recommended remediation."""

from datetime import datetime, UTC
from typing import (
    TYPE_CHECKING,
    Optional,
)

from sqlmodel import (
    Field,
    Relationship,
)

from app.models.base import BaseModel
from app.models.incident_enums import ApprovalStatus

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.remediation import Remediation
    from app.models.user import User


class Approval(BaseModel, table=True):
    """A human approval decision for a recommended remediation.

    High-risk remediations must not execute automatically - this row is the
    audit trail of who decided what, and when. A low-risk remediation that
    doesn't require a human in the loop still gets an Approval row with
    status NOT_REQUIRED, so the audit trail is complete for every
    remediation regardless of risk level rather than only existing for the
    ones that needed a human.

    Attributes:
        id: The primary key.
        incident_id: Foreign key to the parent incident.
        remediation_id: Foreign key to the remediation being decided on.
        status: Current state of the approval request.
        requested_at: When approval was requested (or, for NOT_REQUIRED,
            when that determination was made).
        decided_at: When a human made the approve/reject decision. Null
            while still pending.
        decided_by: Foreign key to the user who made the decision. Null
            while pending or when not required.
        reason: Optional rationale for the decision.
        incident: Relationship back to the parent incident.
        remediation: Relationship to the remediation being approved.
        decider: Relationship to the user who made the decision, if any.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str = Field(foreign_key="incident.id", index=True)
    remediation_id: int = Field(foreign_key="remediation.id")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING, index=True)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: Optional[datetime] = Field(default=None)
    decided_by: Optional[int] = Field(default=None, foreign_key="user.id")
    reason: Optional[str] = Field(default=None)

    incident: "Incident" = Relationship(back_populates="approvals")
    remediation: "Remediation" = Relationship(back_populates="approvals")
    decider: Optional["User"] = Relationship()