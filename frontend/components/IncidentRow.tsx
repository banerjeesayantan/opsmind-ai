import Link from "next/link";
import type { IncidentResponse } from "@/lib/types";
import { formatRelative } from "@/lib/format";
import { SeverityBadge, StatusBadge } from "./badges";

export function IncidentRow({ incident }: { incident: IncidentResponse }) {
  return (
    <Link
      href={`/incidents/${incident.id}`}
      className="flex items-center gap-4 border-b border-border-subtle px-5 py-3.5 transition-colors last:border-b-0 hover:bg-surface-hover"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">{incident.title}</p>
        <p className="mt-0.5 truncate font-mono text-xs text-ink-tertiary">{incident.id}</p>
      </div>
      <SeverityBadge severity={incident.severity} />
      <StatusBadge status={incident.status} />
      <span className="w-20 flex-shrink-0 text-right text-xs text-ink-tertiary">{formatRelative(incident.created_at)}</span>
    </Link>
  );
}
