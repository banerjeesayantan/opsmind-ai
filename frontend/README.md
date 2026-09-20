# OpsMind AI — Frontend

Next.js 15 (App Router) + React 19 + TypeScript client for the OpsMind AI
incident investigation and response platform. Talks only to the OpsMind
FastAPI backend under `../app` — never to Groq/OpenAI or any other LLM
provider directly.

## Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local   # point NEXT_PUBLIC_API_BASE_URL at your backend
npm run dev
```

Requires the backend running separately (see the repo root `README.md`),
with `ALLOWED_ORIGINS` in its settings including `http://localhost:3000`
(the backend's CORS default is permissive in development).

## Scripts

- `npm run dev` — local dev server
- `npm run build` — production build
- `npm run start` — serve a production build
- `npm run lint` — ESLint (`next/core-web-vitals`)
- `npm run typecheck` — `tsc --noEmit`

## Structure

```
app/                    Routes (App Router)
  login/, register/     Public auth pages
  dashboard/            Authenticated home - stats derived from GET /incidents
  incidents/            List + create-incident flow
  incidents/[id]/       Incident detail workspace (investigation through resolution)
components/             Reusable UI: primitives (ui.tsx), badges, shell, per-incident sections
lib/
  api-client.ts         Thin fetch wrapper: bearer token, error shape, 401 -> sign-out
  auth-api.ts            /auth/register, /auth/login
  incidents-api.ts       Every /incidents/* route, 1:1 with app/api/v1/incidents.py
  auth-context.tsx       React context: session state, login/register/logout
  types.ts                TypeScript types mirroring the backend's Pydantic schemas exactly
  format.ts               Display formatting (dates, status/severity labels, lifecycle order)
  use-async.ts            Small hook for consistent loading/error/data state
```

## Auth model

- The backend issues a JWT (`POST /auth/register`, `POST /auth/login`). The frontend stores it
  in `localStorage` and attaches it as `Authorization: Bearer <token>` on every request via
  `lib/api-client.ts` — there is no second, parallel auth system.
- A `401` response from any request triggers an automatic, app-wide sign-out and redirect to
  `/login?reason=expired` (`lib/auth-context.tsx`'s `onUnauthorized` handler).
- `components/AppShell.tsx` guards every authenticated route: it redirects to `/login` if there's
  no session, and renders nothing while that redirect is in flight (no flash of protected content).
- No LLM provider key, database credential, or other backend secret is ever read, stored, or
  referenced in frontend code — `NEXT_PUBLIC_API_BASE_URL` is the only environment variable the
  browser sees, and it's a public hostname, not a credential.

## A note on incident detail layout

The backend's `GET /incidents/{id}` returns the entire investigation/response picture in one
`IncidentResultsResponse` (hypotheses, diagnosis, remediations, approvals, executions,
verifications together) — there's no per-stage endpoint. The detail page mirrors that: it's one
page with clearly separated sections in lifecycle order (Investigation → Evidence → Remediation →
Timeline), rather than artificially splitting the workflow across separate routes that would need
to re-fetch and lose context between them. Each remediation's approval, execution, and
verification are grouped together as one pipeline card, matching how those rows actually relate
in the data model (`approvals`/`action_executions` link to a `remediation_id`;
`verifications` link to an `action_execution_id`).
