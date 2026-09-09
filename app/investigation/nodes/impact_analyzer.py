"""Impact analysis node for the incident investigation graph."""

from typing import Optional, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.core.config import settings
from app.investigation.schemas import ImpactAssessment, InvestigationState
from app.models.incident_enums import Severity
from app.services.llm import LLMRegistry

_SYSTEM_PROMPT = """You are assessing the observed impact of a production incident for the service "{service}".

You will be given metric readings, the incident timeline, and (if
available) validated root-cause hypotheses. Assess the concrete, observed
impact - not the hypothesized cause.

Rules, followed strictly:
- severity must be one of: low, medium, high, critical.
- description must describe concrete observed impact using the actual
  numbers given (e.g. "checkout API latency rose from 0.4s to 2.6s over
  14 minutes"), not a vague restatement like "the service was impacted".
- Base your assessment only on the data given. Do not assume impact that
  isn't evidenced by the metrics or timeline.
"""


class _ImpactVerdict(BaseModel):
    """Structured LLM output for the impact assessment."""

    description: str
    severity: Severity


class StructuredLLM(Protocol):
    """The minimal interface this node depends on - see hypothesis_generator.py for rationale."""

    async def ainvoke(self, messages: list) -> _ImpactVerdict: ...


class ImpactAnalyzerNode:
    """LangGraph node that assesses the concrete impact of an incident.

    Runs off state.evidence directly (particularly metrics), not off
    state.validated_hypotheses - what actually happened to the system is
    a separate question from whether a root cause was confirmed, so this
    node still produces a useful assessment even if evidence_validator
    rejected every hypothesis.
    """

    def __init__(self, structured_llm: Optional[StructuredLLM] = None):
        """Initialize the node.

        Args:
            structured_llm: A structured-output-wrapped LLM implementing
                StructuredLLM. Defaults to the $0 Groq default model.
        """
        self._structured_llm = structured_llm or LLMRegistry.get(settings.DEFAULT_LLM_MODEL).with_structured_output(
            _ImpactVerdict
        )

    def _build_prompt(self, state: InvestigationState) -> list:
        """Build the system/human messages sent to the LLM."""
        system = SystemMessage(content=_SYSTEM_PROMPT.format(service=state.service))

        metric_lines = [
            f"- [{m.timestamp.strftime('%H:%M:%S')}] {m.metric_name} = {m.value}" for m in state.evidence.metrics
        ]
        timeline_lines = [
            f"- [{e.timestamp.strftime('%H:%M:%S')}] ({e.event_type}) {e.description}" for e in state.timeline
        ]
        hypothesis_lines = [f"- {h.statement} (confidence {h.confidence})" for h in state.validated_hypotheses]

        sections = [f"Metrics:\n" + ("\n".join(metric_lines) or "(none)")]
        sections.append("Timeline:\n" + ("\n".join(timeline_lines) or "(none)"))
        sections.append("Validated hypotheses:\n" + ("\n".join(hypothesis_lines) or "(none confirmed)"))

        human = HumanMessage(content="\n\n".join(sections))
        return [system, human]

    async def __call__(self, state: InvestigationState) -> dict:
        """Assess the concrete impact of the incident.

        Args:
            state: Current investigation state. Must have evidence already
                populated by the evidence_collector node.

        Returns:
            dict: Partial state update setting impact. If no evidence at
            all was collected, returns a default LOW-severity assessment
            without making an LLM call.

        Raises:
            ValueError: If evidence has not been collected yet.
        """
        if state.evidence is None:
            raise ValueError(
                "ImpactAnalyzerNode requires state.evidence to be set. "
                "Run EvidenceCollectorNode earlier in the graph first."
            )

        if state.evidence.is_empty:
            return {
                "impact": ImpactAssessment(
                    description="No evidence was observed for this incident.",
                    severity=Severity.LOW,
                )
            }

        messages = self._build_prompt(state)
        verdict = await self._structured_llm.ainvoke(messages)

        return {"impact": ImpactAssessment(description=verdict.description, severity=verdict.severity)}
    