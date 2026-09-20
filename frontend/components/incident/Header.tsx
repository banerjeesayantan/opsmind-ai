import Link from "next/link";
import type { IncidentResponse } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { SeverityBadge, StatusBadge } from "@/components/badges";
import { LifecycleStepper } from "@/components/LifecycleStepper";

export function IncidentHeader({ incident }: { incident: IncidentResponse }) {
  return (
    <div className="border-b border-border bg-surface px-8 py-6">
      <Link href="/incidents" className="mb-3 inline-flex items-center gap-1.5 text-sm text-ink-tertiary hover:text-ink">
        <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12.5 15 7.5 10l5-5" />
        </svg>
        Incidents
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-semibold text-ink">{incident.title}</h1>
            <SeverityBadge severity={incident.severity} />
            <StatusBadge status={incident.status} />
          </div>
          <div className="mt-1.5 flex items-center gap-3 text-sm text-ink-tertiary">
            <span className="font-mono">{incident.id}</span>
            <span>&middot;</span>
            <span>Opened {formatDateTime(incident.created_at)}</span>
            {incident.resolved_at && (
              <>
                <span>&middot;</span>
                <span>Resolved {formatDateTime(incident.resolved_at)}</span>
              </>
            )}
          </div>
          {incident.description && <p className="mt-3 max-w-2xl text-sm text-ink-secondary">{incident.description}</p>}
        </div>
      </div>

      <div className="mt-6">
        <LifecycleStepper status={incident.status} />
      </div>
    </div>
  );
}
