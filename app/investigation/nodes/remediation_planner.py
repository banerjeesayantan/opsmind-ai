"""Remediation planning node for the incident investigation graph."""

from typing import Optional, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.investigation.schemas import InvestigationState, RemediationCandidate
from app.models.incident_enums import RemediationActionType
from app.services.llm import LLMRegistry

_SYSTEM_PROMPT = """You are recommending a remediation action for a diagnosed production incident on the service "{service}".

You may choose exactly ONE action from this fixed list - never invent a
different action:
- rollback_deployment: requires parameter "deployment_id" (string)
- restart_service: requires parameters "service" (string) and "instance_count" (positive integer - how many instances to restart; use a large number, or 3+, for a fleet-wide restart)
- scale_service: requires parameters "service" (string), "target_replicas" (non-negative integer - the desired replica count; 0 means scale to zero), and "direction" (either "up" or "down")
- switch_feature_flag: requires parameters "flag_name" (string) and "enabled" (boolean)

Rules, followed strictly:
- action_type must be exactly one of the four values above.
- parameters must contain exactly the fields that action requires - no
  more, no fewer.
- Base your recommendation only on the diagnosis given. Do not recommend
  an action unrelated to the stated root cause.
"""


class _RollbackParams(BaseModel):
    """Expected parameters for rollback_deployment."""

    model_config = {"extra": "forbid"}

    deployment_id: str


class _RestartParams(BaseModel):
    """Expected parameters for restart_service.

    Keys match app.investigation.risk.classify_risk and
    app.investigation.action_executor.ControlledActionExecutor exactly
    (instance_count), not an independently-invented vocabulary - "service"
    is kept alongside it purely for evidence grounding (see
    RemediationPlannerNode._is_grounded), not read by either downstream
    consumer.
    """

    model_config = {"extra": "forbid"}

    service: str
    instance_count: int = Field(default=1, gt=0)


class _ScaleParams(BaseModel):
    """Expected parameters for scale_service.

    Keys match app.investigation.risk.classify_risk and
    app.investigation.action_executor.ControlledActionExecutor exactly
    (target_replicas, direction) - "service" is kept alongside them purely
    for evidence grounding, not read by either downstream consumer.
    target_replicas allows 0 (a deliberate scale-to-zero, already flagged
    HIGH risk by classify_risk and accepted - not rejected - by
    ControlledActionExecutor); only negative values are invalid.
    """

    model_config = {"extra": "forbid"}

    service: str
    target_replicas: int = Field(ge=0)
    direction: str


class _FeatureFlagParams(BaseModel):
    """Expected parameters for switch_feature_flag."""

    model_config = {"extra": "forbid"}

    flag_name: str
    enabled: bool


_PARAMETER_SCHEMAS = {
    RemediationActionType.ROLLBACK_DEPLOYMENT: _RollbackParams,
    RemediationActionType.RESTART_SERVICE: _RestartParams,
    RemediationActionType.SCALE_SERVICE: _ScaleParams,
    RemediationActionType.SWITCH_FEATURE_FLAG: _FeatureFlagParams,
}


class _RawRemediation(BaseModel):
    """Structured LLM output for a remediation recommendation, pre-validation.

    parameters is an untyped dict here deliberately - it is validated
    against the matching _PARAMETER_SCHEMAS entry for action_type after
    the LLM call, never trusted or executed as raw output.
    """

    action_type: RemediationActionType
    parameters: dict = Field(default_factory=dict)
    rationale: str = ""


class StructuredLLM(Protocol):
    """The minimal interface this node depends on - see hypothesis_generator.py for rationale."""

    async def ainvoke(self, messages: list) -> _RawRemediation: ...


class RemediationPlannerNode:
    """LangGraph node that recommends a controlled remediation action for a diagnosis.

    The LLM selects only from the fixed RemediationActionType registry and
    supplies parameters for it; those parameters are validated against a
    strict per-action-type schema before a RemediationCandidate is ever
    constructed. A malformed or mismatched parameter set is rejected
    entirely (remediation=None) rather than passed through partially
    validated - this node never lets an unvalidated parameter set reach
    anything that could act on it.
    """

    def __init__(self, structured_llm: Optional[StructuredLLM] = None):
        """Initialize the node.

        Args:
            structured_llm: A structured-output-wrapped LLM implementing
                StructuredLLM. Defaults to the $0 Groq default model from
                LLMRegistry, wrapped via with_structured_output.
        """
        self._structured_llm = structured_llm or LLMRegistry.get(settings.DEFAULT_LLM_MODEL).with_structured_output(
            _RawRemediation
        )

    def _build_prompt(self, state: InvestigationState) -> list:
        """Build the system/human messages sent to the LLM."""
        system = SystemMessage(content=_SYSTEM_PROMPT.format(service=state.service))
        impact_line = f"Impact: {state.diagnosis.impact.description}" if state.diagnosis.impact else "Impact: unknown"
        human = HumanMessage(
            content=(
                f"Diagnosis: {state.diagnosis.probable_cause}\n"
                f"Confidence: {state.diagnosis.confidence}\n"
                f"{impact_line}"
            )
        )
        return [system, human]

    def _is_grounded(self, state: InvestigationState, action_type: RemediationActionType, parameters: dict) -> bool:
        """Check that the proposed action's parameters refer to real, observed entities.

        Mirrors the evidence-grounding discipline enforced everywhere
        else in this pipeline (e.g. hypothesis_generator drops any
        hallucinated evidence citation) - a deployment_id or service name
        the LLM invented, rather than one actually seen in evidence, must
        not reach a RemediationCandidate that a later phase could act on.
        switch_feature_flag has no evidence source to ground against yet,
        so only schema validation applies to it.
        """
        if action_type == RemediationActionType.ROLLBACK_DEPLOYMENT:
            if state.evidence is None:
                return False
            real_deployment_ids = {d.deployment_id for d in state.evidence.deployments}
            return parameters.get("deployment_id") in real_deployment_ids

        if action_type in (RemediationActionType.RESTART_SERVICE, RemediationActionType.SCALE_SERVICE):
            return parameters.get("service") == state.service

        return True

    async def __call__(self, state: InvestigationState) -> dict:
        """Recommend a remediation action for a diagnosed incident.

        Args:
            state: Current investigation state. Must have diagnosis
                already populated by the diagnosis node.

        Returns:
            dict: Partial state update setting remediation. None if no
            diagnosis was reached (confidence 0.0 - nothing confirmed to
            remediate), if the LLM's parameters failed validation against
            the chosen action's expected schema, or if the parameters
            reference an entity (deployment, service) not actually
            present in the collected evidence.

        Raises:
            ValueError: If diagnosis has not been reached yet at all
                (state.diagnosis is None - a graph-ordering error, not a
                "no root cause found" outcome, which is handled as a
                short-circuit instead).
        """
        if state.diagnosis is None:
            raise ValueError(
                "RemediationPlannerNode requires state.diagnosis to be set. "
                "Run DiagnosisNode earlier in the graph first."
            )

        if state.diagnosis.confidence == 0.0:
            return {"remediation": None}

        messages = self._build_prompt(state)
        raw = await self._structured_llm.ainvoke(messages)

        schema_cls = _PARAMETER_SCHEMAS[raw.action_type]
        try:
            validated_params = schema_cls(**raw.parameters)
        except ValidationError:
            return {"remediation": None}

        if not self._is_grounded(state, raw.action_type, validated_params.model_dump()):
            return {"remediation": None}

        candidate = RemediationCandidate(
            action_type=raw.action_type,
            parameters=validated_params.model_dump(),
            rationale=raw.rationale,
        )
        return {"remediation": candidate}