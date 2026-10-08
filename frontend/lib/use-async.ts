"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api-client";

interface AsyncState<T> {
  data: T | null;
  error: string | null;
  /** True only while there is nothing to show yet (first load, or a different `deps` key). */
  loading: boolean;
  /** True while re-fetching after `reload()` with the previous data still on screen. */
  refreshing: boolean;
  reload: () => void;
}

/**
 * Runs `fn` on mount (and whenever `deps` changes) and tracks loading/data/error state.
 *
 * `reload()` is stale-while-revalidate: the existing data stays rendered while the refetch is in
 * flight, so a page doesn't blank out to a spinner (and lose form state / scroll position) every
 * time the user approves, executes or verifies something. Changing `deps` (e.g. navigating to a
 * different incident) does reset to the loading state, so one incident's data is never shown
 * under another's id.
 *
 * A 401 is deliberately NOT surfaced as a page-level error - api-client's unauthorized handler
 * already redirects to /login, so showing it here too would just flash a duplicate banner.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const depsKey = JSON.stringify(deps);
  const [state, setState] = useState<{ key: string; data: T | null }>({ key: depsKey, data: null });
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const data = state.key === depsKey ? state.data : null;

  useEffect(() => {
    let cancelled = false;
    setFetching(true);
    setError(null);
    fnRef.current()
      .then((result) => {
        if (!cancelled) setState({ key: depsKey, data: result });
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return;
        setError(err instanceof Error ? err.message : "Something went wrong.");
      })
      .finally(() => {
        if (!cancelled) setFetching(false);
      });
    return () => {
      cancelled = true;
    };
  }, [depsKey, reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  return { data, error, loading: fetching && data === null, refreshing: fetching && data !== null, reload };
}
