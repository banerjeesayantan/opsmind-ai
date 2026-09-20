"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "./api-client";

interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/**
 * Runs `fn` on mount (and whenever `deps` changes) and tracks
 * loading/data/error state for it. A 401 is deliberately NOT surfaced as
 * a page-level error here - api-client's onUnauthorized handler already
 * redirects to /login in that case, so surfacing it here too would just
 * flash a duplicate error banner during the redirect.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fn()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return;
        setError(err instanceof Error ? err.message : "Something went wrong.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadKey]);

  useEffect(() => load(), [load]);

  return { data, error, loading, reload: () => setReloadKey((k) => k + 1) };
}
