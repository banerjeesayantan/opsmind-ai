import type { ApprovalStatus, ExecutionStatus, HypothesisStatus, IncidentStatus, RiskLevel, Severity } from "@/lib/types";
import {
  approvalStatusLabel,
  executionStatusLabel,
  hypothesisStatusLabel,
  riskLabel,
  severityLabel,
  statusLabel,
} from "@/lib/format";

function Dot({ className }: { className: string }) {
  return <span className={`h-1.5 w-1.5 rounded-full ${className}`} />;
}

function Badge({ children, dotClassName, textClassName }: { children: React.ReactNode; dotClassName: string; textClassName: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-raised px-2.5 py-1 text-xs font-medium ${textClassName}`}>
      <Dot className={dotClassName} />
      {children}
    </span>
  );
}

const STATUS_STYLE: Record<IncidentStatus, { dot: string; text: string }> = {
  new: { dot: "bg-status-new", text: "text-ink-secondary" },
  investigating: { dot: "bg-status-progress", text: "text-accent" },
  diagnosed: { dot: "bg-status-progress", text: "text-accent" },
  awaiting_approval: { dot: "bg-status-waiting", text: "text-severity-high" },
  remediating: { dot: "bg-status-progress", text: "text-accent" },
  verifying: { dot: "bg-status-progress", text: "text-accent" },
  resolved: { dot: "bg-status-resolved", text: "text-severity-low" },
  unresolved: { dot: "bg-status-unresolved", text: "text-severity-critical" },
};

export function StatusBadge({ status }: { status: IncidentStatus }) {
  const style = STATUS_STYLE[status];
  return (
    <Badge dotClassName={style.dot} textClassName={style.text}>
      {statusLabel(status)}
    </Badge>
  );
}

const SEVERITY_STYLE: Record<Severity, { dot: string; text: string }> = {
  critical: { dot: "bg-severity-critical", text: "text-severity-critical" },
  high: { dot: "bg-severity-high", text: "text-severity-high" },
  medium: { dot: "bg-severity-medium", text: "text-severity-medium" },
  low: { dot: "bg-severity-low", text: "text-severity-low" },
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const style = SEVERITY_STYLE[severity];
  return (
    <Badge dotClassName={style.dot} textClassName={style.text}>
      {severityLabel(severity)}
    </Badge>
  );
}

const RISK_STYLE: Record<RiskLevel, { dot: string; text: string }> = {
  high: { dot: "bg-risk-high", text: "text-risk-high" },
  medium: { dot: "bg-risk-medium", text: "text-risk-medium" },
  low: { dot: "bg-risk-low", text: "text-risk-low" },
};

export function RiskBadge({ risk }: { risk: RiskLevel }) {
  const style = RISK_STYLE[risk];
  return (
    <Badge dotClassName={style.dot} textClassName={style.text}>
      {riskLabel(risk)} risk
    </Badge>
  );
}

const APPROVAL_STYLE: Record<ApprovalStatus, { dot: string; text: string }> = {
  pending: { dot: "bg-status-waiting", text: "text-severity-high" },
  approved: { dot: "bg-status-resolved", text: "text-severity-low" },
  rejected: { dot: "bg-status-unresolved", text: "text-severity-critical" },
  not_required: { dot: "bg-ink-tertiary", text: "text-ink-tertiary" },
};

export function ApprovalBadge({ status }: { status: ApprovalStatus }) {
  const style = APPROVAL_STYLE[status];
  return (
    <Badge dotClassName={style.dot} textClassName={style.text}>
      {approvalStatusLabel(status)}
    </Badge>
  );
}

const EXECUTION_STYLE: Record<ExecutionStatus, { dot: string; text: string }> = {
  pending: { dot: "bg-status-waiting", text: "text-severity-high" },
  succeeded: { dot: "bg-status-resolved", text: "text-severity-low" },
  simulated: { dot: "bg-status-progress", text: "text-accent" },
  failed: { dot: "bg-status-unresolved", text: "text-severity-critical" },
};

export function ExecutionBadge({ status }: { status: ExecutionStatus }) {
  const style = EXECUTION_STYLE[status];
  return (
    <Badge dotClassName={style.dot} textClassName={style.text}>
      {executionStatusLabel(status)}
    </Badge>
  );
}

const HYPOTHESIS_STYLE: Record<HypothesisStatus, { dot: string; text: string }> = {
  proposed: { dot: "bg-ink-tertiary", text: "text-ink-tertiary" },
  validated: { dot: "bg-status-resolved", text: "text-severity-low" },
  rejected: { dot: "bg-status-unresolved", text: "text-severity-critical" },
};

export function HypothesisBadge({ status }: { status: HypothesisStatus }) {
  const style = HYPOTHESIS_STYLE[status];
  return (
    <Badge dotClassName={style.dot} textClassName={style.text}>
      {hypothesisStatusLabel(status)}
    </Badge>
  );
}
