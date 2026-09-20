import { api } from "./api-client";
import type { TokenResponse, UserResponse } from "./types";

/** POST /auth/register - app/api/v1/auth.py:register_user (JSON body: UserCreate) */
export function registerUser(email: string, password: string): Promise<UserResponse> {
  return api.post<UserResponse>("/auth/register", { email, password }, { skipAuth: true });
}

/**
 * POST /auth/login - app/api/v1/auth.py:login expects OAuth2 password-flow
 * form fields (username, password, grant_type), not JSON - it's declared
 * with FastAPI's Form(...), so the request must be
 * application/x-www-form-urlencoded to match.
 */
export function loginUser(email: string, password: string): Promise<TokenResponse> {
  const body = new URLSearchParams({ username: email, password, grant_type: "password" }).toString();
  return api.post<TokenResponse>("/auth/login", body, { form: true, skipAuth: true });
}
