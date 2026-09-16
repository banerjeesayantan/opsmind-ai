"""Post-action verification - did the remediation actually fix the incident.

An agent is not considered successful merely because it recommended and
executed an action (see app.models.verification.Verification's
docstring) - this module collects fresh telemetry after an action has
run and compares it against the incident's original evidence to decide
whether things actually recovered.

Deliberately not an LLM call: recovery is judged from concrete numbers
(has average latency/error-rate dropped since the action ran), which is
both cheaper than a model call and, more importantly, not something we
want to leave to a model's subjective read of "does this look better" -
a threshold-based comparison is auditable and regression-testable.
"""

from dataclasses import dataclass, field
from typing import Optional

from app.telemetry import TelemetryService, TimeWindow
from app.telemetry.schemas import EvidenceBundle

# A metric average must drop by at least this fraction relative to the
# "before" window average to count as recovered. Guards against noise-
# level fluctuations being read as recovery.
_RECOVERY_IMPROVEMENT_THRESHOLD = 0.2

# A "before" window with zero errors and low latency, and an "after"
# window that stays that way, still counts as recovered (there was
# nothing to recover from, or it's already healthy) - see
# _is_recovered for how these two checks combine.


@dataclass
class VerificationComparison:
    """The result of comparing before/after telemetry for a verification check.

    Attributes:
        recovered: Whether the comparison judges the incident resolved.
        before_avg_metric_value: Mean of the "before" window's metric
            readings (e.g. latency), or None if there were none.
        after_avg_metric_value: Mean of the "after" window's metric
            readings, or None if there were none.
        before_error_log_count: Number of error/critical-severity log
            lines observed in the "before" window.
        after_error_log_count: Number of error/critical-severity log
            lines observed in the "after" window.
        notes: Human-readable summary of the comparison, suitable for
            Verification.notes.
    """

    recovered: bool
    before_avg_metric_value: Optional[float]
    after_avg_metric_value: Optional[float]
    before_error_log_count: int
    after_error_log_count: int
    notes: str
    after_evidence: EvidenceBundle = field(repr=False, default=None)


def _error_log_count(bundle: EvidenceBundle) -> int:
    """Count error/critical-severity log lines in an evidence bundle."""
    return sum(1 for log in bundle.logs if log.severity.lower() in ("error", "critical"))


def _avg_metric_value(bundle: EvidenceBundle) -> Optional[float]:
    """Mean value across all metric points in an evidence bundle, or None if empty."""
    if not bundle.metrics:
        return None
    return sum(point.value for point in bundle.metrics) / len(bundle.metrics)


def _is_recovered(
    before_avg: Optional[float],
    after_avg: Optional[float],
    before_errors: int,
    after_errors: int,
) -> bool:
    """Decide recovery from metric and error-log trends.

    Any error/critical log line still present in the "after" window means
    not recovered, full stop, regardless of what the metric trend looks
    like - a lingering error is exactly the kind of ongoing problem a
    metric average can mask. With a clean "after" window, recovery then
    additionally requires the average metric value to have improved by at
    least the recovery threshold relative to the "before" baseline, when
    there is a baseline to compare against.
    """
    if after_errors > 0:
        return False

    if before_avg is None or before_avg == 0 or after_avg is None:
        # No usable metric baseline to compare against - a clean "after"
        # window with nothing further to check against is recovery.
        return True

    improvement = (before_avg - after_avg) / before_avg
    return improvement >= _RECOVERY_IMPROVEMENT_THRESHOLD


class VerificationService:
    """Collects fresh telemetry after a remediation and compares it to baseline.

    Uses the same TelemetryService abstraction as the investigation
    graph's EvidenceCollectorNode, so a real telemetry backend (once
    configured) is used for verification with no change to this class.
    """

    def __init__(self, telemetry_service: Optional[TelemetryService] = None):
        """Initialize the service.

        Args:
            telemetry_service: Telemetry service to collect fresh
                "after" evidence from. Defaults to the $0/local mock
                sources.
        """
        self._telemetry_service = telemetry_service or TelemetryService.with_mock_sources()

    async def verify(
        self,
        service: str,
        before_evidence: EvidenceBundle,
        after_window: TimeWindow,
    ) -> VerificationComparison:
        """Collect fresh telemetry and compare it against the incident's original evidence.

        Args:
            service: Name of the service under investigation.
            before_evidence: The EvidenceBundle originally collected
                during investigation (InvestigationState.evidence) -
                the baseline the incident was diagnosed from.
            after_window: The time window to collect fresh "after"
                telemetry from - typically the period immediately
                following the action's execution.

        Returns:
            VerificationComparison: The recovery verdict plus the
            concrete numbers behind it.
        """
        after_evidence = await self._telemetry_service.collect_evidence(service, after_window)

        before_avg = _avg_metric_value(before_evidence)
        after_avg = _avg_metric_value(after_evidence)
        before_errors = _error_log_count(before_evidence)
        after_errors = _error_log_count(after_evidence)

        recovered = _is_recovered(before_avg, after_avg, before_errors, after_errors)

        notes = (
            f"Error logs: {before_errors} before -> {after_errors} after. "
            f"Avg metric value: {before_avg if before_avg is not None else 'n/a'} before -> "
            f"{after_avg if after_avg is not None else 'n/a'} after. "
            f"Verdict: {'recovered' if recovered else 'not recovered'}."
        )

        return VerificationComparison(
            recovered=recovered,
            before_avg_metric_value=before_avg,
            after_avg_metric_value=after_avg,
            before_error_log_count=before_errors,
            after_error_log_count=after_errors,
            notes=notes,
            after_evidence=after_evidence,
        )
