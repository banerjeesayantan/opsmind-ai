"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { PageLoading } from "./ui";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: DashboardIcon },
  { href: "/incidents", label: "Incidents", icon: IncidentsIcon },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, email, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (isAuthenticated === false) {
      router.replace("/login");
    }
  }, [isAuthenticated, router]);

  if (isAuthenticated === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-base">
        <PageLoading label="Checking your session" />
      </div>
    );
  }

  if (isAuthenticated === false) {
    // Redirect is in flight; render nothing rather than a flash of protected content.
    return null;
  }

  return (
    <div className="flex min-h-screen bg-base">
      <aside className="flex w-60 flex-shrink-0 flex-col border-r border-border bg-surface">
        <div className="flex h-14 items-center gap-2 border-b border-border px-5">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-accent text-xs font-bold text-white">O</div>
          <span className="text-sm font-semibold tracking-tight text-ink">OpsMind</span>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-4">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  active ? "bg-accent-muted text-accent" : "text-ink-secondary hover:bg-surface-hover hover:text-ink"
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-border p-3">
          <div className="flex items-center justify-between gap-2 rounded-md px-2 py-2">
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-ink" title={email ?? undefined}>
                {email ?? "Signed in"}
              </p>
              <p className="text-[11px] text-ink-tertiary">On-call engineer</p>
            </div>
            <button
              onClick={logout}
              className="flex-shrink-0 rounded-md p-1.5 text-ink-tertiary transition-colors hover:bg-surface-hover hover:text-ink"
              title="Sign out"
              aria-label="Sign out"
            >
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 15.5H5.5A1.5 1.5 0 0 1 4 14V6a1.5 1.5 0 0 1 1.5-1.5H8M13 13.5 16.5 10 13 6.5M16.5 10H8" />
              </svg>
            </button>
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

function DashboardIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h5V3H3v7Zm0 7h5v-4H3v4Zm9 0h5v-7h-5v7Zm0-14v4h5V3h-5Z" />
    </svg>
  );
}

function IncidentsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 2 2 17h16L10 2Zm0 6v4m0 3h.01" />
    </svg>
  );
}
