"""Persistence layer for the incident investigation/response domain.

This is the ONLY place that writes app.models.* incident rows to the
database. Investigation graph nodes and the risk/action/verification
layers all operate on plain pydantic state and never touch a Session
directly - they call into IncidentPersistenceService (or hand it their
result) once they have something worth recording. This keeps the graph
nodes trivially testable with fakes (no DB required) while still giving
every write a single, auditable, regression-tested path.

Each incident persistence service is constructed with an injectable SQL
engine (defaulting to the shared app.services.database.database_service
engine), so the exact same code path runs against real Postgres in
production/dev and against an isolated in-memory SQLite engine in tests -
no mocking of the persistence layer itself is needed to test it.
"""

from datetime import datetime, UTC
from typing import Optional

from sqlmodel import Session, select

from app.investigation.schemas import DiagnosisResult, InvestigationState
from app.models.action_execution import ActionExecution
from app.models.approval import Approval
from app.models.diagnosis import Diagnosis
from app.models.evidence import Evidence
from app.models.hypothesis import Hypothesis
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.incident_enums import (
    ApprovalStatus,
    EvidenceSource,
    ExecutionStatus,
    HypothesisStatus,
    IncidentStatus,
    RemediationActionType,
    RiskLevel,
    Severity,
)
from app.models.remediation import Remediation
from app.models.verification import Verification
from app.services.database import database_service
from app.telemetry.schemas import EvidenceBundle
from app.core.metrics import (
    action_executions_total,
    approvals_total,
    diagnosis_confidence,
    incident_time_to_resolution_seconds,
    investigations_completed_total,
    remediations_by_risk_total,
    verifications_total,
)


