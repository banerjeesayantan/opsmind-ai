"""Evidence validation node for the incident investigation graph."""

from typing import Optional, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.core.config import settings
from app.investigation.schemas import HypothesisCandidate, InvestigationState
from app.services.llm import LLMRegistry

_SYSTEM_PROMPT = """You are reviewing a candidate root-cause hypothesis for a production incident.

You will be given the hypothesis's claim and the exact evidence it cites.
Your job is to judge whether that evidence genuinely supports the specific
claim being made - not whether the evidence exists (it does, by
construction), but whether it actually justifies this particular
conclusion rather than just being loosely related.

Rules, followed strictly:
- supported must be false if the evidence is only tangentially related to
  the specific claim, even if it's real evidence from the incident.
- adjusted_confidence should reflect your own assessment after reviewing
  the evidence, which may be higher or lower than the hypothesis's
  original confidence.
- Be skeptical. A hypothesis with weak evidence should be marked
  unsupported rather than passed through out of leniency.
"""


class _ValidationVerdict(BaseModel):
    """Structured LLM output: whether a hypothesis's evidence actually supports its claim."""

    supported: bool
    adjusted_confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


class StructuredLLM(Protocol):
    """The minimal interface this node depends on - see hypothesis_generator.py for rationale."""

    async def ainvoke(self, messages: list) -> _ValidationVerdict: ...


class EvidenceValidatorNode:
    """LangGraph node that checks each hypothesis's evidence against its specific claim.

    Distinct from the structural grounding already enforced in
    HypothesisGeneratorNode (every citation resolves to a real evidence
    item) - this is a semantic check of whether that evidence actually
    justifies the conclusion being drawn from it, not just that evidence
    of some kind was cited.
    """

    def __init__(self, structured_llm: Optional[StructuredLLM] = None):
        """Initialize the node.

        Args:
            structured_llm: A structured-output-wrapped LLM implementing
                StructuredLLM. Defaults to the $0 Groq default model.
        """
        self._structured_llm = structured_llm or LLMRegistry.get(settings.DEFAULT_LLM_MODEL).with_structured_output(
            _ValidationVerdict
        )

    def _build_prompt(self, hypothesis: HypothesisCandidate) -> list:
        """Build the system/human messages sent to the LLM for one hypothesis."""
        system = SystemMessage(content=_SYSTEM_PROMPT)
        evidence_lines = [
            f"- [{c.timestamp.strftime('%H:%M:%S')}] ({c.source}) {c.content}" for c in hypothesis.supporting_evidence
        ]
        human = HumanMessage(
            content=(
                f"Claim: {hypothesis.statement}\n"
                f"Reasoning given: {hypothesis.reasoning}\n"
                f"Original confidence: {hypothesis.confidence}\n\n"
                f"Cited evidence:\n" + "\n".join(evidence_lines)
            )
        )
        return [system, human]

    async def _validate_one(self, hypothesis: HypothesisCandidate) -> _ValidationVerdict:
        """Run the validation check for a single hypothesis."""
        messages = self._build_prompt(hypothesis)
        return await self._structured_llm.ainvoke(messages)

    async def __call__(self, state: InvestigationState) -> dict:
        """Validate each candidate hypothesis's evidence against its specific claim.

        Args:
            state: Current investigation state. Must have hypotheses
                already populated by the hypothesis_generator node
                (an empty list is a valid state, not an error).

        Returns:
            dict: Partial state update setting validated_hypotheses - the
            subset of state.hypotheses judged to be genuinely supported by
            their cited evidence, with validated=True and confidence
            replaced by the validator's own reassessment. No LLM calls
            are made if state.hypotheses is empty.
        """
        if not state.hypotheses:
            return {"validated_hypotheses": []}

        validated: list[HypothesisCandidate] = []
        for hypothesis in state.hypotheses:
            verdict = await self._validate_one(hypothesis)
            if verdict.supported:
                validated.append(
                    hypothesis.model_copy(update={"validated": True, "confidence": verdict.adjusted_confidence})
                )

        return {"validated_hypotheses": validated}

    