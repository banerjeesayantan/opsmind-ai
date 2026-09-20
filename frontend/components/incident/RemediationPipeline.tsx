"use client";

import { useState } from "react";
import type {
  ActionExecutionResponse,
  ApprovalResponse,
  DiagnosisResponse,
  RemediationResponse,
  VerificationResponse,
} from "@/lib/types";
import { actionTypeLabel, formatDateTime } from "@/lib/format";
import { incidentsApi } from "@/lib/incidents-api";
import { ApiError } from "@/lib/api-client";
import { ApprovalBadge, ExecutionBadge, RiskBadge } from "@/components/badges";
import { Button, Card, CardHeader, EmptyState, ErrorBanner } from "@/components/ui";
import { RecommendRemediationForm } from "./RecommendRemediationForm";

function latestBy<T>(items: T[], key: (item: T) => string): T | null {
  if (items.length === 0) return null;
  return [...items].sort((a, b) => new Date(key(b)).getTime() - new Date(key(a)).getTime())[0] ?? null;
}

export function RemediationSection({
  incidentId,
  diagnosis,
  remediations,
  approvals,
  executions,
  verifications,
  onChanged,
}: {
  incidentId: string;
  diagnosis: DiagnosisResponse | null;
  remediations: RemediationResponse[];
  approvals: ApprovalResponse[];
  executions: ActionExecutionResponse[];
  verifications: VerificationResponse[];
  onChanged: () => void;
}) {
  return (
    <Card>
      <CardHeader title="Remediation" subtitle="Recommended fixes, human approval, and controlled execution" />
      <div className="space-y-4 px-5 py-4">
        {!diagnosis && (
          <EmptyState title="No diagnosis yet" message="Run an investigation that reaches a diagnosis before recommending a remediation." />
        )}

        {diagnosis && (
          <RecommendRemediationForm incidentId={incidentId} diagnosisId={diagnosis.id} onRecommended={onChanged} />
        )}

        {diagnosis && remediations.length === 0 && (
          <EmptyState title="No remediation recommended yet" message="Use the form above to recommend a controlled action." />
        )}

        {remediations.length > 0 && (
          <div className="space-y-3">
            {remediations.map((remediation) => (
              <RemediationCard
                key={remediation.id}
                incidentId={incidentId}
                remediation={remediation}
                approval={latestBy(
                  approvals.filter((a) => a.remediation_id === remediation.id),
                  (a) => a.requested_at
                )}
                execution={latestBy(
                  executions.filter((e) => e.remediation_id === remediation.id),
                  (e) => e.executed_at
                )}
                verifications={verifications}
                onChanged={onChanged}
              />
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function RemediationCard({
  incidentId,
  remediation,
  approval,
  execution,
  verifications,
  onChanged,
}: {
  incidentId: string;
  remediation: RemediationResponse;
  approval: ApprovalResponse | null;
  execution: ActionExecutionResponse | null;
  verifications: VerificationResponse[];
  onChanged: () => void;
}) {
  const verification = execution ? latestBy(verifications.filter((v) => v.action_execution_id === execution.id), (v) => v.checked_at) : null;

  return (
    <div className="rounded-md border border-border-subtle bg-surface-raised">
      <div className="flex items-start justify-between gap-3 border-b border-border-subtle px-4 py-3">
        <div>
          <p className="text-sm font-medium text-ink">{actionTypeLabel(remediation.action_type)}</p>
          {remediation.rationale && <p className="mt-0.5 text-sm text-ink-tertiary">{remediation.rationale}</p>}
          {Object.keys(remediation.parameters).length > 0 && (
            <p className="mt-1.5 font-mono text-xs text-ink-tertiary">{JSON.stringify(remediation.parameters)}</p>
          )}
        </div>
        <RiskBadge risk={remediation.risk_level} />
      </div>

      <div className="grid grid-cols-1 divide-y divide-border-subtle sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <ApprovalStep incidentId={incidentId} approval={approval} onChanged={onChanged} />
        <ExecutionStep incidentId={incidentId} remediation={remediation} approval={approval} execution={execution} onChanged={onChanged} />
        <VerificationStep incidentId={incidentId} execution={execution} verification={verification} onChanged={onChanged} />
      </div>
    </div>
  );
}

function StepShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-4 py-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-tertiary">{title}</p>
      {children}
    </div>
  );
}

function ApprovalStep({
  incidentId,
  approval,
  onChanged,
}: {
  incidentId: string;
  approval: ApprovalResponse | null;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<"approve" | "reject" | null>(null);

  async function decide(approved: boolean) {
    if (!approval) return;
    setError(null);
    setLoading(approved ? "approve" : "reject");
    try {
      await incidentsApi.decideApproval(incidentId, approval.id, { approved });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't record that decision.");
    } finally {
      setLoading(null);
    }
  }

  if (!approval) {
    return (
      <StepShell title="Approval">
        <p className="text-sm text-ink-tertiary">Not requested yet</p>
      </StepShell>
    );
  }

  return (
    <StepShell title="Approval">
      <ApprovalBadge status={approval.status} />
      {approval.decided_at && <p className="mt-1.5 text-xs text-ink-tertiary">Decided {formatDateTime(approval.decided_at)}</p>}
      {approval.reason && <p className="mt-1 text-sm text-ink-tertiary">&ldquo;{approval.reason}&rdquo;</p>}
      {error && <p className="mt-1.5 text-sm text-severity-critical">{error}</p>}
      {approval.status === "pending" && (
        <div className="mt-2.5 flex gap-2">
          <Button variant="primary" onClick={() => decide(true)} loading={loading === "approve"} disabled={loading !== null}>
            Approve
          </Button>
          <Button variant="danger" onClick={() => decide(false)} loading={loading === "reject"} disabled={loading !== null}>
            Reject
          </Button>
        </div>
      )}
    </StepShell>
  );
}

function ExecutionStep({
  incidentId,
  remediation,
  approval,
  execution,
  onChanged,
}: {
  incidentId: string;
  remediation: RemediationResponse;
  approval: ApprovalResponse | null;
  execution: ActionExecutionResponse | null;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canExecute = !execution && approval && (approval.status === "approved" || approval.status === "not_required");

  async function handleExecute() {
    setError(null);
    setLoading(true);
    try {
      await incidentsApi.executeRemediation(incidentId, remediation.id);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Execution failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <StepShell title="Execution">
      {execution ? (
        <>
          <ExecutionBadge status={execution.status} />
          <p className="mt-1.5 text-xs text-ink-tertiary">{formatDateTime(execution.executed_at)}</p>
          {execution.error_message && <p className="mt-1 text-sm text-severity-critical">{execution.error_message}</p>}
        </>
      ) : (
        <p className="text-sm text-ink-tertiary">{approval ? "Not executed yet" : "Waiting on approval"}</p>
      )}
      {error && <p className="mt-1.5 text-sm text-severity-critical">{error}</p>}
      {canExecute && (
        <div className="mt-2.5">
          <Button variant="primary" onClick={handleExecute} loading={loading}>
            Execute
          </Button>
        </div>
      )}
    </StepShell>
  );
}

function VerificationStep({
  incidentId,
  execution,
  verification,
  onChanged,
}: {
  incidentId: string;
  execution: ActionExecutionResponse | null;
  verification: VerificationResponse | null;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const canVerify = execution && (execution.status === "succeeded" || execution.status === "simulated") && !verification;

  async function handleVerify() {
    if (!execution) return;
    setError(null);
    setLoading(true);
    try {
      await incidentsApi.verifyExecution(incidentId, execution.id, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Verification failed to run.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <StepShell title="Verification">
      {verification ? (
        <>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium ${
              verification.recovered ? "text-severity-low" : "text-severity-critical"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${verification.recovered ? "bg-severity-low" : "bg-severity-critical"}`} />
            {verification.recovered === null ? "Inconclusive" : verification.recovered ? "Recovered" : "Not recovered"}
          </span>
          <p className="mt-1.5 text-xs text-ink-tertiary">{formatDateTime(verification.checked_at)}</p>
          {verification.notes && <p className="mt-1 text-sm text-ink-tertiary">{verification.notes}</p>}
        </>
      ) : (
        <p className="text-sm text-ink-tertiary">{execution ? "Not checked yet" : "Waiting on execution"}</p>
      )}
      {error && <p className="mt-1.5 text-sm text-severity-critical">{error}</p>}
      {canVerify && (
        <div className="mt-2.5">
          <Button variant="primary" onClick={handleVerify} loading={loading}>
            Verify recovery
          </Button>
        </div>
      )}
    </StepShell>
  );
}
