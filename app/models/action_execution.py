"""This file contains the ActionExecution model - a record of a remediation actually being run."""

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
from app.models.incident_enums import ExecutionStatus

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.remediation import Remediation
    from app.models.verification import Verification


class ActionExecution(BaseModel, table=True):
    """A record of a remediation action actually being executed.

    This is separate from Remediation (the recommendation) and Approval
    (the sign-off) because a single approved remediation could in principle
    be executed, fail, and be retried - each attempt gets its own row here
    rather than overwriting the last attempt's outcome.

    For a $0/local portfolio deployment, actions are simulated
    (status=SIMULATED) rather than actually calling a real orchestrator -
    the schema doesn't distinguish that at the type level so a real adapter
    can be plugged in later without a migration.

    Attributes:
        id: The primary key.
        incident_id: Foreign key to the parent incident.
        remediation_id: Foreign key to the remediation this execution
            attempts to carry out.
        status: Outcome of this execution attempt.
        executed_at: When this execution attempt was made.
        result: Structured result payload from the execution (or the
            simulated outcome), when available.
        error_message: Error details if status is FAILED.
        incident: Relationship back to the parent incident.
        remediation: Relationship to the remediation being executed.
        verifications: Post-execution checks for whether this action
            actually resolved the incident.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str = Field(foreign_key="incident.id", index=True)
    remediation_id: int = Field(foreign_key="remediation.id")
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING, index=True)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    result: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    error_message: Optional[str] = Field(default=None)

    incident: "Incident" = Relationship(back_populates="action_executions")
    remediation: "Remediation" = Relationship(back_populates="action_executions")
    verifications: List["Verification"] = Relationship(back_populates="action_execution")