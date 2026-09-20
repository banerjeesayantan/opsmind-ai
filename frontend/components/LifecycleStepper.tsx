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
        <svg className="h-4 w-4 text-severity-critical" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.63-1.516 2.63H3.72c-1.347 0-2.189-1.463-1.516-2.63L8.485 2.495ZM10 6a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 6Zm0 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
            clipRule="evenodd"
          />
        </svg>
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
                {isDone ? (
                  <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M16.704 5.29a1 1 0 0 1 .006 1.415l-7.5 7.6a1 1 0 0 1-1.42.005l-3.5-3.5a1 1 0 1 1 1.414-1.414l2.796 2.796 6.79-6.876a1 1 0 0 1 1.414-.026Z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : (
                  i + 1
                )}
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
