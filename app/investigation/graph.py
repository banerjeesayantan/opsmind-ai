"""Assembles the incident investigation LangGraph from its individual nodes."""

from typing import Optional

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.investigation.nodes.diagnosis import DiagnosisNode
from app.investigation.nodes.evidence_collector import EvidenceCollectorNode
from app.investigation.nodes.evidence_validator import EvidenceValidatorNode
from app.investigation.nodes.hypothesis_generator import HypothesisGeneratorNode
from app.investigation.nodes.impact_analyzer import ImpactAnalyzerNode
from app.investigation.nodes.timeline_builder import TimelineBuilderNode
from app.investigation.schemas import InvestigationState
from app.telemetry import TelemetryService


def build_investigation_graph(
    telemetry_service: Optional[TelemetryService] = None,
) -> CompiledStateGraph:
    """Build and compile the incident investigation graph.

    Flow: evidence_collector -> timeline_builder -> hypothesis_generator ->
    evidence_validator -> impact_analyzer -> diagnosis -> END. This is a
    single linear pipeline, not a branching agent - each stage's job is
    narrow and its output is fully consumed by the next, which is what
    keeps every stage independently testable (as each node's own test
    suite already does with fakes) while still composing into one real
    LangGraph.

    Args:
        telemetry_service: Telemetry service for EvidenceCollectorNode.
            Defaults to the $0/local mock sources. hypothesis_generator,
            evidence_validator, and impact_analyzer each default
            internally to the $0 Groq LLM (see their own modules) -
            there is no single shared LLM injection point here, since
            each node owns its own structured-output contract.

    Returns:
        CompiledStateGraph: The compiled investigation graph, ready to
        run via .ainvoke(InvestigationState(...)).
    """
    builder = StateGraph(InvestigationState)

    builder.add_node("evidence_collector", EvidenceCollectorNode(telemetry_service=telemetry_service))
    builder.add_node("timeline_builder", TimelineBuilderNode())
    builder.add_node("hypothesis_generator", HypothesisGeneratorNode())
    builder.add_node("evidence_validator", EvidenceValidatorNode())
    builder.add_node("impact_analyzer", ImpactAnalyzerNode())
    builder.add_node("diagnosis", DiagnosisNode())

    builder.set_entry_point("evidence_collector")
    builder.add_edge("evidence_collector", "timeline_builder")
    builder.add_edge("timeline_builder", "hypothesis_generator")
    builder.add_edge("hypothesis_generator", "evidence_validator")
    builder.add_edge("evidence_validator", "impact_analyzer")
    builder.add_edge("impact_analyzer", "diagnosis")
    builder.add_edge("diagnosis", END)

    return builder.compile()




