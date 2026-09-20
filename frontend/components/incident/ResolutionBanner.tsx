import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { IncidentStatus } from "@/lib/types";

export function ResolutionBanner({ status }: { status: IncidentStatus }) {
  if (status === "resolved") {
    return (
      <div className="flex items-center gap-2.5 rounded-lg border border-severity-low/30 bg-severity-low/10 px-4 py-3">
        <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-severity-low" strokeWidth={2} aria-hidden="true" />
        <p className="text-sm font-medium text-severity-low">This incident is resolved &mdash; verification confirmed recovery.</p>
      </div>
    );
  }
  if (status === "unresolved") {
    return (
      <div className="flex items-center gap-2.5 rounded-lg border border-severity-critical/30 bg-severity-critical/10 px-4 py-3">
        <AlertTriangle className="h-4 w-4 flex-shrink-0 text-severity-critical" strokeWidth={2} aria-hidden="true" />
        <p className="text-sm font-medium text-severity-critical">This incident is unresolved. Investigation did not reach a confirmed fix.</p>
      </div>
    );
  }
  return null;
}
