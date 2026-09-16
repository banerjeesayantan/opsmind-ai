"""State and supporting data structures for the incident investigation graph.

This state is transient and pre-persistence: evidence is referenced by
human-readable citation (source, content, timestamp), not by database ID,
because nothing has been written to app.models.evidence.Evidence or
app.models.hypothesis.Hypothesis yet at graph-execution time. Mapping the
final graph output into actual DB rows is a separate concern, handled
elsewhere, not by the graph itself.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.incident_enums import RemediationActionType, Severity
from app.telemetry.schemas import EvidenceBundle, TimeWindow


class EvidenceCitation(BaseModel):
    """A human-readable reference to a specific piece of observed evidence.

    Used inside HypothesisCandidate and DiagnosisResult so a claim can be
    traced back to what was actually observed, without depending on a
    database ID that doesn't exist yet at this stage of processing.

    Attributes:
        source: Which telemetry category this evidence came from
            (e.g. "log", "metric", "deployment").
        content: Short human-readable snippet of the evidence itself.
        timestamp: When the underlying evidence occurred.
    """

    source: str
    content: str
    timestamp: datetime


class TimelineEntry(BaseModel):
    """A single chronological entry in the investigation's working timeline.

    Mirrors the shape of app.models.incident_event.IncidentEvent so a
    later persistence step can map these across with no field renaming,
    without this graph depending on the database model directly.

    Attributes:
        timestamp: When the event occurred.
        event_type: Free-text category (e.g. "deployment", "log_error",
            "metric_anomaly").
        description: Human-readable summary of what happened.
    """

    timestamp: datetime
    event_type: str
    description: str


class HypothesisCandidate(BaseModel):
    """A single AI-generated candidate explanation, before validation.

    Attributes:
        statement: The candidate root-cause explanation, in plain language.
        reasoning: Longer explanation of how this was arrived at.
        confidence: Confidence in this hypothesis, from 0.0 to 1.0.
        supporting_evidence: Evidence citations this hypothesis is
            grounded in - required to be non-empty by the time a
            hypothesis reaches the validation node, since an ungrounded
            hypothesis is exactly what the evidence-vs-hypothesis
            separation exists to prevent.
        validated: Whether this candidate has passed evidence validation.
            False until the evidence_validator node processes it.
    """

    statement: str
    reasoning: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_evidence: list[EvidenceCitation] = Field(default_factory=list)
    validated: bool = False


class ImpactAssessment(BaseModel):
    """Assessed business impact of the incident.

    Attributes:
        description: Human-readable description of the impact
            (e.g. "increased checkout API latency for 12 minutes").
        severity: Business impact severity, reusing the same enum as
            app.models.incident.Incident rather than duplicating it.
    """

    description: str
    severity: Severity = Severity.MEDIUM


class DiagnosisResult(BaseModel):
    """The final output of a completed investigation.

    Attributes:
        probable_cause: The finalized root-cause statement, drawn from
            whichever validated hypothesis was selected.
        confidence: Confidence in this diagnosis, from 0.0 to 1.0.
        supporting_evidence: Evidence citations backing this diagnosis.
        impact: The assessed impact of the incident.
    """

    probable_cause: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_evidence: list[EvidenceCitation] = Field(default_factory=list)
    impact: Optional[ImpactAssessment] = None


class RemediationCandidate(BaseModel):
    """A recommended corrective action produced by the remediation planner.

    Deliberately the plain (action_type, parameters, rationale) shape
    that app.services.persistence.persist_remediation and
    app.investigation.risk.classify_risk both expect as plain arguments -
    those modules were built decoupled from this schema by design (see
    risk.py's own docstring), so this shape is the actual integration
    contract, not an implementation detail.

    Attributes:
        action_type: Which controlled action is being recommended - one
            of the fixed RemediationActionType values, never free-form.
        parameters: The parameters for this action, already validated
            against the chosen action's expected schema and checked to
            reference only real, observed entities (e.g. a real
            deployment_id actually seen in evidence, not one invented).
        rationale: Why this action was recommended, in plain language.
    """

    action_type: RemediationActionType
    parameters: dict = Field(default_factory=dict)
    rationale: str = ""


class InvestigationState(BaseModel):
    """State definition for the incident investigation LangGraph.

    Flows through the graph incrementally - each node reads what earlier
    nodes populated and adds its own contribution, following the same
    Command(update={...}) pattern as the existing chat graph in
    app.core.langgraph.graph.

    Attributes:
        incident_id: ID of the Incident this investigation covers.
        service: Name of the service under investigation.
        time_window: The incident's time window, reused from
            app.telemetry.schemas rather than duplicated.
        evidence: Raw evidence collected by the evidence_collector node.
            None until that node runs.
        timeline: Chronological entries built by the timeline_builder
            node from the raw evidence.
        hypotheses: All candidate hypotheses generated by the
            hypothesis_generator node, validated or not.
        validated_hypotheses: The subset of hypotheses that passed the
            evidence_validator node.
        impact: Impact assessment produced by the impact_analyzer node.
        diagnosis: The final diagnosis, once the graph has selected a
            validated hypothesis as the working root cause. None until
            the graph reaches that point.
        remediation: The recommended remediation action, once the
            remediation_planner node has run. None if no diagnosis was
            reached, or if the LLM's proposal failed schema/grounding
            validation.
    """

    incident_id: str
    service: str
    time_window: TimeWindow

    evidence: Optional[EvidenceBundle] = None
    timeline: list[TimelineEntry] = Field(default_factory=list)
    hypotheses: list[HypothesisCandidate] = Field(default_factory=list)
    validated_hypotheses: list[HypothesisCandidate] = Field(default_factory=list)
    impact: Optional[ImpactAssessment] = None
    diagnosis: Optional[DiagnosisResult] = None
    remediation: Optional[RemediationCandidate] = None






    