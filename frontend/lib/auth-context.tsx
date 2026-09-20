"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, getStoredToken, setStoredToken, setUnauthorizedHandler } from "./api-client";
import { loginUser, registerUser } from "./auth-api";

const EMAIL_STORAGE_KEY = "opsmind_user_email";

interface AuthContextValue {
  /** null while the initial localStorage check is happening. */
  isAuthenticated: boolean | null;
  email: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    setIsAuthenticated(!!token);
    setEmail(window.localStorage.getItem(EMAIL_STORAGE_KEY));
  }, []);

  const logout = useCallback(() => {
    setStoredToken(null);
    window.localStorage.removeItem(EMAIL_STORAGE_KEY);
    setIsAuthenticated(false);
    setEmail(null);
    router.push("/login");
  }, [router]);

  // Any 401 from the API (expired/invalid token) forces a clean sign-out
  // rather than leaving the UI stuck showing data behind a dead session.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setStoredToken(null);
      window.localStorage.removeItem(EMAIL_STORAGE_KEY);
      setIsAuthenticated(false);
      setEmail(null);
      router.push("/login?reason=expired");
    });
    return () => setUnauthorizedHandler(null);
  }, [router]);

  const login = useCallback(async (loginEmail: string, password: string) => {
    const result = await loginUser(loginEmail, password);
    setStoredToken(result.access_token);
    window.localStorage.setItem(EMAIL_STORAGE_KEY, loginEmail);
    setEmail(loginEmail);
    setIsAuthenticated(true);
  }, []);

  const register = useCallback(async (registerEmail: string, password: string) => {
    const result = await registerUser(registerEmail, password);
    setStoredToken(result.token.access_token);
    window.localStorage.setItem(EMAIL_STORAGE_KEY, result.email);
    setEmail(result.email);
    setIsAuthenticated(true);
  }, []);

  const value = useMemo(
    () => ({ isAuthenticated, email, login, register, logout }),
    [isAuthenticated, email, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

/** Re-exported so callers that only need to classify an error don't need to import api-client directly. */
export { ApiError };
