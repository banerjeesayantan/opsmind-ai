"""Tests for app.investigation.risk - deterministic remediation risk classification.

Plain sync pytest functions, no async needed since classify_risk is pure
and synchronous.

Run with: pytest tests/test_risk.py -v
"""

import pytest

from app.investigation.risk import (
    classify_risk,
    requires_human_approval,
)
from app.models.incident_enums import (
    RemediationActionType,
    RiskLevel,
)

# --- rollback_deployment -----------------------------------------------------


def test_rollback_deployment_in_production_is_high_risk():
    risk = classify_risk(RemediationActionType.ROLLBACK_DEPLOYMENT, {"deployment_id": "v41"})
    assert risk == RiskLevel.HIGH


def test_rollback_deployment_in_staging_is_medium_risk():
    risk = classify_risk(
        RemediationActionType.ROLLBACK_DEPLOYMENT,
        {"deployment_id": "v41", "environment": "staging"},
    )
    assert risk == RiskLevel.MEDIUM


# --- restart_service ----------------------------------------------------------


def test_restart_single_instance_is_low_risk():
    risk = classify_risk(RemediationActionType.RESTART_SERVICE, {"instance_count": 1})
    assert risk == RiskLevel.LOW


def test_restart_service_defaults_to_low_risk_with_no_parameters():
    risk = classify_risk(RemediationActionType.RESTART_SERVICE, {})
    assert risk == RiskLevel.LOW


def test_restart_all_instances_is_medium_risk():
    risk = classify_risk(RemediationActionType.RESTART_SERVICE, {"scope": "all_instances"})
    assert risk == RiskLevel.MEDIUM


def test_restart_large_instance_count_is_medium_risk():
    risk = classify_risk(RemediationActionType.RESTART_SERVICE, {"instance_count": 5})
    assert risk == RiskLevel.MEDIUM


# --- scale_service -------------------------------------------------------------


def test_scale_up_is_low_risk():
    risk = classify_risk(RemediationActionType.SCALE_SERVICE, {"direction": "up", "target_replicas": 10})
    assert risk == RiskLevel.LOW


def test_scale_down_is_medium_risk():
    risk = classify_risk(RemediationActionType.SCALE_SERVICE, {"direction": "down", "target_replicas": 2})
    assert risk == RiskLevel.MEDIUM


def test_scale_down_to_zero_is_high_risk():
    risk = classify_risk(RemediationActionType.SCALE_SERVICE, {"direction": "down", "target_replicas": 0})
    assert risk == RiskLevel.HIGH


# --- switch_feature_flag -------------------------------------------------------


def test_disabling_a_flag_is_low_risk():
    risk = classify_risk(RemediationActionType.SWITCH_FEATURE_FLAG, {"enabled": False})
    assert risk == RiskLevel.LOW


def test_enabling_a_flag_as_a_canary_rollout_is_low_risk():
    risk = classify_risk(
        RemediationActionType.SWITCH_FEATURE_FLAG,
        {"enabled": True, "rollout_percent": 5},
    )
    assert risk == RiskLevel.LOW


def test_enabling_a_flag_fully_in_production_is_medium_risk():
    risk = classify_risk(
        RemediationActionType.SWITCH_FEATURE_FLAG,
        {"enabled": True, "rollout_percent": 100},
    )
    assert risk == RiskLevel.MEDIUM


def test_enabling_a_flag_fully_outside_production_is_low_risk():
    risk = classify_risk(
        RemediationActionType.SWITCH_FEATURE_FLAG,
        {"enabled": True, "rollout_percent": 100, "environment": "staging"},
    )
    assert risk == RiskLevel.LOW


# --- determinism & error handling ----------------------------------------------


def test_classify_risk_is_deterministic():
    params = {"scope": "all_instances"}
    results = {classify_risk(RemediationActionType.RESTART_SERVICE, params) for _ in range(10)}
    assert results == {RiskLevel.MEDIUM}


def test_classify_risk_rejects_unrecognized_action_type():
    with pytest.raises(ValueError):
        classify_risk("not_a_real_action", {})


# --- requires_human_approval ----------------------------------------------------


def test_low_risk_does_not_require_approval():
    assert requires_human_approval(RiskLevel.LOW) is False


@pytest.mark.parametrize("level", [RiskLevel.MEDIUM, RiskLevel.HIGH])
def test_medium_and_high_risk_require_approval(level):
    assert requires_human_approval(level) is True
