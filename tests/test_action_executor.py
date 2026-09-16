"""Tests for app.investigation.action_executor.ControlledActionExecutor.

Plain sync pytest functions driving the async execute() via asyncio.run(),
per the project's testing convention (see tests/test_telemetry.py).

Run with: pytest tests/test_action_executor.py -v
"""

import asyncio

import pytest

from app.investigation.action_executor import ControlledActionExecutor
from app.models.incident_enums import RemediationActionType
from app.models.remediation import Remediation


def _remediation(action_type: RemediationActionType, parameters: dict) -> Remediation:
    """Build an in-memory (unpersisted) Remediation row for executor tests."""
    return Remediation(
        incident_id="incident-1",
        diagnosis_id=1,
        action_type=action_type,
        parameters=parameters,
    )


# --- rollback_deployment ------------------------------------------------------


def test_rollback_deployment_succeeds_with_deployment_id():
    executor = ControlledActionExecutor()
    remediation = _remediation(RemediationActionType.ROLLBACK_DEPLOYMENT, {"deployment_id": "dep-41"})

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is True
    assert result.result["action"] == "rollback_deployment"
    assert result.result["rolled_back_to"] == "dep-41"
    assert result.result["simulated"] is True


def test_rollback_deployment_fails_without_deployment_id():
    executor = ControlledActionExecutor()
    remediation = _remediation(RemediationActionType.ROLLBACK_DEPLOYMENT, {})

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is False
    assert "deployment_id" in result.error_message


# --- restart_service -----------------------------------------------------------


def test_restart_service_defaults_to_single_instance():
    executor = ControlledActionExecutor()
    remediation = _remediation(RemediationActionType.RESTART_SERVICE, {})

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is True
    assert result.result["instances_restarted"] == 1
    assert result.result["scope"] == "single_instance"


def test_restart_service_respects_explicit_instance_count():
    executor = ControlledActionExecutor()
    remediation = _remediation(
        RemediationActionType.RESTART_SERVICE, {"instance_count": 4, "scope": "all_instances"}
    )

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is True
    assert result.result["instances_restarted"] == 4
    assert result.result["scope"] == "all_instances"


def test_restart_service_fails_with_non_numeric_instance_count():
    executor = ControlledActionExecutor()
    remediation = _remediation(RemediationActionType.RESTART_SERVICE, {"instance_count": "all-of-them"})

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is False


def test_restart_service_fails_with_zero_instance_count():
    executor = ControlledActionExecutor()
    remediation = _remediation(RemediationActionType.RESTART_SERVICE, {"instance_count": 0})

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is False


# --- scale_service ---------------------------------------------------------------


def test_scale_service_succeeds_with_target_replicas():
    executor = ControlledActionExecutor()
    remediation = _remediation(
        RemediationActionType.SCALE_SERVICE, {"target_replicas": 6, "direction": "up"}
    )

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is True
    assert result.result["target_replicas"] == 6
    assert result.result["direction"] == "up"


def test_scale_service_allows_scale_to_zero():
    executor = ControlledActionExecutor()
    remediation = _remediation(RemediationActionType.SCALE_SERVICE, {"target_replicas": 0})

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is True
    assert result.result["target_replicas"] == 0


def test_scale_service_fails_without_target_replicas():
    executor = ControlledActionExecutor()
    remediation = _remediation(RemediationActionType.SCALE_SERVICE, {})

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is False


def test_scale_service_fails_with_negative_target_replicas():
    executor = ControlledActionExecutor()
    remediation = _remediation(RemediationActionType.SCALE_SERVICE, {"target_replicas": -1})

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is False


# --- switch_feature_flag -------------------------------------------------------------


def test_switch_feature_flag_succeeds_with_flag_name():
    executor = ControlledActionExecutor()
    remediation = _remediation(
        RemediationActionType.SWITCH_FEATURE_FLAG,
        {"flag_name": "new_checkout_flow", "enabled": False},
    )

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is True
    assert result.result["flag_name"] == "new_checkout_flow"
    assert result.result["enabled"] is False


def test_switch_feature_flag_fails_without_flag_name():
    executor = ControlledActionExecutor()
    remediation = _remediation(RemediationActionType.SWITCH_FEATURE_FLAG, {})

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is False


# --- all branches covered, deterministic ----------------------------------------------


@pytest.mark.parametrize(
    "action_type,parameters",
    [
        (RemediationActionType.ROLLBACK_DEPLOYMENT, {"deployment_id": "dep-1"}),
        (RemediationActionType.RESTART_SERVICE, {}),
        (RemediationActionType.SCALE_SERVICE, {"target_replicas": 3}),
        (RemediationActionType.SWITCH_FEATURE_FLAG, {"flag_name": "x"}),
    ],
)
def test_every_action_type_is_handled_and_marked_simulated(action_type, parameters):
    executor = ControlledActionExecutor()
    remediation = _remediation(action_type, parameters)

    result = asyncio.run(executor.execute(remediation))

    assert result.succeeded is True
    assert result.result["simulated"] is True
