"""Diagnosis node for the incident investigation graph - the final step of this phase."""

from app.investigation.schemas import DiagnosisResult, InvestigationState


class DiagnosisNode:
    """LangGraph node that selects the working diagnosis from validated hypotheses.

    Pure selection logic - no LLM call. The hard reasoning (is this
    hypothesis grounded? does the evidence really support it?) already
    happened in HypothesisGeneratorNode and EvidenceValidatorNode; this
    node's job is to pick the strongest surviving candidate and assemble
    the final DiagnosisResult, or to honestly report that no root cause
    could be confirmed rather than fabricating one.
    """

    async def __call__(self, state: InvestigationState) -> dict:
        """Select the diagnosis from the investigation's validated hypotheses.

        Args:
            state: Current investigation state. Must have evidence already
                populated by the evidence_collector node. impact and
                validated_hypotheses may be empty - both are handled
                explicitly rather than assumed present.

        Returns:
            dict: Partial state update setting diagnosis. If no
            hypothesis survived validation, returns a zero-confidence
            diagnosis stating that honestly, rather than a fabricated
            root cause.

        Raises:
            ValueError: If evidence has not been collected yet.
        """
        if state.evidence is None:
            raise ValueError(
                "DiagnosisNode requires state.evidence to be set. "
                "Run EvidenceCollectorNode earlier in the graph first."
            )

        if not state.validated_hypotheses:
            diagnosis = DiagnosisResult(
                probable_cause="No root cause could be confirmed from the available evidence.",
                confidence=0.0,
                supporting_evidence=[],
                impact=state.impact,
            )
            return {"diagnosis": diagnosis}

        chosen = max(state.validated_hypotheses, key=lambda h: h.confidence)
        diagnosis = DiagnosisResult(
            probable_cause=chosen.statement,
            confidence=chosen.confidence,
            supporting_evidence=chosen.supporting_evidence,
            impact=state.impact,
        )
        return {"diagnosis": diagnosis}