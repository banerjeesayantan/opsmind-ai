"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AlertTriangle, LayoutDashboard, LogOut, Menu, X } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { PageLoading } from "./ui";

// Nav is intentionally limited to routes that exist and are wired to a
// real backend feature - no "Reports"/"Settings" placeholders for
// functionality the API doesn't have yet.
const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, email, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    if (isAuthenticated === false) {
      router.replace("/login");
    }
  }, [isAuthenticated, router]);

  // Close the mobile nav on route changes rather than leaving it open
  // over the newly-navigated page.
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

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
      {/* Mobile top bar: only the menu toggle + wordmark, shown below md */}
      <div className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-surface px-4 md:hidden">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-accent text-xs font-bold text-white">O</div>
          <span className="text-sm font-semibold tracking-tight text-ink">OpsMind</span>
        </div>
        <button
          onClick={() => setMobileNavOpen((v) => !v)}
          aria-label={mobileNavOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={mobileNavOpen}
          className="rounded-md p-2 text-ink-secondary hover:bg-surface-hover hover:text-ink"
        >
          {mobileNavOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-20 bg-black/60 md:hidden" onClick={() => setMobileNavOpen(false)} aria-hidden="true" />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-20 flex w-60 flex-shrink-0 flex-col border-r border-border bg-surface transition-transform duration-150 md:static md:translate-x-0 ${
          mobileNavOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="hidden h-14 items-center gap-2 border-b border-border px-5 md:flex">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-accent text-xs font-bold text-white">O</div>
          <span className="text-sm font-semibold tracking-tight text-ink">OpsMind</span>
        </div>
        <div className="h-14 flex-shrink-0 md:hidden" aria-hidden="true" />

        <nav className="flex-1 space-y-0.5 px-3 py-4" aria-label="Primary">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  active ? "bg-accent-muted text-accent" : "text-ink-secondary hover:bg-surface-hover hover:text-ink"
                }`}
              >
                <Icon className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
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
            </div>
            <button
              onClick={logout}
              className="flex-shrink-0 rounded-md p-1.5 text-ink-tertiary transition-colors hover:bg-surface-hover hover:text-ink"
              title="Sign out"
              aria-label="Sign out"
            >
              <LogOut className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
            </button>
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto pt-14 md:pt-0">{children}</main>
    </div>
  );
}
