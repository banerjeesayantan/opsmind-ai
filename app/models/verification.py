"""This file contains the Verification model - the post-action check for whether an incident recovered."""

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
    from app.models.action_execution import ActionExecution
    from app.models.incident import Incident


class Verification(BaseModel, table=True):
    """A post-action check for whether a remediation actually resolved the incident.

    An agent is not considered successful merely because it recommended and
    executed an action - this row is where fresh telemetry is compared
    against the pre-incident baseline to determine whether the incident is
    actually over. If recovered is False, the incident returns to
    investigation rather than being marked resolved on the strength of the
    action alone.

    Attributes:
        id: The primary key.
        incident_id: Foreign key to the parent incident.
        action_execution_id: Foreign key to the action execution being
            verified.
        checked_at: When this verification check was performed.
        recovered: Whether fresh telemetry showed the incident had
            resolved. Null while the check has not yet been made.
        evidence_after_ids: IDs of the fresh Evidence rows collected during
            verification, following the same evidence-reference pattern
            used by Hypothesis rather than duplicating evidence content.
        notes: Free-text notes on what was observed during verification.
        incident: Relationship back to the parent incident.
        action_execution: Relationship to the execution being verified.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str = Field(foreign_key="incident.id", index=True)
    action_execution_id: int = Field(foreign_key="actionexecution.id")
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    recovered: Optional[bool] = Field(default=None, index=True)
    evidence_after_ids: List[int] = Field(default_factory=list, sa_column=Column(JSON))
    notes: Optional[str] = Field(default=None)

    incident: "Incident" = Relationship(back_populates="verifications")
    action_execution: "ActionExecution" = Relationship(back_populates="verifications")