class IncidentPersistenceService:
    """Reads and writes the incident domain model rows.

    Methods are declared async for interface consistency with the rest of
    the codebase (nodes, API routes) that await database operations, even
    though the underlying SQLModel Session calls are themselves
    synchronous - the same convention app.services.database.DatabaseService
    already uses.
    """

    def __init__(self, engine=None):
        """Initialize the service.

        Args:
            engine: SQLAlchemy engine to use. Defaults to the shared
                app.services.database.database_service engine (real
                Postgres). Tests inject an isolated in-memory SQLite
                engine instead so persistence logic can be regression-
                tested without depending on external state.
        """
        self.engine = engine if engine is not None else database_service.engine

    def _session(self) -> Session:
        return Session(self.engine)

    # -- Incident ----------------------------------------------------------

    async def create_incident(
        self,
        title: str,
        description: str = "",
        severity: Severity = Severity.MEDIUM,
        created_by: Optional[int] = None,
    ) -> Incident:
        """Create a new incident in the NEW status.

        Args:
            title: Short human-readable summary of the incident.
            description: Longer free-text description.
            severity: Initial business impact severity.
            created_by: Foreign key to the reporting user, if any.

        Returns:
            Incident: The created incident row.
        """
        with self._session() as session:
            incident = Incident(
                title=title,
                description=description,
                severity=severity,
                status=IncidentStatus.NEW,
                created_by=created_by,
            )
            session.add(incident)
            session.commit()
            session.refresh(incident)
            return incident

    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Fetch a single incident by ID, or None if it doesn't exist."""
        with self._session() as session:
            return session.get(Incident, incident_id)

    async def list_incidents(self) -> list[Incident]:
        """List all incidents, most recently created first."""
        with self._session() as session:
            statement = select(Incident).order_by(Incident.created_at.desc())
            return list(session.exec(statement).all())

    async def update_incident_status(self, incident_id: str, status: IncidentStatus) -> Incident:
        """Move an incident to a new lifecycle status.

        Sets resolved_at when transitioning into a terminal status
        (RESOLVED or UNRESOLVED); leaves it untouched otherwise.

        Args:
            incident_id: The incident to update.
            status: The new status.

        Returns:
            Incident: The updated incident row.

        Raises:
            ValueError: If no incident exists with that ID.
        """
        with self._session() as session:
            incident = session.get(Incident, incident_id)
            if incident is None:
                raise ValueError(f"No incident found with id {incident_id!r}")
            incident.status = status
            if status in (IncidentStatus.RESOLVED, IncidentStatus.UNRESOLVED):
                incident.resolved_at = datetime.now(UTC)
            session.add(incident)
            session.commit()
            session.refresh(incident)
            return incident

    async def add_incident_event(
        self,
        incident_id: str,
        event_type: str,
        description: str = "",
        occurred_at: Optional[datetime] = None,
        event_metadata: Optional[dict] = None,
    ) -> IncidentEvent:
        """Append a single timeline entry for an incident.

        Returns:
            IncidentEvent: The created, append-only timeline row.
        """
        with self._session() as session:
            event = IncidentEvent(
                incident_id=incident_id,
                event_type=event_type,
                description=description,
                occurred_at=occurred_at or datetime.now(UTC),
                event_metadata=event_metadata,
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

    async def get_timeline(self, incident_id: str) -> list:
        """Fetch an incident's append-only timeline, in chronological order."""
        with self._session() as session:
            statement = (
                select(IncidentEvent)
                .where(IncidentEvent.incident_id == incident_id)
                .order_by(IncidentEvent.occurred_at)
            )
            return list(session.exec(statement).all())

    # -- Investigation result (Evidence / Hypothesis / Diagnosis) ----------

    async def persist_investigation_result(self, incident_id: str, state: InvestigationState) -> dict:
        """Persist a completed investigation graph run's output.

        Maps the transient InvestigationState produced by
        app.investigation.graph into real DB rows: raw evidence, the
        timeline, every candidate hypothesis (validated or rejected), and
        the final diagnosis if one could be reached. Advances the
        incident's status to DIAGNOSED on success, or UNRESOLVED if no
        diagnosis could be confirmed.

        Args:
            incident_id: The incident this investigation covers.
            state: The completed InvestigationState (post-graph-run).

        Returns:
            dict: {
                "evidence_ids": list[int],
                "hypothesis_ids": list[int],
                "diagnosis_id": Optional[int],
            }
        """
        with self._session() as session:
            evidence_ids: list[int] = []
            citation_lookup: dict[tuple[str, datetime], int] = {}

            if state.evidence is not None:
                for log in state.evidence.logs:
                    row = Evidence(
                        incident_id=incident_id,
                        source=EvidenceSource.LOG,
                        content=log.message,
                        raw_data={"severity": log.severity, "metadata": log.metadata},
                        occurred_at=log.timestamp,
                    )
                    session.add(row)
                    session.flush()
                    evidence_ids.append(row.id)
                    citation_lookup[(log.message, log.timestamp)] = row.id

                for deployment in state.evidence.deployments:
                    content = deployment.change_summary or f"Deployment {deployment.deployment_id}"
                    row = Evidence(
                        incident_id=incident_id,
                        source=EvidenceSource.DEPLOYMENT_EVENT,
                        source_reference=deployment.deployment_id,
                        content=content,
                        raw_data={"commit_sha": deployment.commit_sha, "environment": deployment.environment},
                        occurred_at=deployment.timestamp,
                    )
                    session.add(row)
                    session.flush()
                    evidence_ids.append(row.id)
                    citation_lookup[(content, deployment.timestamp)] = row.id

                for metric in state.evidence.metrics:
                    content = f"{metric.metric_name} = {metric.value}"
                    row = Evidence(
                        incident_id=incident_id,
                        source=EvidenceSource.METRIC,
                        source_reference=metric.metric_name,
                        content=content,
                        raw_data={"value": metric.value, "labels": metric.labels},
                        occurred_at=metric.timestamp,
                    )
                    session.add(row)
                    session.flush()
                    evidence_ids.append(row.id)

            for entry in state.timeline:
                session.add(
                    IncidentEvent(
                        incident_id=incident_id,
                        event_type=entry.event_type,
                        description=entry.description,
                        occurred_at=entry.timestamp,
                    )
                )
            session.commit()

            validated_statements = {h.statement for h in state.validated_hypotheses}
            hypothesis_ids: list[int] = []
            statement_to_id: dict[str, int] = {}
            for candidate in state.hypotheses:
                supporting_ids = [
                    citation_lookup[(c.content, c.timestamp)]
                    for c in candidate.supporting_evidence
                    if (c.content, c.timestamp) in citation_lookup
                ]
                status = HypothesisStatus.VALIDATED if candidate.statement in validated_statements else (
                    HypothesisStatus.REJECTED
                )
                confidence = candidate.confidence
                if status == HypothesisStatus.VALIDATED:
                    validated_match = next(
                        (h for h in state.validated_hypotheses if h.statement == candidate.statement), None
                    )
                    if validated_match is not None:
                        confidence = validated_match.confidence

                row = Hypothesis(
                    incident_id=incident_id,
                    statement=candidate.statement,
                    reasoning=candidate.reasoning,
                    confidence=confidence,
                    status=status,
                    supporting_evidence_ids=supporting_ids,
                )
                session.add(row)
                session.flush()
                hypothesis_ids.append(row.id)
                statement_to_id[candidate.statement] = row.id
            session.commit()

            diagnosis_id: Optional[int] = None
            diagnosis: Optional[DiagnosisResult] = state.diagnosis
            if diagnosis is not None and diagnosis.probable_cause in statement_to_id:
                supporting_ids = [
                    citation_lookup[(c.content, c.timestamp)]
                    for c in diagnosis.supporting_evidence
                    if (c.content, c.timestamp) in citation_lookup
                ]
                # supporting_evidence_ids for the diagnosis is carried on the
                # linked Hypothesis row already; Diagnosis itself just needs
                # the finalized cause, confidence, and impact summary.
                diagnosis_row = Diagnosis(
                    incident_id=incident_id,
                    hypothesis_id=statement_to_id[diagnosis.probable_cause],
                    probable_cause=diagnosis.probable_cause,
                    confidence=diagnosis.confidence,
                    impact=diagnosis.impact.description if diagnosis.impact else "",
                    is_active=True,
                )
                session.add(diagnosis_row)
                session.flush()
                diagnosis_id = diagnosis_row.id
                _ = supporting_ids  # already captured via the hypothesis's own supporting_evidence_ids
                session.commit()

            incident = session.get(Incident, incident_id)
            if incident is not None:
                incident.status = IncidentStatus.DIAGNOSED if diagnosis_id is not None else IncidentStatus.UNRESOLVED
                if diagnosis is not None and diagnosis.impact is not None:
                    incident.severity = diagnosis.impact.severity
                session.add(incident)
                session.commit()

            investigations_completed_total.labels(
                outcome="diagnosed" if diagnosis_id is not None else "unresolved"
            ).inc()
            if diagnosis_id is not None and diagnosis is not None:
                diagnosis_confidence.observe(diagnosis.confidence)

            return {
                "evidence_ids": evidence_ids,
                "hypothesis_ids": hypothesis_ids,
                "diagnosis_id": diagnosis_id,
            }

    # -- Remediation / Approval (Phase 3) -----------------------------------

    async def persist_remediation(
        self,
        incident_id: str,
        diagnosis_id: int,
        action_type: RemediationActionType,
        parameters: dict,
        risk_level: RiskLevel,
        rationale: str = "",
        is_selected: bool = True,
    ) -> Remediation:
        """Persist a recommended remediation for a diagnosis.

        Deliberately takes plain fields rather than a graph-transient
        "RemediationCandidate" object, so this persistence step stays
        decoupled from whatever internal shape the remediation_planner
        node uses - the planner only needs to supply these fields,
        extracted from its own candidate representation.

        If is_selected is True, any previously-selected remediation for
        the same diagnosis is marked unselected first (an incident's
        diagnosis has at most one currently-active remediation).
        """
        with self._session() as session:
            if is_selected:
                statement = select(Remediation).where(
                    Remediation.diagnosis_id == diagnosis_id, Remediation.is_selected == True  # noqa: E712
                )
                for previous in session.exec(statement).all():
                    previous.is_selected = False
                    session.add(previous)

            remediation = Remediation(
                incident_id=incident_id,
                diagnosis_id=diagnosis_id,
                action_type=action_type,
                parameters=parameters or {},
                risk_level=risk_level,
                rationale=rationale,
                is_selected=is_selected,
            )
            session.add(remediation)
            session.commit()
            session.refresh(remediation)

        remediations_by_risk_total.labels(action_type=action_type.value, risk_level=risk_level.value).inc()
        return remediation

    async def get_remediation(self, remediation_id: int) -> Optional[Remediation]:
        """Fetch a single remediation by ID."""
        with self._session() as session:
            return session.get(Remediation, remediation_id)

    async def create_approval_request(
        self,
        incident_id: str,
        remediation_id: int,
        risk_level: RiskLevel,
    ) -> Approval:
        """Create the Approval audit row for a recommended remediation.

        Every remediation gets exactly one Approval row, regardless of
        risk: LOW risk is recorded as NOT_REQUIRED (auto-approved) so the
        audit trail is complete even when no human was involved. MEDIUM
        and HIGH risk are recorded as PENDING and block execution until
        decide_approval is called.

        Args:
            incident_id: The parent incident.
            remediation_id: The remediation being decided on.
            risk_level: The remediation's classified risk level, from
                app.investigation.risk.classify_risk.

        Returns:
            Approval: The created approval row.
        """
        from app.investigation.risk import requires_human_approval

        status = ApprovalStatus.PENDING if requires_human_approval(risk_level) else ApprovalStatus.NOT_REQUIRED
        with self._session() as session:
            approval = Approval(
                incident_id=incident_id,
                remediation_id=remediation_id,
                status=status,
            )
            session.add(approval)
            if status == ApprovalStatus.PENDING:
                incident = session.get(Incident, incident_id)
                if incident is not None:
                    incident.status = IncidentStatus.AWAITING_APPROVAL
                    session.add(incident)
            session.commit()
            session.refresh(approval)

        approvals_total.labels(status=status.value).inc()
        return approval

    async def get_approval(self, approval_id: int) -> Optional[Approval]:
        """Fetch a single approval request by ID."""
        with self._session() as session:
            return session.get(Approval, approval_id)

    async def decide_approval(
        self,
        approval_id: int,
        approved: bool,
        decided_by: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> Approval:
        """Record a human approve/reject decision on a pending approval.

        Args:
            approval_id: The approval request being decided.
            approved: True to approve, False to reject.
            decided_by: Foreign key to the deciding user, if known.
            reason: Optional rationale for the decision.

        Returns:
            Approval: The updated approval row.

        Raises:
            ValueError: If the approval doesn't exist, or is not
                currently PENDING (already decided, or never required).
        """
        with self._session() as session:
            approval = session.get(Approval, approval_id)
            if approval is None:
                raise ValueError(f"No approval found with id {approval_id!r}")
            if approval.status != ApprovalStatus.PENDING:
                raise ValueError(
                    f"Approval {approval_id} is not pending (status={approval.status.value}); "
                    "it cannot be decided again."
                )

            approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            approval.decided_at = datetime.now(UTC)
            approval.decided_by = decided_by
            approval.reason = reason
            session.add(approval)

            incident = session.get(Incident, approval.incident_id)
            if incident is not None:
                incident.status = (
                    IncidentStatus.REMEDIATING if approved else IncidentStatus.DIAGNOSED
                )
                session.add(incident)

            session.commit()
            session.refresh(approval)

        approvals_total.labels(status=approval.status.value).inc()
        return approval

    # -- Action execution (Phase 4) -----------------------------------------

    async def create_action_execution(
        self,
        incident_id: str,
        remediation_id: int,
        status: ExecutionStatus = ExecutionStatus.PENDING,
    ) -> ActionExecution:
        """Create a new execution attempt record for a remediation."""
        with self._session() as session:
            execution = ActionExecution(
                incident_id=incident_id,
                remediation_id=remediation_id,
                status=status,
            )
            session.add(execution)
            session.commit()
            session.refresh(execution)
            return execution

    async def complete_action_execution(
        self,
        execution_id: int,
        status: ExecutionStatus,
        result: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> ActionExecution:
        """Record the outcome of an execution attempt.

        On SUCCEEDED or SIMULATED, advances the parent incident to
        VERIFYING (ready for Phase 5). On FAILED, leaves the incident in
        REMEDIATING so it can be retried or re-planned.
        """
        with self._session() as session:
            execution = session.get(ActionExecution, execution_id)
            if execution is None:
                raise ValueError(f"No action execution found with id {execution_id!r}")

            execution.status = status
            execution.result = result
            execution.error_message = error_message
            session.add(execution)

            if status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.SIMULATED):
                incident = session.get(Incident, execution.incident_id)
                if incident is not None:
                    incident.status = IncidentStatus.VERIFYING
                    session.add(incident)

            session.commit()
            session.refresh(execution)

        action_executions_total.labels(
            action_type=self._action_type_for_execution(execution), status=status.value
        ).inc()
        return execution

    def _action_type_for_execution(self, execution: ActionExecution) -> str:
        """Best-effort action_type label for metrics, without an extra async round-trip."""
        with self._session() as session:
            remediation = session.get(Remediation, execution.remediation_id)
            return remediation.action_type.value if remediation else "unknown"

    async def get_action_execution(self, execution_id: int) -> Optional[ActionExecution]:
        """Fetch a single action execution by ID."""
        with self._session() as session:
            return session.get(ActionExecution, execution_id)

    # -- Verification (Phase 5) ----------------------------------------------

    async def create_verification(
        self,
        incident_id: str,
        action_execution_id: int,
        recovered: Optional[bool],
        evidence_after_ids: Optional[list[int]] = None,
        notes: str = "",
    ) -> Verification:
        """Persist a post-action verification check.

        Advances the incident to RESOLVED if recovered is True, or back
        to INVESTIGATING if recovered is False (the remediation didn't
        fix it, so the incident needs another look) rather than being
        marked resolved on the strength of the action alone.
        """
        with self._session() as session:
            verification = Verification(
                incident_id=incident_id,
                action_execution_id=action_execution_id,
                recovered=recovered,
                evidence_after_ids=evidence_after_ids or [],
                notes=notes,
            )
            session.add(verification)

            incident = session.get(Incident, incident_id)
            if incident is not None:
                if recovered is True:
                    incident.status = IncidentStatus.RESOLVED
                    incident.resolved_at = datetime.now(UTC)
                elif recovered is False:
                    incident.status = IncidentStatus.INVESTIGATING
                session.add(incident)

            session.commit()
            session.refresh(verification)

            recovered_label = "unknown" if recovered is None else ("true" if recovered else "false")
            verifications_total.labels(recovered=recovered_label).inc()

            if recovered is True and incident is not None and incident.resolved_at is not None:
                # Different backends (SQLite vs Postgres) round-trip
                # timezone awareness differently, so normalize both sides
                # to naive UTC before subtracting rather than assuming
                # either is tz-aware.
                created_at = incident.created_at.replace(tzinfo=None)
                resolved_at = incident.resolved_at.replace(tzinfo=None)
                seconds = (resolved_at - created_at).total_seconds()
                if seconds >= 0:
                    incident_time_to_resolution_seconds.observe(seconds)

        return verification

    async def get_verification(self, verification_id: int) -> Optional[Verification]:
        """Fetch a single verification by ID."""
        with self._session() as session:
            return session.get(Verification, verification_id)

    # -- Result retrieval (Phase 7 API support) ------------------------------

    async def list_evidence(self, incident_id: str) -> list[Evidence]:
        """List all persisted evidence for an incident, in chronological order."""
        with self._session() as session:
            statement = (
                select(Evidence).where(Evidence.incident_id == incident_id).order_by(Evidence.occurred_at)
            )
            return list(session.exec(statement).all())

    async def get_evidence_bundle(self, incident_id: str, service: str) -> EvidenceBundle:
        """Reconstruct an EvidenceBundle from an incident's persisted Evidence rows.

        Used as the "before" baseline for Phase 5 verification, since the
        transient InvestigationState.evidence used during the graph run
        isn't kept around after persist_investigation_result - the
        persisted Evidence rows are the durable record of what was
        originally observed.
        """
        from app.telemetry.schemas import DeploymentEvent, LogEntry, MetricPoint, TimeWindow

        rows = await self.list_evidence(incident_id)
        if not rows:
            now = datetime.now(UTC)
            return EvidenceBundle(service=service, time_window=TimeWindow(start=now, end=now))

        logs, metrics, deployments = [], [], []
        for row in rows:
            raw = row.raw_data or {}
            if row.source == EvidenceSource.LOG:
                logs.append(
                    LogEntry(
                        timestamp=row.occurred_at,
                        service=service,
                        severity=raw.get("severity", "info"),
                        message=row.content,
                        metadata=raw.get("metadata", {}),
                    )
                )
            elif row.source == EvidenceSource.METRIC:
                metrics.append(
                    MetricPoint(
                        timestamp=row.occurred_at,
                        service=service,
                        metric_name=row.source_reference or row.content.split(" = ")[0],
                        value=raw.get("value", 0.0),
                        labels=raw.get("labels", {}),
                    )
                )
            elif row.source == EvidenceSource.DEPLOYMENT_EVENT:
                deployments.append(
                    DeploymentEvent(
                        timestamp=row.occurred_at,
                        service=service,
                        deployment_id=row.source_reference or "",
                        commit_sha=raw.get("commit_sha", ""),
                        environment=raw.get("environment", "production"),
                        change_summary=row.content,
                    )
                )

        window = TimeWindow(
            start=min(r.occurred_at for r in rows),
            end=max(r.occurred_at for r in rows),
        )
        return EvidenceBundle(service=service, time_window=window, logs=logs, metrics=metrics, deployments=deployments)

    async def list_hypotheses(self, incident_id: str) -> list[Hypothesis]:
        """List all hypotheses generated for an incident."""
        with self._session() as session:
            statement = select(Hypothesis).where(Hypothesis.incident_id == incident_id)
            return list(session.exec(statement).all())

    async def get_active_diagnosis(self, incident_id: str) -> Optional[Diagnosis]:
        """Fetch the current active diagnosis for an incident, if any."""
        with self._session() as session:
            statement = select(Diagnosis).where(
                Diagnosis.incident_id == incident_id, Diagnosis.is_active == True  # noqa: E712
            )
            return session.exec(statement).first()

    async def list_remediations(self, incident_id: str) -> list[Remediation]:
        """List all remediations recommended for an incident."""
        with self._session() as session:
            statement = select(Remediation).where(Remediation.incident_id == incident_id)
            return list(session.exec(statement).all())

    async def list_approvals(self, incident_id: str) -> list[Approval]:
        """List all approval requests for an incident."""
        with self._session() as session:
            statement = select(Approval).where(Approval.incident_id == incident_id)
            return list(session.exec(statement).all())

    async def list_action_executions(self, incident_id: str) -> list[ActionExecution]:
        """List all action executions for an incident."""
        with self._session() as session:
            statement = select(ActionExecution).where(ActionExecution.incident_id == incident_id)
            return list(session.exec(statement).all())

    async def list_verifications(self, incident_id: str) -> list[Verification]:
        """List all verification checks for an incident."""
        with self._session() as session:
            statement = select(Verification).where(Verification.incident_id == incident_id)
            return list(session.exec(statement).all())


# Create a singleton instance, mirroring app.services.database.database_service.
incident_persistence_service = IncidentPersistenceService()
