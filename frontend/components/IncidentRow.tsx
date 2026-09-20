import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { IncidentResponse } from "@/lib/types";
import { formatRelative } from "@/lib/format";
import { SeverityBadge, StatusBadge } from "./badges";

export function IncidentRow({ incident }: { incident: IncidentResponse }) {
  return (
    <Link
      href={`/incidents/${incident.id}`}
      className="flex items-center gap-3 border-b border-border-subtle px-5 py-3.5 transition-colors last:border-b-0 hover:bg-surface-hover sm:gap-4"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">{incident.title}</p>
        <p className="mt-0.5 truncate font-mono text-xs text-ink-tertiary">{incident.id}</p>
      </div>
      <div className="flex flex-shrink-0 items-center gap-2 sm:gap-3">
        <SeverityBadge severity={incident.severity} />
        <StatusBadge status={incident.status} />
        <span className="hidden w-20 flex-shrink-0 text-right text-xs text-ink-tertiary sm:inline">
          {formatRelative(incident.created_at)}
        </span>
        <ChevronRight className="h-4 w-4 flex-shrink-0 text-ink-tertiary" strokeWidth={2} aria-hidden="true" />
      </div>
    </Link>
  );
}
