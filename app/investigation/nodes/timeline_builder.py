"""Timeline construction node for the incident investigation graph."""

from app.investigation.schemas import InvestigationState, TimelineEntry


class TimelineBuilderNode:
    """LangGraph node that turns collected evidence into a chronological timeline.

    Only discrete events (log entries, deployments) become timeline
    entries - metric points remain a continuous series on
    state.evidence.metrics for nodes that need the numeric trend, rather
    than being itemized individually here, which would produce a noisy
    timeline rather than a readable "what happened" story.
    """

    async def __call__(self, state: InvestigationState) -> dict:
        """Build a sorted timeline from the state's collected evidence.

        Args:
            state: Current investigation state. Must have evidence
                already populated by the evidence_collector node.

        Returns:
            dict: Partial state update setting timeline.

        Raises:
            ValueError: If evidence has not been collected yet - this
                node has a genuine precondition on graph ordering, and
                silently producing an empty timeline would hide that
                ordering bug rather than surface it.
        """
        if state.evidence is None:
            raise ValueError(
                "TimelineBuilderNode requires state.evidence to be set. "
                "Run EvidenceCollectorNode earlier in the graph first."
            )

        entries = [
            TimelineEntry(
                timestamp=log.timestamp,
                event_type=f"log_{log.severity}",
                description=log.message,
            )
            for log in state.evidence.logs
        ]
        entries += [
            TimelineEntry(
                timestamp=deployment.timestamp,
                event_type="deployment",
                description=deployment.change_summary or f"Deployment {deployment.deployment_id}",
            )
            for deployment in state.evidence.deployments
        ]
        entries.sort(key=lambda entry: entry.timestamp)

        return {"timeline": entries}