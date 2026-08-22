# FBOS Frontend — Next.js ERP Web Application

The web application for FitNation's Fitness Business Operating System (FBOS).

## Tech Stack
- **Framework:** Next.js 15 (App Router)
- **UI:** React 19 + Tailwind CSS 4
- **Forms:** react-hook-form + zod
- **State:** TanStack React Query (server), Zustand (client)
- **Icons:** Lucide React
- **Notifications:** Sonner

## Getting Started

```bash
# Install dependencies
pnpm install

# Copy env file
cp .env.example .env.local

# Run dev server
pnpm dev
```

## Project Structure

```
frontend/
├── app/                    # Next.js App Router pages
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Landing page
│   ├── signup/             # FBOS-001: Vendor signup
│   ├── verify-email/       # FBOS-001: Email verification
│   ├── select-plan/        # FBOS-001: Plan selection
│   ├── onboarding/         # FBOS-001: Onboarding wizard
│   └── dashboard/          # FBOS-008: ERP dashboard (future)
├── components/
│   ├── ui/                 # Reusable UI primitives (Button, Input, Card, Alert)
│   └── layout/             # Layout components (AuthLayout)
├── lib/
│   ├── api.ts              # API client for backend endpoints
│   ├── auth.ts             # Token storage & session helpers
│   ├── permissions.ts      # FBOS-009: Role-based permission matrix + route guards
│   └── utils.ts            # Shared utilities (cn for classnames)
└── package.json
```

## Sprint 1 Scope (FBOS-001 + FBOS-009)

### Routes Built
| Route | Description | Auth |
|-------|-------------|------|
| `/signup` | Multi-field registration form | No |
| `/verify-email` | Email token verification | No |
| `/select-plan` | 3-tier subscription plan selection | No |
| `/onboarding` | 2-step wizard (business type → branch info) | Yes (token) |

### API Integration
All API calls go through `lib/api.ts` which handles:
- POST `/auth/signup/` — create registration
- GET `/auth/verify-email/?token=*** — verify email
- POST `/auth/resend-verification/` — resend email
- GET `/subscriptions/plans/` — list plans
- POST `/auth/select-plan/` — select plan + get auth token
- PUT `/auth/onboarding/` — complete onboarding

### FBOS-009: Permissions Library
`lib/permissions.ts` exports:
- `ROLE_PERMISSIONS` — role → permission set mapping
- `hasPermission(role, permission)` — check single permission
- `hasAnyPermission(role, permissions[])` — check any of
- `canAccessRoute(role, pathname)` — route guard check
- `ROUTE_PERMISSIONS` — pathname → required permissions map
- `ROLE_LABELS` / `ROLE_COLORS` — display helpers