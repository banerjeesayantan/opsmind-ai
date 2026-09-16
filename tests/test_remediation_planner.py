"""Automated tests for the Remediation Planner node and its integration.

All LLM and telemetry dependencies are fake/stub-driven - no real Groq,
OpenAI, or telemetry calls are made anywhere in this file. Integration
tests against risk classification, persistence, and action execution use
the real modules (not mocks of them), with persistence backed by an
isolated in-memory SQLite engine, so the integration contract between
Phase 2 and Phases 3-5 is genuinely exercised rather than assumed.

Follows the existing convention: plain synchronous test functions driving
async code via asyncio.run(), no pytest-asyncio dependency.

Run with: pytest tests/test_remediation_planner.py -v
"""

import asyncio
from datetime import datetime, UTC

from sqlmodel import SQLModel, create_engine

import app.models.database  # noqa: F401 - force-import the full model registry
from app.investigation.action_executor import ControlledActionExecutor
from app.investigation.graph import build_investigation_graph
from app.investigation.nodes.evidence_collector import EvidenceCollectorNode
from app.investigation.nodes.evidence_validator import _ValidationVerdict
from app.investigation.nodes.hypothesis_generator import _HypothesisGenerationOutput, _RawHypothesis
from app.investigation.nodes.impact_analyzer import _ImpactVerdict
from app.investigation.nodes.remediation_planner import RemediationPlannerNode, _RawRemediation
from app.investigation.risk import classify_risk, requires_human_approval
from app.investigation.schemas import (
    DiagnosisResult,
    EvidenceCitation,
    HypothesisCandidate,
    InvestigationState,
)
from app.models.incident_enums import (
    ApprovalStatus,
    RemediationActionType,
    RiskLevel,
    Severity,
)
from app.services.persistence import IncidentPersistenceService
from app.telemetry import TimeWindow


class FakeStructuredLLM:
    """Stub matching the node's StructuredLLM protocol - no real LLM needed."""

    def __init__(self, response):
        self.response = response
        self.call_count = 0

    async def ainvoke(self, messages):
        self.call_count += 1
        return self.response


def _incident_window() -> TimeWindow:
    return TimeWindow(
        start=datetime(2026, 9, 6, 10, 0, tzinfo=UTC),
        end=datetime(2026, 9, 6, 10, 15, tzinfo=UTC),
    )


def _base_state(incident_id: str = "inc-remediation-test") -> InvestigationState:
    return InvestigationState(incident_id=incident_id, service="checkout", time_window=_incident_window())


async def _state_with_evidence_and_diagnosis(confidence: float = 0.8) -> InvestigationState:
    """A state that has real collected evidence plus a reached diagnosis.

    The diagnosis is backed by a matching validated hypothesis, mirroring
    what the real graph produces - persist_investigation_result only
    writes a Diagnosis row when its probable_cause traces back to a
    persisted Hypothesis, so a diagnosis with no hypothesis behind it
    would be silently dropped (correctly).
    """
    state = _base_state()
    state = state.model_copy(update=await EvidenceCollectorNode()(state))

    statement = "Deployment caused regression"
    citation = EvidenceCitation(
        source="deployment",
        content=state.evidence.deployments[0].change_summary,
        timestamp=state.evidence.deployments[0].timestamp,
    )
    hypothesis = HypothesisCandidate(
        statement=statement,
        reasoning="timing lines up",
        confidence=confidence,
        supporting_evidence=[citation],
    )
    validated = hypothesis.model_copy(update={"validated": True})
    diagnosis = DiagnosisResult(
        probable_cause=statement,
        confidence=confidence,
        supporting_evidence=[citation],
    )
    return state.model_copy(
        update={
            "hypotheses": [hypothesis],
            "validated_hypotheses": [validated],
            "diagnosis": diagnosis,
        }
    )


