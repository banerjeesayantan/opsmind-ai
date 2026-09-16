"""Controlled action execution - simulated, for the $0/local deployment.

Executes a Remediation's recommended action. For a $0/local portfolio
deployment there is no real orchestrator to call (no Kubernetes, no cloud
deployment API), so every branch here is SIMULATED rather than
SUCCEEDED/FAILED against a live system - this mirrors exactly what
app.models.action_execution.ActionExecution's docstring describes: "the
schema doesn't distinguish that at the type level so a real adapter can
be plugged in later without a migration."

Each of the four RemediationActionType branches is handled explicitly
(never a generic fallback), and each validates its own required
parameters before "running" anything - a remediation with malformed or
missing parameters fails validation rather than silently no-op'ing.
"""

from datetime import datetime, UTC
from typing import Protocol

from app.models.incident_enums import RemediationActionType
from app.models.remediation import Remediation


class ActionExecutionResult:
    """The outcome of attempting to execute a remediation's action.

    Attributes:
        succeeded: Whether the (simulated) execution completed without
            a parameter-validation error.
        result: Structured payload describing what the simulated
            execution "did" - shape depends on action_type.
        error_message: Populated only when succeeded is False.
    """

    def __init__(self, succeeded: bool, result: dict, error_message: str = ""):
        """Initialize the result of one execution attempt."""
        self.succeeded = succeeded
        self.result = result
        self.error_message = error_message


class ActionBackend(Protocol):
    """The interface a real (non-simulated) execution backend would implement.

    Not used by the $0/local ControlledActionExecutor today - documented
    here so a future real adapter (a Kubernetes client, a deployment
    API, a feature-flag service's API) has a concrete contract to
    implement, matching the "simulate now, plug in a real adapter later
    with no migration" design already reflected in the ActionExecution
    model.
    """

    async def rollback_deployment(self, parameters: dict) -> dict:
        """Roll back the target service to a previous deployment."""
        ...

    async def restart_service(self, parameters: dict) -> dict:
        """Restart one or more instances of the target service."""
        ...

    async def scale_service(self, parameters: dict) -> dict:
        """Scale the target service to a given replica count."""
        ...

    async def switch_feature_flag(self, parameters: dict) -> dict:
        """Enable or disable a feature flag."""
        ...


class ControlledActionExecutor:
    """Simulates executing a Remediation's recommended action.

    Deliberately closed over the same four RemediationActionType values
    as the Remediation model - there is no generic "run arbitrary
    parameters" path, so nothing here can execute an action outside the
    fixed, reviewed registry.
    """

    async def execute(self, remediation: Remediation) -> ActionExecutionResult:
        """Execute (simulate) a remediation's recommended action.

        Args:
            remediation: The remediation to execute. Its action_type
                selects which of the four branches runs; its parameters
                are validated by that branch before anything is
                "performed".

        Returns:
            ActionExecutionResult: Whether the simulated execution
            succeeded, and a structured result/error payload.
        """
        handler = {
            RemediationActionType.ROLLBACK_DEPLOYMENT: self._rollback_deployment,
            RemediationActionType.RESTART_SERVICE: self._restart_service,
            RemediationActionType.SCALE_SERVICE: self._scale_service,
            RemediationActionType.SWITCH_FEATURE_FLAG: self._switch_feature_flag,
        }.get(remediation.action_type)

        if handler is None:
            return ActionExecutionResult(
                succeeded=False,
                result={},
                error_message=f"Unrecognized action_type: {remediation.action_type!r}",
            )

        return handler(remediation.parameters or {})

    @staticmethod
    def _simulated_at() -> str:
        return datetime.now(UTC).isoformat()

    def _rollback_deployment(self, parameters: dict) -> ActionExecutionResult:
        """Simulate rolling back to a previous deployment.

        Requires parameters["deployment_id"] - the deployment being
        rolled back *to*. Without it there's nothing concrete to roll
        back to, so this fails validation rather than guessing.
        """
        deployment_id = parameters.get("deployment_id")
        if not deployment_id:
            return ActionExecutionResult(
                succeeded=False,
                result={},
                error_message="rollback_deployment requires a 'deployment_id' parameter.",
            )

        return ActionExecutionResult(
            succeeded=True,
            result={
                "action": "rollback_deployment",
                "rolled_back_to": deployment_id,
                "simulated": True,
                "simulated_at": self._simulated_at(),
            },
        )

    def _restart_service(self, parameters: dict) -> ActionExecutionResult:
        """Simulate restarting one or more instances of the service.

        instance_count defaults to 1 (a single-instance restart) if not
        given - a restart with no scope specified is still a well-formed,
        low-risk action, unlike a rollback with no target.
        """
        instance_count = parameters.get("instance_count", 1)
        try:
            instance_count = int(instance_count)
        except (TypeError, ValueError):
            return ActionExecutionResult(
                succeeded=False,
                result={},
                error_message=f"restart_service requires a numeric 'instance_count', got {instance_count!r}.",
            )
        if instance_count < 1:
            return ActionExecutionResult(
                succeeded=False,
                result={},
                error_message="restart_service requires 'instance_count' to be at least 1.",
            )

        return ActionExecutionResult(
            succeeded=True,
            result={
                "action": "restart_service",
                "instances_restarted": instance_count,
                "scope": parameters.get("scope", "single_instance"),
                "simulated": True,
                "simulated_at": self._simulated_at(),
            },
        )

    def _scale_service(self, parameters: dict) -> ActionExecutionResult:
        """Simulate scaling the service to a target replica count.

        Requires parameters["target_replicas"] - scaling with no target
        is not a well-formed action. Negative replica counts are
        rejected outright (zero is allowed - that's a deliberate scale-
        to-zero, already flagged HIGH risk by classify_risk upstream).
        """
        target_replicas = parameters.get("target_replicas")
        if target_replicas is None:
            return ActionExecutionResult(
                succeeded=False,
                result={},
                error_message="scale_service requires a 'target_replicas' parameter.",
            )
        try:
            target_replicas = int(target_replicas)
        except (TypeError, ValueError):
            return ActionExecutionResult(
                succeeded=False,
                result={},
                error_message=f"scale_service requires a numeric 'target_replicas', got {target_replicas!r}.",
            )
        if target_replicas < 0:
            return ActionExecutionResult(
                succeeded=False,
                result={},
                error_message="scale_service requires 'target_replicas' to be non-negative.",
            )

        return ActionExecutionResult(
            succeeded=True,
            result={
                "action": "scale_service",
                "target_replicas": target_replicas,
                "direction": parameters.get("direction", "unspecified"),
                "simulated": True,
                "simulated_at": self._simulated_at(),
            },
        )

    def _switch_feature_flag(self, parameters: dict) -> ActionExecutionResult:
        """Simulate enabling or disabling a feature flag.

        Requires parameters["flag_name"] - a flag toggle with no named
        flag has nothing to act on. "enabled" defaults to False (the
        conservative default: turning something off) if not given.
        """
        flag_name = parameters.get("flag_name")
        if not flag_name:
            return ActionExecutionResult(
                succeeded=False,
                result={},
                error_message="switch_feature_flag requires a 'flag_name' parameter.",
            )

        return ActionExecutionResult(
            succeeded=True,
            result={
                "action": "switch_feature_flag",
                "flag_name": flag_name,
                "enabled": bool(parameters.get("enabled", False)),
                "rollout_percent": parameters.get("rollout_percent", 100),
                "simulated": True,
                "simulated_at": self._simulated_at(),
            },
        )
