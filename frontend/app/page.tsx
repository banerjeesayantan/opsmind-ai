"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { PageLoading } from "@/components/ui";

export default function RootPage() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated === true) router.replace("/dashboard");
    if (isAuthenticated === false) router.replace("/login");
  }, [isAuthenticated, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-base">
      <PageLoading />
    </div>
  );
}