def _sqlite_persistence() -> IncidentPersistenceService:
    """An IncidentPersistenceService backed by an isolated in-memory SQLite engine."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return IncidentPersistenceService(engine=engine)


# --- Valid remediation generation ---------------------------------------------


def test_planner_produces_valid_remediation_candidate():
    async def run():
        state = await _state_with_evidence_and_diagnosis()
        real_deployment_id = state.evidence.deployments[0].deployment_id
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
                parameters={"deployment_id": real_deployment_id},
                rationale="rollback the bad deploy",
            )
        )
        return await RemediationPlannerNode(structured_llm=fake)(state)

    update = asyncio.run(run())
    assert update["remediation"] is not None
    assert update["remediation"].action_type == RemediationActionType.ROLLBACK_DEPLOYMENT
    assert update["remediation"].rationale == "rollback the bad deploy"


def test_planner_supports_all_four_action_types():
    """Every RemediationActionType must be producible, with its own
    required parameters - the planner is not silently limited to one."""

    cases = [
        (RemediationActionType.ROLLBACK_DEPLOYMENT, {"deployment_id": "dep-42"}),
        (RemediationActionType.RESTART_SERVICE, {"service": "checkout", "instance_count": 1}),
        (RemediationActionType.SCALE_SERVICE, {"service": "checkout", "target_replicas": 5, "direction": "up"}),
        (RemediationActionType.SWITCH_FEATURE_FLAG, {"flag_name": "new-checkout", "enabled": False}),
    ]

    async def run(action_type, parameters):
        state = await _state_with_evidence_and_diagnosis()
        fake = FakeStructuredLLM(_RawRemediation(action_type=action_type, parameters=parameters))
        return await RemediationPlannerNode(structured_llm=fake)(state)

    for action_type, parameters in cases:
        update = asyncio.run(run(action_type, parameters))
        assert update["remediation"] is not None, f"{action_type} should produce a candidate"
        assert update["remediation"].action_type == action_type


# --- Invalid parameters ---------------------------------------------------


def test_planner_rejects_missing_required_parameter():
    async def run():
        state = await _state_with_evidence_and_diagnosis()
        # SCALE_SERVICE requires 'service', 'target_replicas', AND 'direction'.
        fake = FakeStructuredLLM(
            _RawRemediation(action_type=RemediationActionType.SCALE_SERVICE, parameters={"service": "checkout"})
        )
        return await RemediationPlannerNode(structured_llm=fake)(state)

    update = asyncio.run(run())
    assert update["remediation"] is None


def test_planner_rejects_extra_unexpected_parameters():
    """extra="forbid" - an LLM adding fields beyond the action's schema
    is rejected outright rather than having them silently stripped."""

    async def run():
        state = await _state_with_evidence_and_diagnosis()
        real_deployment_id = state.evidence.deployments[0].deployment_id
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
                parameters={"deployment_id": real_deployment_id, "sudo": True},
            )
        )
        return await RemediationPlannerNode(structured_llm=fake)(state)

    update = asyncio.run(run())
    assert update["remediation"] is None


def test_planner_rejects_wrong_typed_parameter():
    async def run():
        state = await _state_with_evidence_and_diagnosis()
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.SCALE_SERVICE,
                # target_replicas=0 (scale-to-zero) is valid; negative is not.
                parameters={"service": "checkout", "target_replicas": -1, "direction": "down"},
            )
        )
        return await RemediationPlannerNode(structured_llm=fake)(state)

    update = asyncio.run(run())
    assert update["remediation"] is None


# --- Evidence grounding ---------------------------------------------------


def test_planner_rejects_hallucinated_deployment_id():
    """A deployment_id must correspond to a real deployment actually seen
    in evidence - never one the LLM invented."""

    async def run():
        state = await _state_with_evidence_and_diagnosis()
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
                parameters={"deployment_id": "dep-DOES-NOT-EXIST-999"},
            )
        )
        return await RemediationPlannerNode(structured_llm=fake)(state)

    update = asyncio.run(run())
    assert update["remediation"] is None


def test_planner_rejects_mismatched_service_name():
    async def run():
        state = await _state_with_evidence_and_diagnosis()
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.RESTART_SERVICE,
                parameters={"service": "some-other-service"},
            )
        )
        return await RemediationPlannerNode(structured_llm=fake)(state)

    update = asyncio.run(run())
    assert update["remediation"] is None


def test_planner_rejects_rollback_when_no_evidence_collected():
    """With no evidence at all there is nothing to ground a deployment_id
    against, so a rollback cannot be validated."""

    async def run():
        state = _base_state()
        diagnosis = DiagnosisResult(probable_cause="something", confidence=0.8)
        state = state.model_copy(update={"diagnosis": diagnosis})
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
                parameters={"deployment_id": "dep-42"},
            )
        )
        return await RemediationPlannerNode(structured_llm=fake)(state)

    update = asyncio.run(run())
    assert update["remediation"] is None


# --- Failure / empty result handling ----------------------------------------


def test_planner_precondition_raises_without_diagnosis():
    fake = FakeStructuredLLM(
        _RawRemediation(action_type=RemediationActionType.RESTART_SERVICE, parameters={"service": "checkout"})
    )

    async def run():
        await RemediationPlannerNode(structured_llm=fake)(_base_state())

    try:
        asyncio.run(run())
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_planner_zero_confidence_diagnosis_short_circuits_without_llm_call():
    """A zero-confidence diagnosis means nothing was actually confirmed,
    so there is nothing to remediate - and no LLM request is spent."""
    fake = FakeStructuredLLM(
        _RawRemediation(action_type=RemediationActionType.RESTART_SERVICE, parameters={"service": "checkout"})
    )

    async def run():
        state = await _state_with_evidence_and_diagnosis(confidence=0.0)
        result = await RemediationPlannerNode(structured_llm=fake)(state)
        return result, fake

    result, fake = asyncio.run(run())
    assert result["remediation"] is None
    assert fake.call_count == 0


# --- Integration: planner -> risk classification ------------------------------


def test_planner_output_feeds_risk_classification():
    """The planner's (action_type, parameters) output is exactly the shape
    app.investigation.risk.classify_risk expects - this is the real
    integration contract, tested against the real risk module."""

    async def run():
        state = await _state_with_evidence_and_diagnosis()
        real_deployment_id = state.evidence.deployments[0].deployment_id
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
                parameters={"deployment_id": real_deployment_id},
            )
        )
        return await RemediationPlannerNode(structured_llm=fake)(state)

    update = asyncio.run(run())
    candidate = update["remediation"]

    risk_level = classify_risk(candidate.action_type, candidate.parameters)
    # A production rollback is classified HIGH by risk.py's rules.
    assert risk_level == RiskLevel.HIGH
    assert requires_human_approval(risk_level) is True


def test_low_risk_planner_output_does_not_require_approval():
    """A restart of a single instance is LOW risk and auto-approved."""

    async def run():
        state = await _state_with_evidence_and_diagnosis()
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.RESTART_SERVICE,
                parameters={"service": "checkout", "instance_count": 1},
            )
        )
        return await RemediationPlannerNode(structured_llm=fake)(state)

    update = asyncio.run(run())
    candidate = update["remediation"]

    risk_level = classify_risk(candidate.action_type, candidate.parameters)
    assert risk_level == RiskLevel.LOW
    assert requires_human_approval(risk_level) is False


def test_restart_service_planner_output_feeds_risk_classification_correctly():
    """Regression guard for the fixed restart_service contract: the
    planner's 'instance_count' key must be the same key classify_risk and
    ControlledActionExecutor both read (previously the planner only ever
    emitted 'service', so instance_count-based risk tiering was silently
    unreachable - a fleet-wide restart was indistinguishable from a
    single-instance one)."""

    async def run(instance_count):
        state = await _state_with_evidence_and_diagnosis()
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.RESTART_SERVICE,
                parameters={"service": "checkout", "instance_count": instance_count},
            )
        )
        return await RemediationPlannerNode(structured_llm=fake)(state)

    single = asyncio.run(run(1))["remediation"]
    assert classify_risk(single.action_type, single.parameters) == RiskLevel.LOW

    fleet_wide = asyncio.run(run(5))["remediation"]
    assert classify_risk(fleet_wide.action_type, fleet_wide.parameters) == RiskLevel.MEDIUM


def test_restart_service_planner_output_executes_successfully():
    """A restart_service candidate from the planner must actually execute,
    not just classify correctly - guards the same contract from the
    execution side."""

    async def run():
        state = await _state_with_evidence_and_diagnosis()
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.RESTART_SERVICE,
                parameters={"service": "checkout", "instance_count": 3},
            )
        )
        update = await RemediationPlannerNode(structured_llm=fake)(state)
        candidate = update["remediation"]

        class _FakeRemediationRow:
            action_type = candidate.action_type
            parameters = candidate.parameters

        return await ControlledActionExecutor().execute(_FakeRemediationRow())

    result = asyncio.run(run())
    assert result.succeeded is True
    assert result.result["instances_restarted"] == 3


def test_scale_service_planner_output_feeds_risk_classification_correctly():
    """Regression guard for the fixed scale_service contract: the planner
    must emit 'target_replicas' (not 'replicas') and 'direction', the
    exact keys classify_risk reads - previously classify_risk always saw
    an empty dict for these keys and classified every scale_service
    recommendation LOW regardless of whether it was actually a risky
    scale-down or scale-to-zero."""

    async def run(target_replicas, direction):
        state = await _state_with_evidence_and_diagnosis()
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.SCALE_SERVICE,
                parameters={"service": "checkout", "target_replicas": target_replicas, "direction": direction},
            )
        )
        return await RemediationPlannerNode(structured_llm=fake)(state)

    scale_up = asyncio.run(run(10, "up"))["remediation"]
    assert classify_risk(scale_up.action_type, scale_up.parameters) == RiskLevel.LOW

    scale_down = asyncio.run(run(2, "down"))["remediation"]
    assert classify_risk(scale_down.action_type, scale_down.parameters) == RiskLevel.MEDIUM

    scale_to_zero = asyncio.run(run(0, "down"))["remediation"]
    assert classify_risk(scale_to_zero.action_type, scale_to_zero.parameters) == RiskLevel.HIGH


def test_scale_service_planner_output_executes_successfully():
    """Regression guard for the specific bug found during Phase 2/3
    integration: a scale_service candidate from the planner previously
    failed execution outright with "scale_service requires a
    'target_replicas' parameter" because the planner emitted 'replicas'
    while ControlledActionExecutor required 'target_replicas'. This must
    now succeed, including the scale-to-zero edge case."""

    async def run(target_replicas):
        state = await _state_with_evidence_and_diagnosis()
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.SCALE_SERVICE,
                parameters={"service": "checkout", "target_replicas": target_replicas, "direction": "down"},
            )
        )
        update = await RemediationPlannerNode(structured_llm=fake)(state)
        candidate = update["remediation"]

        class _FakeRemediationRow:
            action_type = candidate.action_type
            parameters = candidate.parameters

        return await ControlledActionExecutor().execute(_FakeRemediationRow())

    result = asyncio.run(run(2))
    assert result.succeeded is True
    assert result.result["target_replicas"] == 2

    # The scale-to-zero edge case specifically - must succeed (it's a
    # valid, if HIGH-risk, action), not be treated as "missing".
    zero_result = asyncio.run(run(0))
    assert zero_result.succeeded is True
    assert zero_result.result["target_replicas"] == 0


# --- Integration: planner -> persistence -> approval -> action ------------------


def test_planner_output_persists_and_creates_approval():
    """End-to-end against the real persistence service (isolated SQLite):
    a planner candidate becomes a Remediation row plus its Approval row."""

    async def run():
        persistence = _sqlite_persistence()
        state = await _state_with_evidence_and_diagnosis()
        real_deployment_id = state.evidence.deployments[0].deployment_id
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
                parameters={"deployment_id": real_deployment_id},
                rationale="rollback the bad deploy",
            )
        )
        state = state.model_copy(update=await RemediationPlannerNode(structured_llm=fake)(state))

        incident = await persistence.create_incident(title="Checkout latency")
        state = state.model_copy(update={"incident_id": incident.id})
        result = await persistence.persist_investigation_result(incident.id, state)

        candidate = state.remediation
        risk_level = classify_risk(candidate.action_type, candidate.parameters)
        remediation_row = await persistence.persist_remediation(
            incident_id=incident.id,
            diagnosis_id=result["diagnosis_id"],
            action_type=candidate.action_type,
            parameters=candidate.parameters,
            risk_level=risk_level,
            rationale=candidate.rationale,
        )
        approval = await persistence.create_approval_request(incident.id, remediation_row.id, risk_level)
        return remediation_row, approval

    remediation_row, approval = asyncio.run(run())
    assert remediation_row.action_type == RemediationActionType.ROLLBACK_DEPLOYMENT
    assert remediation_row.risk_level == RiskLevel.HIGH
    assert remediation_row.rationale == "rollback the bad deploy"
    # HIGH risk must require an explicit human decision.
    assert approval.status == ApprovalStatus.PENDING


def test_planner_output_executes_through_action_executor():
    """A persisted Remediation built from a planner candidate executes
    successfully through the real ControlledActionExecutor."""

    async def run():
        persistence = _sqlite_persistence()
        state = await _state_with_evidence_and_diagnosis()
        real_deployment_id = state.evidence.deployments[0].deployment_id
        fake = FakeStructuredLLM(
            _RawRemediation(
                action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
                parameters={"deployment_id": real_deployment_id},
            )
        )
        state = state.model_copy(update=await RemediationPlannerNode(structured_llm=fake)(state))

        incident = await persistence.create_incident(title="Checkout latency")
        state = state.model_copy(update={"incident_id": incident.id})
        result = await persistence.persist_investigation_result(incident.id, state)

        candidate = state.remediation
        remediation_row = await persistence.persist_remediation(
            incident_id=incident.id,
            diagnosis_id=result["diagnosis_id"],
            action_type=candidate.action_type,
            parameters=candidate.parameters,
            risk_level=classify_risk(candidate.action_type, candidate.parameters),
            rationale=candidate.rationale,
        )
        return await ControlledActionExecutor().execute(remediation_row)

    exec_result = asyncio.run(run())
    assert exec_result.succeeded is True
    assert exec_result.result["action"] == "rollback_deployment"
    assert exec_result.result["simulated"] is True


# --- Full graph integration -----------------------------------------------


def test_full_graph_includes_remediation_planner_after_diagnosis():
    graph = build_investigation_graph()
    node_names = set(graph.get_graph().nodes.keys())
    assert "remediation_planner" in node_names
    assert node_names == {
        "__start__",
        "evidence_collector",
        "timeline_builder",
        "hypothesis_generator",
        "evidence_validator",
        "impact_analyzer",
        "diagnosis",
        "remediation_planner",
        "__end__",
    }


def test_full_graph_run_produces_grounded_remediation():
    """The complete pipeline through to a recommended remediation, fully
    fake-driven - no real Groq/OpenAI/telemetry calls."""
    fake_hyp = FakeStructuredLLM(
        _HypothesisGenerationOutput(
            hypotheses=[
                _RawHypothesis(
                    statement="Deployment caused regression",
                    reasoning="timing lines up",
                    confidence=0.7,
                    supporting_evidence_indices=[1],
                )
            ]
        )
    )
    fake_val = FakeStructuredLLM(_ValidationVerdict(supported=True, adjusted_confidence=0.88))
    fake_imp = FakeStructuredLLM(_ImpactVerdict(description="latency degraded", severity=Severity.HIGH))
    fake_rem = FakeStructuredLLM(
        _RawRemediation(
            action_type=RemediationActionType.ROLLBACK_DEPLOYMENT,
            parameters={"deployment_id": "dep-42"},
            rationale="rollback the bad deploy",
        )
    )

    async def run():
        graph = build_investigation_graph(
            hypothesis_llm=fake_hyp,
            evidence_validator_llm=fake_val,
            impact_llm=fake_imp,
            remediation_llm=fake_rem,
        )
        return await graph.ainvoke(_base_state("inc-full-graph"))

    final = asyncio.run(run())
    assert final["diagnosis"].probable_cause == "Deployment caused regression"
    assert final["remediation"] is not None
    assert final["remediation"].action_type == RemediationActionType.ROLLBACK_DEPLOYMENT
    assert final["remediation"].parameters == {"deployment_id": "dep-42"}


def test_full_graph_result_reconstructs_into_investigation_state():
    """graph.ainvoke() returns a plain dict, not an InvestigationState -
    a caller passing it to persistence must reconstruct the pydantic
    object first. This documents that integration requirement so it
    can't silently regress."""
    fake_hyp = FakeStructuredLLM(
        _HypothesisGenerationOutput(
            hypotheses=[
                _RawHypothesis(statement="Deployment caused regression", confidence=0.7, supporting_evidence_indices=[1])
            ]
        )
    )
    fake_val = FakeStructuredLLM(_ValidationVerdict(supported=True, adjusted_confidence=0.88))
    fake_imp = FakeStructuredLLM(_ImpactVerdict(description="latency degraded", severity=Severity.HIGH))
    fake_rem = FakeStructuredLLM(
        _RawRemediation(
            action_type=RemediationActionType.ROLLBACK_DEPLOYMENT, parameters={"deployment_id": "dep-42"}
        )
    )

    async def run():
        graph = build_investigation_graph(
            hypothesis_llm=fake_hyp,
            evidence_validator_llm=fake_val,
            impact_llm=fake_imp,
            remediation_llm=fake_rem,
        )
        final_dict = await graph.ainvoke(_base_state("inc-reconstruct"))
        return final_dict, InvestigationState(**final_dict)

    final_dict, reconstructed = asyncio.run(run())
    assert isinstance(final_dict, dict)
    assert reconstructed.remediation is not None
    assert reconstructed.remediation.action_type == RemediationActionType.ROLLBACK_DEPLOYMENT