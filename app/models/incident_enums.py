"""Shared enum types for the incident investigation domain model."""

from enum import Enum


class IncidentStatus(str, Enum):
    """Lifecycle status of an incident.

    Normal path:
        NEW -> INVESTIGATING -> DIAGNOSED -> AWAITING_APPROVAL
             -> REMEDIATING -> VERIFYING -> RESOLVED

    Failure path:
        INVESTIGATING -> UNRESOLVED
    """

    NEW = "new"
    INVESTIGATING = "investigating"
    DIAGNOSED = "diagnosed"
    AWAITING_APPROVAL = "awaiting_approval"
    REMEDIATING = "remediating"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class Severity(str, Enum):
    """Business impact severity of an incident."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceSource(str, Enum):
    """Where a piece of observed evidence came from.

    These are the telemetry categories the investigation graph will
    eventually collect from (Phase 3). Declaring the categories now is
    a domain-modeling concern; the actual ingestion integrations are
    out of scope for this step.
    """

    LOG = "log"
    METRIC = "metric"
    DEPLOYMENT_EVENT = "deployment_event"
    RUNBOOK = "runbook"


class HypothesisStatus(str, Enum):
    """Status of an AI-generated candidate root cause."""

    PROPOSED = "proposed"
    VALIDATED = "validated"
    REJECTED = "rejected"


class RemediationActionType(str, Enum):
    """The fixed, controlled set of actions the system may recommend.

    Deliberately closed: the model selects from this registry rather
    than generating free-form commands, so nothing here is ever
    LLM-authored shell execution.
    """

    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    RESTART_SERVICE = "restart_service"
    SCALE_SERVICE = "scale_service"
    SWITCH_FEATURE_FLAG = "switch_feature_flag"


class RiskLevel(str, Enum):
    """Risk classification used to decide whether human approval is required."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalStatus(str, Enum):
    """Status of a human approval request for a remediation."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NOT_REQUIRED = "not_required"


class ExecutionStatus(str, Enum):
    """Outcome status of a remediation action execution."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SIMULATED = "simulated"