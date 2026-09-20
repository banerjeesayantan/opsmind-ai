"use client";

import { ButtonHTMLAttributes, InputHTMLAttributes, LabelHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

// --- Button ------------------------------------------------------------------

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  loading?: boolean;
}

export function Button({ variant = "secondary", loading, className = "", children, disabled, ...rest }: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition-colors duration-100 disabled:cursor-not-allowed disabled:opacity-50";
  const variants: Record<string, string> = {
    primary: "bg-accent text-white hover:bg-accent-hover",
    secondary: "bg-surface-raised text-ink border border-border hover:bg-surface-hover",
    danger: "bg-severity-critical/90 text-white hover:bg-severity-critical",
    ghost: "text-ink-secondary hover:text-ink hover:bg-surface-hover",
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} disabled={disabled || loading} {...rest}>
      {loading && <Spinner size={14} />}
      {children}
    </button>
  );
}

// --- Card ---------------------------------------------------------------------

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-border bg-surface shadow-panel ${className}`}>{children}</div>
  );
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border-subtle px-5 py-4">
      <div>
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {subtitle && <p className="mt-0.5 text-sm text-ink-tertiary">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

// --- Form fields ---------------------------------------------------------------

export function Label(props: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label {...props} className={`mb-1.5 block text-sm font-medium text-ink-secondary ${props.className ?? ""}`} />;
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink placeholder:text-ink-tertiary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50 ${props.className ?? ""}`}
    />
  );
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink placeholder:text-ink-tertiary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50 ${props.className ?? ""}`}
    />
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50 ${props.className ?? ""}`}
    />
  );
}

export function FieldError({ children }: { children?: ReactNode }) {
  if (!children) return null;
  return <p className="mt-1.5 text-sm text-severity-critical">{children}</p>;
}

// --- Spinner --------------------------------------------------------------------

export function Spinner({ size = 20, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      className={`animate-spin ${className}`}
      style={{ width: size, height: size }}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

// --- Page-level states ------------------------------------------------------------

export function PageLoading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-3 text-ink-tertiary">
      <Spinner size={22} />
      <p className="text-sm">{label}…</p>
    </div>
  );
}

export function ErrorBanner({ title = "Something went wrong", message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-lg border border-severity-critical/30 bg-severity-critical/10 px-4 py-3.5">
      <div className="flex gap-3">
        <svg className="mt-0.5 h-4 w-4 flex-shrink-0 text-severity-critical" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.63-1.516 2.63H3.72c-1.347 0-2.189-1.463-1.516-2.63L8.485 2.495ZM10 6a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 6Zm0 8a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
            clipRule="evenodd"
          />
        </svg>
        <div>
          <p className="text-sm font-medium text-ink">{title}</p>
          <p className="mt-0.5 text-sm text-ink-secondary">{message}</p>
        </div>
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry} className="flex-shrink-0">
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  message,
  action,
  icon,
}: {
  title: string;
  message: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border px-6 py-14 text-center">
      {icon ?? (
        <svg className="h-8 w-8 text-ink-tertiary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2Z" />
        </svg>
      )}
      <div>
        <p className="text-sm font-medium text-ink">{title}</p>
        <p className="mt-1 max-w-sm text-sm text-ink-tertiary">{message}</p>
      </div>
      {action}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-surface-raised ${className}`} />;
}
