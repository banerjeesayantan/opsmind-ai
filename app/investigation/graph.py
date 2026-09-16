"""Assembles the incident investigation LangGraph from its individual nodes."""

from typing import Optional

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.investigation.nodes.diagnosis import DiagnosisNode
from app.investigation.nodes.evidence_collector import EvidenceCollectorNode
from app.investigation.nodes.evidence_validator import EvidenceValidatorNode
from app.investigation.nodes.evidence_validator import StructuredLLM as EvidenceValidatorLLM
from app.investigation.nodes.hypothesis_generator import HypothesisGeneratorNode
from app.investigation.nodes.hypothesis_generator import StructuredLLM as HypothesisGeneratorLLM
from app.investigation.nodes.impact_analyzer import ImpactAnalyzerNode
from app.investigation.nodes.impact_analyzer import StructuredLLM as ImpactAnalyzerLLM
from app.investigation.nodes.remediation_planner import RemediationPlannerNode
from app.investigation.nodes.remediation_planner import StructuredLLM as RemediationPlannerLLM
from app.investigation.nodes.timeline_builder import TimelineBuilderNode
from app.investigation.schemas import InvestigationState
from app.telemetry import TelemetryService


def build_investigation_graph(
    telemetry_service: Optional[TelemetryService] = None,
    hypothesis_llm: Optional[HypothesisGeneratorLLM] = None,
    evidence_validator_llm: Optional[EvidenceValidatorLLM] = None,
    impact_llm: Optional[ImpactAnalyzerLLM] = None,
    remediation_llm: Optional[RemediationPlannerLLM] = None,
) -> CompiledStateGraph:
    """Build and compile the incident investigation graph.

    Flow: evidence_collector -> timeline_builder -> hypothesis_generator ->
    evidence_validator -> impact_analyzer -> diagnosis ->
    remediation_planner -> END. This is a single linear pipeline, not a
    branching agent - each stage's job is narrow and its output is fully
    consumed by the next, which is what keeps every stage independently
    testable (as each node's own test suite already does with fakes)
    while still composing into one real LangGraph.

    Args:
        telemetry_service: Telemetry service for EvidenceCollectorNode.
            Defaults to the $0/local mock sources.
        hypothesis_llm: Structured LLM for HypothesisGeneratorNode.
            Defaults to the $0 Groq default model.
        evidence_validator_llm: Structured LLM for EvidenceValidatorNode.
            Defaults to the $0 Groq default model.
        impact_llm: Structured LLM for ImpactAnalyzerNode. Defaults to
            the $0 Groq default model.
        remediation_llm: Structured LLM for RemediationPlannerNode.
            Defaults to the $0 Groq default model. Each LLM-calling node
            owns its own structured-output contract, so each gets its
            own injection seam here rather than one shared LLM parameter
            for the whole graph.

    Returns:
        CompiledStateGraph: The compiled investigation graph, ready to
        run via .ainvoke(InvestigationState(...)).
    """
    builder = StateGraph(InvestigationState)

    builder.add_node("evidence_collector", EvidenceCollectorNode(telemetry_service=telemetry_service))
    builder.add_node("timeline_builder", TimelineBuilderNode())
    builder.add_node("hypothesis_generator", HypothesisGeneratorNode(structured_llm=hypothesis_llm))
    builder.add_node("evidence_validator", EvidenceValidatorNode(structured_llm=evidence_validator_llm))
    builder.add_node("impact_analyzer", ImpactAnalyzerNode(structured_llm=impact_llm))
    builder.add_node("diagnosis", DiagnosisNode())
    builder.add_node("remediation_planner", RemediationPlannerNode(structured_llm=remediation_llm))

    builder.set_entry_point("evidence_collector")
    builder.add_edge("evidence_collector", "timeline_builder")
    builder.add_edge("timeline_builder", "hypothesis_generator")
    builder.add_edge("hypothesis_generator", "evidence_validator")
    builder.add_edge("evidence_validator", "impact_analyzer")
    builder.add_edge("impact_analyzer", "diagnosis")
    builder.add_edge("diagnosis", "remediation_planner")
    builder.add_edge("remediation_planner", END)

    return builder.compile()



