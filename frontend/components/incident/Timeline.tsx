import type { TimelineEntryResponse } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { Card, CardHeader, EmptyState, ErrorBanner, Skeleton } from "@/components/ui";

export function TimelineSection({
  entries,
  loading,
  error,
}: {
  entries: TimelineEntryResponse[] | null;
  loading: boolean;
  error: string | null;
}) {
  return (
    <Card>
      <CardHeader title="Timeline" subtitle="Everything that's happened on this incident, in order" />
      <div className="px-5 py-4">
        {loading && (
          <div className="space-y-3">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        )}
        {!loading && error && <ErrorBanner message={error} />}
        {!loading && !error && entries && entries.length === 0 && (
          <EmptyState title="No timeline entries yet" message="Events will appear here as the incident progresses." />
        )}
        {!loading && !error && entries && entries.length > 0 && (
          <ol className="space-y-0">
            {[...entries]
              .sort((a, b) => new Date(a.occurred_at).getTime() - new Date(b.occurred_at).getTime())
              .map((entry, i, arr) => (
                <li key={entry.id} className="relative flex gap-3 pb-4 last:pb-0">
                  <div className="flex flex-col items-center">
                    <span className="mt-1 h-2 w-2 flex-shrink-0 rounded-full bg-accent" />
                    {i < arr.length - 1 && <span className="mt-1 w-px flex-1 bg-border" />}
                  </div>
                  <div className="min-w-0 flex-1 pb-1">
                    <p className="text-sm text-ink">{entry.description}</p>
                    <p className="mt-0.5 font-mono text-xs text-ink-tertiary">{formatDateTime(entry.occurred_at)}</p>
                  </div>
                </li>
              ))}
          </ol>
        )}
      </div>
    </Card>
  );
}
