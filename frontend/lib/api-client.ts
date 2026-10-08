/**
 * A single, thin wrapper around fetch for talking to the OpsMind FastAPI
 * backend. Every request in the app goes through here - the browser never
 * calls Groq/OpenAI or any other LLM provider directly, and no LLM
 * provider key is ever read, stored, or referenced in frontend code.
 *
 * NEXT_PUBLIC_API_BASE_URL is not a secret: it's the public address of
 * our own API (the same way a REST client needs to know a hostname), not
 * a credential. The only credential the browser ever holds is the user's
 * own JWT, obtained by that same user logging in.
 */
import type { ApiErrorBody } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

const TOKEN_STORAGE_KEY = "opsmind_access_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

/**
 * Thrown for any non-2xx response. Callers that care about auth failures
 * specifically should check `status === 401`.
 */
export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | null;

  constructor(status: number, body: ApiErrorBody | null, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/** Fired whenever a request comes back 401 - used to force a sign-out. */
type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler;
}

function messageFromBody(body: ApiErrorBody | null, fallback: string): string {
  if (!body) return fallback;
  if (body.detail && !(body.errors && body.errors.length > 0)) return body.detail;
  if (body.errors && body.errors.length > 0) {
    // Backend validation messages look like "Value error, Password must contain ...".
    // Drop pydantic's boilerplate prefix, and only prefix the field name when the
    // message doesn't already say what it's about.
    return body.errors
      .map((e) => {
        const msg = e.message.replace(/^Value error,\s*/i, "");
        return msg.toLowerCase().includes(e.field.toLowerCase()) ? msg : `${e.field}: ${msg}`;
      })
      .join("; ");
  }
  return body.detail ?? fallback;
}

/**
 * The backend reports a bad session in three different ways (see get_current_user in
 * app/api/v1/auth.py): 401 for a missing/expired/invalid token, 422 "Invalid token format"
 * for a malformed one, and 404 "User not found" for a valid token whose user no longer exists.
 * All three mean the stored token is unusable and the user has to sign in again.
 */
function isInvalidSession(status: number, body: ApiErrorBody | null): boolean {
  if (status === 401) return true;
  if (status === 404 && body?.detail === "User not found") return true;
  if (status === 422 && body?.detail === "Invalid token format") return true;
  return false;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** Send as application/x-www-form-urlencoded instead of JSON (the login endpoint uses OAuth2 form fields). */
  form?: boolean;
  /** Skip attaching the bearer token (only /auth/register and /auth/login need this). */
  skipAuth?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, form = false, skipAuth = false } = options;

  const headers: Record<string, string> = {};
  let sentToken = false;
  if (body !== undefined) {
    headers["Content-Type"] = form ? "application/x-www-form-urlencoded" : "application/json";
  }
  if (!skipAuth) {
    const token = getStoredToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
      sentToken = true;
    }
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : form ? (body as string) : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, null, "Could not reach the OpsMind API. Check your connection and try again.");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  let parsed: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = null;
    }
  }

  if (!response.ok) {
    const errorBody = parsed as ApiErrorBody | null;
    if (!skipAuth && (sentToken || response.status === 401) && isInvalidSession(response.status, errorBody)) {
      onUnauthorized?.();
    }
    if (response.status === 429) {
      throw new ApiError(429, errorBody, "Too many requests. Wait a moment and try again.");
    }
    throw new ApiError(response.status, errorBody, messageFromBody(errorBody, `Request failed (${response.status})`));
  }

  return parsed as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown, opts?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...opts, method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
