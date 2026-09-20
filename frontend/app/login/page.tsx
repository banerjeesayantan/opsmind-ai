"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api-client";
import { Button, ErrorBanner, Input, Label } from "@/components/ui";

function LoginForm() {
  const { login, isAuthenticated } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const expired = params.get("reason") === "expired";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) router.replace("/dashboard");
  }, [isAuthenticated, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? "That email or password isn't right." : err.message);
      } else {
        setError("Something went wrong. Try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-base px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-sm font-bold text-white">O</div>
          <div>
            <h1 className="text-lg font-semibold text-ink">Sign in to OpsMind</h1>
            <p className="mt-1 text-sm text-ink-tertiary">Investigate and resolve incidents faster</p>
          </div>
        </div>

        {expired && !error && (
          <div className="mb-4">
            <ErrorBanner title="Your session ended" message="Sign in again to keep going." />
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-border bg-surface p-6">
          {error && <ErrorBanner message={error} />}

          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </div>

          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          <Button type="submit" variant="primary" className="w-full" loading={loading}>
            Sign in
          </Button>
        </form>

        <p className="mt-5 text-center text-sm text-ink-tertiary">
          New to OpsMind?{" "}
          <Link href="/register" className="font-medium text-accent hover:text-accent-hover">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
