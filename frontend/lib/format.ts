import type { ApprovalStatus, ExecutionStatus, HypothesisStatus, IncidentStatus, RiskLevel, Severity } from "./types";

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelative(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diffMs = d.getTime() - Date.now();
  const diffMin = Math.round(diffMs / 60000);
  const abs = Math.abs(diffMin);
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (abs < 60) return rtf.format(diffMin, "minute");
  if (abs < 60 * 24) return rtf.format(Math.round(diffMin / 60), "hour");
  return rtf.format(Math.round(diffMin / (60 * 24)), "day");
}

export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`;
}

// --- Lifecycle stages, in the exact order defined by IncidentStatus
// (app/models/incident_enums.py). UNRESOLVED is the failure-path terminal
// state, kept out of the normal forward rail and shown separately.
export const LIFECYCLE_STAGES: { key: IncidentStatus; label: string }[] = [
  { key: "new", label: "New" },
  { key: "investigating", label: "Investigating" },
  { key: "diagnosed", label: "Diagnosed" },
  { key: "awaiting_approval", label: "Awaiting approval" },
  { key: "remediating", label: "Remediating" },
  { key: "verifying", label: "Verifying" },
  { key: "resolved", label: "Resolved" },
];

export function statusLabel(status: IncidentStatus): string {
  if (status === "unresolved") return "Unresolved";
  return LIFECYCLE_STAGES.find((s) => s.key === status)?.label ?? status;
}

export function severityLabel(severity: Severity): string {
  return severity.charAt(0).toUpperCase() + severity.slice(1);
}

export function riskLabel(risk: RiskLevel): string {
  return risk.charAt(0).toUpperCase() + risk.slice(1);
}

export function approvalStatusLabel(status: ApprovalStatus): string {
  switch (status) {
    case "pending":
      return "Pending approval";
    case "approved":
      return "Approved";
    case "rejected":
      return "Rejected";
    case "not_required":
      return "Auto-approved (low risk)";
  }
}

export function executionStatusLabel(status: ExecutionStatus): string {
  switch (status) {
    case "pending":
      return "Pending";
    case "succeeded":
      return "Succeeded";
    case "failed":
      return "Failed";
    case "simulated":
      return "Simulated";
  }
}

export function hypothesisStatusLabel(status: HypothesisStatus): string {
  switch (status) {
    case "proposed":
      return "Proposed";
    case "validated":
      return "Validated";
    case "rejected":
      return "Rejected";
  }
}

export function actionTypeLabel(actionType: string): string {
  return actionType
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/**
 * The service an incident was opened for. The backend doesn't return it on the incident itself, but
 * it records it in the metadata of the incident's first timeline event ("incident_created"), so we
 * read it from there - real data, nothing assumed.
 */
export function serviceFromTimeline(entries: { event_type: string; event_metadata: Record<string, unknown> | null }[] | null): string | null {
  if (!entries) return null;
  for (const entry of entries) {
    const service = entry.event_metadata?.["service"];
    if (entry.event_type === "incident_created" && typeof service === "string" && service) return service;
  }
  return null;
}
