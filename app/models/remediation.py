"""This file contains the Remediation model - a recommended, controlled corrective action."""

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
from app.models.incident_enums import (
    RemediationActionType,
    RiskLevel,
)

if TYPE_CHECKING:
    from app.models.action_execution import ActionExecution
    from app.models.approval import Approval
    from app.models.diagnosis import Diagnosis
    from app.models.incident import Incident


class Remediation(BaseModel, table=True):
    """A recommended corrective action for a diagnosed incident.

    The action_type is always one of the fixed RemediationActionType values
    - the model selects from this closed registry and supplies parameters
    for it, rather than generating a free-form command. Application code is
    responsible for validating those parameters before anything is ever
    executed; this row only records what was recommended and why, not
    permission to run it.

    An incident's diagnosis may end up with more than one remediation
    recommended over its lifetime (e.g. a first suggestion is rejected in
    approval and a different one is proposed); is_selected marks the one
    currently in play.

    Attributes:
        id: The primary key.
        incident_id: Foreign key to the parent incident.
        diagnosis_id: Foreign key to the diagnosis this remediation
            addresses.
        action_type: Which controlled action is being recommended.
        parameters: The parameters the model produced for this action
            (e.g. {"deployment_id": "v42"} for a rollback). Validated by
            application code before execution, never trusted as-is.
        risk_level: Risk classification used to decide whether human
            approval is required before this can be executed.
        rationale: Why this action was recommended, in plain language.
        is_selected: Whether this is the remediation currently being
            pursued for the incident. False if superseded.
        recommended_at: When this remediation was recommended.
        incident: Relationship back to the parent incident.
        diagnosis: Relationship to the diagnosis being addressed.
        approvals: Human approval decisions for this remediation.
        action_executions: Records of this remediation actually being run.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str = Field(foreign_key="incident.id", index=True)
    diagnosis_id: int = Field(foreign_key="diagnosis.id")
    action_type: RemediationActionType = Field(index=True)
    parameters: dict = Field(default_factory=dict, sa_column=Column(JSON))
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM, index=True)
    rationale: str = Field(default="")
    is_selected: bool = Field(default=True, index=True)
    recommended_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    incident: "Incident" = Relationship(back_populates="remediations")
    diagnosis: "Diagnosis" = Relationship(back_populates="remediations")
    approvals: List["Approval"] = Relationship(back_populates="remediation")
    action_executions: List["ActionExecution"] = Relationship(back_populates="remediation")
