"""Deterministic risk classification for recommended remediation actions.

This is intentionally NOT an LLM call: risk classification is a safety-
critical gate that decides whether a human must sign off before a
remediation can execute, so it needs to be deterministic, auditable, and
regression-testable rather than subject to model variance. Given the same
action_type and parameters, classify_risk always returns the same
RiskLevel.

The function operates on the plain (action_type, parameters) shape that
app.models.remediation.Remediation already stores, rather than importing
a graph-transient "RemediationCandidate" schema - that keeps this module
decoupled from however the remediation_planner node happens to represent
a not-yet-persisted candidate internally.
"""

from app.models.incident_enums import (
    RemediationActionType,
    RiskLevel,
)

# Actions below this many affected instances/replicas are treated as
# narrow-blast-radius; at or above it, the action is treated as fleet-wide.
_FLEET_WIDE_THRESHOLD = 3

# A feature-flag rollout at or below this percentage is treated as a
# limited/canary exposure rather than a full rollout.
_CANARY_ROLLOUT_PERCENT = 10


def _is_production(parameters: dict, environment: str) -> bool:
    """Resolve the effective environment for a remediation.

    parameters["environment"], when present, takes precedence over the
    caller-supplied default (e.g. an Incident may be for a service that
    only exists in staging, even though the platform's default assumption
    is production).
    """
    return str(parameters.get("environment", environment)).lower() == "production"


def _classify_rollback_deployment(parameters: dict, environment: str) -> RiskLevel:
    """A rollback reverts a release for all traffic on the target service.

    HIGH in production - it changes what code every user is served,
    and if the previous version had its own problems, rolling back can
    itself cause a new incident. MEDIUM outside production, where the
    blast radius is limited to non-customer-facing traffic.
    """
    return RiskLevel.HIGH if _is_production(parameters, environment) else RiskLevel.MEDIUM


def _classify_restart_service(parameters: dict, environment: str) -> RiskLevel:
    """A restart is normally low-risk: it's reversible and commonly used.

    Escalated to MEDIUM if the restart targets the whole fleet at once
    (scope="all_instances", or an explicit instance_count at or above the
    fleet-wide threshold) rather than a single instance or a small subset,
    since restarting everything simultaneously can cause a brief full
    outage instead of a rolling one.
    """
    scope = str(parameters.get("scope", "single_instance")).lower()
    instance_count = int(parameters.get("instance_count", 1) or 1)

    if scope == "all_instances" or instance_count >= _FLEET_WIDE_THRESHOLD:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _classify_scale_service(parameters: dict, environment: str) -> RiskLevel:
    """Scaling up capacity is low-risk; scaling down can reduce it dangerously.

    - Scaling up (more replicas/capacity than before, or direction="up"):
      LOW - the failure mode is "spent a bit more money", not an outage.
    - Scaling down to zero replicas: HIGH - this takes the service
      offline entirely.
    - Any other scale-down: MEDIUM - reduces capacity while an incident
      is in progress, which needs a human to confirm it's safe.
    """
    direction = str(parameters.get("direction", "")).lower()
    target_replicas = parameters.get("target_replicas")

    if target_replicas is not None and int(target_replicas) <= 0:
        return RiskLevel.HIGH
    if direction == "down":
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _classify_switch_feature_flag(parameters: dict, environment: str) -> RiskLevel:
    """Flag risk scales with exposure: a canary rollout is safer than a full one.

    - Disabling a flag (turning a feature off) is treated as LOW: it's the
      standard "turn off the thing that's misbehaving" action.
    - Enabling a flag at or below the canary rollout threshold: LOW.
    - Enabling a flag above the canary threshold (including 100%) in
      production: MEDIUM - it changes behavior for a large or complete
      slice of production users.
    - Enabling a flag above the canary threshold outside production: LOW.
    """
    enabled = bool(parameters.get("enabled", True))
    rollout_percent = int(parameters.get("rollout_percent", 100))

    if not enabled:
        return RiskLevel.LOW
    if rollout_percent <= _CANARY_ROLLOUT_PERCENT:
        return RiskLevel.LOW
    return RiskLevel.MEDIUM if _is_production(parameters, environment) else RiskLevel.LOW


_CLASSIFIERS = {
    RemediationActionType.ROLLBACK_DEPLOYMENT: _classify_rollback_deployment,
    RemediationActionType.RESTART_SERVICE: _classify_restart_service,
    RemediationActionType.SCALE_SERVICE: _classify_scale_service,
    RemediationActionType.SWITCH_FEATURE_FLAG: _classify_switch_feature_flag,
}


def classify_risk(
    action_type: RemediationActionType,
    parameters: dict,
    *,
    environment: str = "production",
) -> RiskLevel:
    """Classify the risk level of a recommended remediation action.

    Deterministic and side-effect free: the same inputs always produce the
    same RiskLevel, which is what makes this safe to regression-test and
    to run as a gate ahead of every approval request rather than trusting
    an LLM's judgment call on something this consequential.

    Args:
        action_type: Which controlled action is being classified. Must be
            one of the four RemediationActionType values - there is no
            free-form action type by design (see Remediation model).
        parameters: The parameters recommended for this action (e.g.
            {"deployment_id": "v42"} for a rollback). Never trusted for
            anything beyond the specific keys each classifier reads.
        environment: Default environment assumption if parameters doesn't
            specify one. Defaults to "production" - the conservative
            choice when the environment is unknown.

    Returns:
        RiskLevel: LOW, MEDIUM, or HIGH.

    Raises:
        ValueError: If action_type is not a recognized RemediationActionType.
    """
    classifier = _CLASSIFIERS.get(action_type)
    if classifier is None:
        raise ValueError(f"Unrecognized action_type for risk classification: {action_type!r}")
    return classifier(parameters or {}, environment)


def requires_human_approval(risk_level: RiskLevel) -> bool:
    """Whether a remediation at this risk level must wait for a human decision.

    LOW-risk remediations are auto-approved (Approval.status =
    NOT_REQUIRED) so routine, low-blast-radius actions aren't held up by a
    human in the loop. MEDIUM and HIGH always require an explicit human
    approve/reject decision before an ActionExecution may proceed.

    Args:
        risk_level: The classified risk level of the remediation.

    Returns:
        bool: True if a human approval decision is required.
    """
    return risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)
