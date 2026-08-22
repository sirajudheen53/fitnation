# AGENTS.md - FitNation Project (OpenCode)

## Project: Fitness Business Operating System (FBOS)

## What is this?
A multi-vendor fitness ERP + customer engagement platform. Built with Django backend, Next.js ERP frontend, and Flutter customer mobile app.

## Tech Stack
- **Backend:** Django + Django REST Framework + PostgreSQL + Redis + Elasticsearch
- **Frontend:** Next.js + React + Tailwind CSS
- **Mobile:** Flutter
- **Hosting:** GCP
- **Payments:** Razorpay
- **Notifications:** WhatsApp Business API
- **Video:** GCP Cloud Storage + CDN
- **Auth:** OTP-based

## Project Structure
```
/backend    — Django REST API (DRF)
/frontend   — Next.js ERP web application
/mobile     — Flutter customer mobile app
/docs       — Architecture docs, ADRs, API specs
```

## Coding Standards

### Backend (Django)
- Use Django model managers for tenant filtering
- All APIs return JSON via DRF serializers
- Pagination on all list endpoints
- Rate limiting on auth endpoints
- Use Celery for background tasks
- Write tests for all endpoints

### Frontend (Next.js)
- TypeScript everywhere
- Function components with hooks
- Tailwind utility classes for styling
- React Query for server state, Zustand for UI state
- Feature-based folder structure
- Tests with Jest + React Testing Library

### Mobile (Flutter)
- Null safety everywhere
- Immutable data models (freezed)
- Feature-based folder structure
- Riverpod for state management
- Tests for all widgets and integration

## Multi-Tenant Rules
- Every database entity has a `tenant_id` (vendor_id)
- All queries MUST filter by tenant — no exceptions
- API endpoints require tenant context from auth token
- Never expose cross-tenant data

## OpenCode Agents
When working on this project, use the appropriate agent:
- `/agent architect` — for architecture and design tasks
- `/agent backend` — for Django/backend coding
- `/agent frontend` — for Next.js/frontend coding
- `/agent mobile` — for Flutter/mobile coding

## Important
- Always write tests for new features
- Never commit secrets, API keys, or passwords
- Follow the architecture in /docs
- Run `python manage.py test` after backend changes
- Run `npm run test` after frontend changes
- Run `flutter test` after mobile changes