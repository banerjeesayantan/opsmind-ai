"use client";

import { KeyboardEvent, useRef } from "react";

export interface TabItem {
  key: string;
  label: string;
  icon?: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  /** Optional small count badge, e.g. number of hypotheses - only ever real data. */
  count?: number;
}

export function Tabs({
  items,
  active,
  onChange,
}: {
  items: TabItem[];
  active: string;
  onChange: (key: string) => void;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const idx = items.findIndex((i) => i.key === active);
    if (idx === -1) return;
    let nextIdx: number | null = null;
    if (e.key === "ArrowRight") nextIdx = (idx + 1) % items.length;
    if (e.key === "ArrowLeft") nextIdx = (idx - 1 + items.length) % items.length;
    if (e.key === "Home") nextIdx = 0;
    if (e.key === "End") nextIdx = items.length - 1;
    if (nextIdx !== null) {
      e.preventDefault();
      const nextItem = items[nextIdx];
      if (!nextItem) return;
      onChange(nextItem.key);
      refs.current[nextItem.key]?.focus();
    }
  }

  return (
    <div
      role="tablist"
      aria-label="Incident sections"
      onKeyDown={handleKeyDown}
      className="flex gap-1 overflow-x-auto border-b border-border"
    >
      {items.map((item) => {
        const isActive = item.key === active;
        const Icon = item.icon;
        return (
          <button
            key={item.key}
            ref={(el) => {
              refs.current[item.key] = el;
            }}
            role="tab"
            id={`tab-${item.key}`}
            aria-selected={isActive}
            aria-controls={`tabpanel-${item.key}`}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onChange(item.key)}
            className={`flex flex-shrink-0 items-center gap-1.5 border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors ${
              isActive
                ? "border-accent text-ink"
                : "border-transparent text-ink-tertiary hover:border-border-strong hover:text-ink-secondary"
            }`}
          >
            {Icon && <Icon className="h-3.5 w-3.5" strokeWidth={2} />}
            {item.label}
            {typeof item.count === "number" && item.count > 0 && (
              <span
                className={`ml-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-semibold tabular-nums ${
                  isActive ? "bg-accent-muted text-accent" : "bg-surface-raised text-ink-tertiary"
                }`}
              >
                {item.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export function TabPanel({ tabKey, active, children }: { tabKey: string; active: string; children: React.ReactNode }) {
  if (tabKey !== active) return null;
  return (
    <div role="tabpanel" id={`tabpanel-${tabKey}`} aria-labelledby={`tab-${tabKey}`} className="animate-fade-in">
      {children}
    </div>
  );
}
