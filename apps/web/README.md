# AQOS Web

The AQOS console. A foundation: the shell, the API client and the guards, with
placeholder screens where the feature views will go.

## Configuration

Three public values are required. Copy `.env.example` to `.env.local` and set
them, or supply them in the environment:

| Variable | Meaning |
| --- | --- |
| `NEXT_PUBLIC_AQOS_WEB_API_BASE_URL` | Absolute origin of the AQOS HTTP API |
| `NEXT_PUBLIC_AQOS_WEB_APP_NAME` | Name shown in the header and the tab |
| `NEXT_PUBLIC_AQOS_WEB_ENV` | `development`, `test`, `staging` or `production` |

Everything here is compiled into the browser bundle, so nothing secret may go
in it — no database URL, no API key, no credential. A public variable whose
name looks like a secret is rejected at startup rather than shipped.

**A build without these values fails on purpose.** A build that guessed would
produce an app that looks healthy while every request goes nowhere, and a
`staging` or `production` build pointed at localhost is refused for the same
reason.

## Scripts

```
npm run lint       # eslint, no warnings tolerated
npm run typecheck  # tsc --noEmit, strict
npm test           # vitest
npm run build      # next build (needs the variables above)
npm run dev        # local development server
```

## What this app deliberately cannot do

The backend exposes 21 write endpoints. This app reaches two of them — login
and logout — and nothing else. There is no order form, no signal action, no
session control and no account mutation, and `src/test/guards.test.ts` fails
the build if one appears.

It also never opens a database, never imports backend Python, never calls
`fetch` outside `src/api/client.ts`, and never parses the session token: AQOS
issues opaque server-side tokens, not JWTs.

## The session token

Held in memory and mirrored into `sessionStorage`, so a refresh does not sign
you out. `sessionStorage` is scoped to one tab and cleared when it closes,
unlike `localStorage`. Neither is safe against script injection on this origin;
the safer end state is an httpOnly cookie, which needs cookie and CSRF handling
on the backend. See `src/lib/session.ts`.
