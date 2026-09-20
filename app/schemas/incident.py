"""Request/response schemas for the incident investigation/response API.

Kept separate from app.investigation.schemas (the LangGraph's internal,
transient state) and from app.models.* (the DB rows) - this module is the
API's own contract, free to reshape either of those for a cleaner HTTP
surface without coupling the graph or the database schema to whatever a
client needs.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.incident_enums import (
    ApprovalStatus,
    EvidenceSource,
    ExecutionStatus,
    HypothesisStatus,
    IncidentStatus,
    RemediationActionType,
    RiskLevel,
    Severity,
)


class IncidentCreateRequest(BaseModel):
    """Request body for POST /incidents."""

    title: str = Field(..., min_length=1, description="Short human-readable summary of the incident.")
    description: str = Field(default="", description="Longer free-text description of what was observed.")
    severity: Severity = Field(default=Severity.MEDIUM, description="Initial business impact severity.")
    service: str = Field(..., min_length=1, description="Name of the service this incident is about.")


class IncidentResponse(BaseModel):
    """A single incident, as returned by the API."""

    id: str
    title: str
    description: str
    severity: Severity
    status: IncidentStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None


class InvestigateRequest(BaseModel):
    """Request body for POST /incidents/{id}/investigate.

    The investigation graph needs a service name and a time window to
    collect telemetry for - these aren't stored on Incident itself (an
    incident may span services, or the window may be refined between
    investigation runs), so they're supplied per investigation request.
    """

    service: str = Field(..., min_length=1, description="Name of the service to collect telemetry for.")
    window_start: datetime = Field(..., description="Start of the time window to investigate (inclusive).")
    window_end: datetime = Field(..., description="End of the time window to investigate (inclusive).")


class InvestigateResponse(BaseModel):
    """Result of running the investigation graph against an incident."""

    incident_id: str
    status: IncidentStatus
    evidence_count: int
    hypothesis_count: int
    diagnosis_id: Optional[int] = None
    probable_cause: Optional[str] = None
    confidence: Optional[float] = None
    remediation_id: Optional[int] = Field(
        default=None,
        description="Set when the graph's remediation_planner node reached a grounded recommendation and it was "
        "persisted with its approval request - None if no diagnosis was reached, or the planner's proposal "
        "failed validation/grounding.",
    )
    risk_level: Optional[RiskLevel] = None


class EvidenceResponse(BaseModel):
    """A single piece of raw, observed evidence collected during investigation."""

    id: int
    source: EvidenceSource
    source_reference: Optional[str] = None
    content: str
    raw_data: Optional[dict] = None
    occurred_at: datetime
    collected_at: datetime


class HypothesisResponse(BaseModel):
    """A single persisted hypothesis."""

    id: int
    statement: str
    reasoning: Optional[str] = None
    confidence: float
    status: HypothesisStatus
    supporting_evidence_ids: list[int]


class DiagnosisResponse(BaseModel):
    """The active diagnosis for an incident, if one has been reached."""

    id: int
    hypothesis_id: int
    probable_cause: str
    confidence: float
    impact: str
    diagnosed_at: datetime


class RemediationResponse(BaseModel):
    """A single recommended remediation."""

    id: int
    diagnosis_id: int
    action_type: RemediationActionType
    parameters: dict
    risk_level: RiskLevel
    rationale: str
    is_selected: bool
    recommended_at: datetime


class ApprovalResponse(BaseModel):
    """A single approval request/decision."""

    id: int
    remediation_id: int
    status: ApprovalStatus
    requested_at: datetime
    decided_at: Optional[datetime] = None
    decided_by: Optional[int] = None
    reason: Optional[str] = None


class ActionExecutionResponse(BaseModel):
    """A single remediation action execution attempt."""

    id: int
    remediation_id: int
    status: ExecutionStatus
    executed_at: datetime
    result: Optional[dict] = None
    error_message: Optional[str] = None


class VerificationResponse(BaseModel):
    """A single post-action verification check."""

    id: int
    action_execution_id: int
    checked_at: datetime
    recovered: Optional[bool] = None
    notes: Optional[str] = None


class IncidentResultsResponse(BaseModel):
    """The full investigation/response picture for a single incident."""

    incident: IncidentResponse
    hypotheses: list[HypothesisResponse]
    diagnosis: Optional[DiagnosisResponse] = None
    remediations: list[RemediationResponse]
    approvals: list[ApprovalResponse]
    action_executions: list[ActionExecutionResponse]
    verifications: list[VerificationResponse]


class TimelineEntryResponse(BaseModel):
    """A single append-only timeline entry."""

    id: int
    event_type: str
    description: str
    occurred_at: datetime
    event_metadata: Optional[dict] = None


class RemediationCreateRequest(BaseModel):
    """Request body for POST /incidents/{id}/remediations.

    Lets the demo/API recommend a remediation directly against a
    diagnosis, independent of whichever process (an LLM planner node, or
    a human operator) decided on it - classify_risk is always applied
    server-side, never trusted from the client, so risk_level is
    computed here rather than accepted as input.
    """

    diagnosis_id: int = Field(..., description="The diagnosis this remediation addresses.")
    action_type: RemediationActionType
    parameters: dict = Field(default_factory=dict)
    rationale: str = Field(default="")
    environment: str = Field(default="production", description="Used by risk classification if parameters omit it.")


class ApprovalDecisionRequest(BaseModel):
    """Request body for POST /incidents/{id}/approvals/{approval_id}/decision.

    decided_by is deliberately not a field here: the deciding user is
    always taken from the authenticated caller's JWT (see
    app.api.v1.incidents.decide_approval), never accepted from the
    client, so a caller can't attribute a decision to someone else.
    """

    approved: bool
    reason: Optional[str] = None


class VerifyRequest(BaseModel):
    """Request body for POST /incidents/{id}/executions/{execution_id}/verify.

    after_window defaults to "now, plus a short lookahead" server-side if
    omitted - the caller usually just wants "check now", not to hand-pick
    a window.
    """

    after_window_start: Optional[datetime] = None
    after_window_end: Optional[datetime] = None


    