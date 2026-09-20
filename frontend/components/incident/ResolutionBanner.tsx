import type { IncidentStatus } from "@/lib/types";

export function ResolutionBanner({ status }: { status: IncidentStatus }) {
  if (status === "resolved") {
    return (
      <div className="flex items-center gap-2.5 rounded-lg border border-severity-low/30 bg-severity-low/10 px-4 py-3">
        <svg className="h-4 w-4 flex-shrink-0 text-severity-low" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M16.704 5.29a1 1 0 0 1 .006 1.415l-7.5 7.6a1 1 0 0 1-1.42.005l-3.5-3.5a1 1 0 1 1 1.414-1.414l2.796 2.796 6.79-6.876a1 1 0 0 1 1.414-.026Z"
            clipRule="evenodd"
          />
        </svg>
        <p className="text-sm font-medium text-severity-low">This incident is resolved &mdash; verification confirmed recovery.</p>
      </div>
    );
  }
  if (status === "unresolved") {
    return (
      <div className="flex items-center gap-2.5 rounded-lg border border-severity-critical/30 bg-severity-critical/10 px-4 py-3">
        <svg className="h-4 w-4 flex-shrink-0 text-severity-critical" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.63-1.516 2.63H3.72c-1.347 0-2.189-1.463-1.516-2.63L8.485 2.495ZM10 6a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 6Zm0 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
            clipRule="evenodd"
          />
        </svg>
        <p className="text-sm font-medium text-severity-critical">This incident is unresolved. Investigation did not reach a confirmed fix.</p>
      </div>
    );
  }
  return null;
}
