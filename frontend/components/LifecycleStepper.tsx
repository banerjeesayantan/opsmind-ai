import { AlertTriangle, Check } from "lucide-react";
import type { IncidentStatus } from "@/lib/types";
import { LIFECYCLE_STAGES } from "@/lib/format";

/**
 * The incident lifecycle IS a real, fixed sequence (see IncidentStatus in
 * app/models/incident_enums.py), so a numbered/ordered rail is earned here
 * specifically - unlike a generic step indicator applied to content that
 * doesn't actually have an order.
 */
export function LifecycleStepper({ status }: { status: IncidentStatus }) {
  if (status === "unresolved") {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-severity-critical/30 bg-severity-critical/10 px-4 py-3">
        <AlertTriangle className="h-4 w-4 text-severity-critical" strokeWidth={2} aria-hidden="true" />
        <p className="text-sm font-medium text-severity-critical">Investigation did not reach a resolution</p>
      </div>
    );
  }

  const currentIndex = LIFECYCLE_STAGES.findIndex((s) => s.key === status);

  return (
    <ol className="flex items-center overflow-x-auto pb-1" aria-label="Incident lifecycle">
      {LIFECYCLE_STAGES.map((stage, i) => {
        const isDone = i < currentIndex;
        const isCurrent = i === currentIndex;
        const isLast = i === LIFECYCLE_STAGES.length - 1;
        return (
          <li key={stage.key} className="flex flex-shrink-0 items-center">
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold ${
                  isDone
                    ? "bg-accent text-white"
                    : isCurrent
                      ? "border-2 border-accent bg-base text-accent"
                      : "border border-border bg-surface-raised text-ink-tertiary"
                }`}
              >
                {isDone ? <Check className="h-3 w-3" strokeWidth={3} /> : i + 1}
              </div>
              <span className={`whitespace-nowrap text-[11px] font-medium ${isCurrent ? "text-ink" : "text-ink-tertiary"}`}>
                {stage.label}
              </span>
            </div>
            {!isLast && <div className={`mx-2 h-px w-8 flex-shrink-0 ${isDone ? "bg-accent" : "bg-border"}`} />}
          </li>
        );
      })}
    </ol>
  );
}
