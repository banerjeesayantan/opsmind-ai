"""Tests for app.investigation.verification.VerificationService.

Uses a fake TelemetryService (matching the injectable-dependency pattern
used throughout app.investigation.nodes) so recovery/non-recovery
scenarios can be constructed deterministically, plus one integration
test against the real $0/local mock telemetry sources.

Run with: pytest tests/test_verification.py -v
"""

import asyncio
from datetime import datetime, timedelta, UTC

from app.investigation.verification import VerificationService
from app.telemetry import TelemetryService, TimeWindow
from app.telemetry.schemas import EvidenceBundle, LogEntry, MetricPoint


class FakeTelemetryService:
    """A stub TelemetryService returning a pre-built bundle regardless of args."""

    def __init__(self, bundle: EvidenceBundle):
        self._bundle = bundle
        self.calls: list[tuple[str, TimeWindow]] = []

    async def collect_evidence(self, service: str, time_window: TimeWindow) -> EvidenceBundle:
        self.calls.append((service, time_window))
        return self._bundle


def _window(start_offset_minutes: int = 0) -> TimeWindow:
    start = datetime(2026, 9, 6, 10, start_offset_minutes, tzinfo=UTC)
    return TimeWindow(start=start, end=start + timedelta(minutes=15))


def _bundle(service: str, window: TimeWindow, errors: int, metric_values: list[float]) -> EvidenceBundle:
    logs = [
        LogEntry(timestamp=window.start, service=service, severity="error", message=f"error {i}")
        for i in range(errors)
    ]
    metrics = [
        MetricPoint(timestamp=window.start, service=service, metric_name="latency", value=v)
        for v in metric_values
    ]
    return EvidenceBundle(service=service, time_window=window, logs=logs, metrics=metrics)


# --- recovered scenarios -------------------------------------------------------


def test_verify_reports_recovered_when_errors_and_latency_both_drop():
    before = _bundle("checkout", _window(), errors=3, metric_values=[2.0, 2.4, 2.6])
    after_bundle = _bundle("checkout", _window(20), errors=0, metric_values=[0.3, 0.4])
    fake_telemetry = FakeTelemetryService(after_bundle)
    service = VerificationService(telemetry_service=fake_telemetry)

    comparison = asyncio.run(service.verify("checkout", before, _window(20)))

    assert comparison.recovered is True
    assert comparison.before_error_log_count == 3
    assert comparison.after_error_log_count == 0
    assert "recovered" in comparison.notes


def test_verify_reports_recovered_when_nothing_was_wrong_before_or_after():
    before = _bundle("checkout", _window(), errors=0, metric_values=[])
    after_bundle = _bundle("checkout", _window(20), errors=0, metric_values=[])
    fake_telemetry = FakeTelemetryService(after_bundle)
    service = VerificationService(telemetry_service=fake_telemetry)

    comparison = asyncio.run(service.verify("checkout", before, _window(20)))

    assert comparison.recovered is True


# --- not-recovered scenarios ------------------------------------------------------


def test_verify_reports_not_recovered_when_errors_persist():
    before = _bundle("checkout", _window(), errors=3, metric_values=[2.0])
    after_bundle = _bundle("checkout", _window(20), errors=2, metric_values=[0.3])
    fake_telemetry = FakeTelemetryService(after_bundle)
    service = VerificationService(telemetry_service=fake_telemetry)

    comparison = asyncio.run(service.verify("checkout", before, _window(20)))

    assert comparison.recovered is False


def test_verify_reports_not_recovered_when_improvement_is_below_threshold():
    # Only ~10% latency improvement - below the 20% recovery threshold.
    before = _bundle("checkout", _window(), errors=0, metric_values=[2.0])
    after_bundle = _bundle("checkout", _window(20), errors=0, metric_values=[1.8])
    fake_telemetry = FakeTelemetryService(after_bundle)
    service = VerificationService(telemetry_service=fake_telemetry)

    comparison = asyncio.run(service.verify("checkout", before, _window(20)))

    assert comparison.recovered is False


def test_verify_reports_not_recovered_when_new_errors_appear_with_no_prior_metric_baseline():
    before = _bundle("checkout", _window(), errors=0, metric_values=[])
    after_bundle = _bundle("checkout", _window(20), errors=1, metric_values=[])
    fake_telemetry = FakeTelemetryService(after_bundle)
    service = VerificationService(telemetry_service=fake_telemetry)

    comparison = asyncio.run(service.verify("checkout", before, _window(20)))

    assert comparison.recovered is False


# --- wiring ------------------------------------------------------------------------


def test_verify_calls_telemetry_service_with_the_given_service_and_window():
    before = _bundle("checkout", _window(), errors=0, metric_values=[1.0])
    after_bundle = _bundle("checkout", _window(20), errors=0, metric_values=[0.5])
    fake_telemetry = FakeTelemetryService(after_bundle)
    service = VerificationService(telemetry_service=fake_telemetry)
    target_window = _window(20)

    asyncio.run(service.verify("checkout", before, target_window))

    assert fake_telemetry.calls == [("checkout", target_window)]


# --- integration with the real $0/local mock telemetry sources ---------------------


def test_verify_works_against_real_mock_telemetry_service():
    service = VerificationService(telemetry_service=TelemetryService.with_mock_sources())
    before = _bundle("checkout", _window(), errors=2, metric_values=[2.0, 2.6])

    comparison = asyncio.run(service.verify("checkout", before, _window(30)))

    # Not asserting a specific verdict here (the deterministic mock always
    # reproduces the same worsening pattern relative to any window it's
    # given) - just that the real TelemetryService code path runs
    # end-to-end and produces a well-formed comparison.
    assert isinstance(comparison.recovered, bool)
    assert comparison.after_evidence is not None
