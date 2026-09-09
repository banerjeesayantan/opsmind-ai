"""Evidence collection node for the incident investigation graph."""

from typing import Optional

from app.investigation.schemas import InvestigationState
from app.telemetry import TelemetryService


class EvidenceCollectorNode:
    """LangGraph node that collects raw telemetry evidence for an incident.

    A thin wrapper around app.telemetry.TelemetryService - this node has
    no logic of its own beyond calling the service and putting the result
    on state. Uses the $0/local mock sources by default; a real
    deployment would construct this node with a TelemetryService wired to
    real adapters (Prometheus, Loki, GitHub) instead, with no change to
    this class.
    """

    def __init__(self, telemetry_service: Optional[TelemetryService] = None):
        """Initialize the node.

        Args:
            telemetry_service: The telemetry service to collect evidence
                from. Defaults to the $0/local mock sources.
        """
        self._telemetry_service = telemetry_service or TelemetryService.with_mock_sources()

    async def __call__(self, state: InvestigationState) -> dict:
        """Collect evidence for the incident's service and time window.

        Args:
            state: Current investigation state. Must have service and
                time_window already set (established at investigation
                start, before this node runs).

        Returns:
            dict: Partial state update setting evidence.
        """
        bundle = await self._telemetry_service.collect_evidence(state.service, state.time_window)
        return {"evidence": bundle}