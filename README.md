# FitNation

> Fitness Business Operating System (FBOS) — Multi-Vendor Fitness ERP + Customer Engagement Platform

## Vision
Become the Shopify + Salesforce + Health App ecosystem for fitness businesses.

## Tech Stack
- **Backend:** Django + DRF + PostgreSQL + Redis + Elasticsearch
- **ERP Frontend:** Next.js + React + Tailwind CSS
- **Mobile App:** Flutter
- **Hosting:** GCP | **Payments:** Razorpay | **Notifications:** WhatsApp Business API

## Project Structure
```
/backend    — Django REST API
/frontend   — Next.js ERP web app
/mobile     — Flutter customer mobile app
/docs       — Architecture, ADRs, API specs
/AGENTS.md  — OpenCode project instructions
```

## Getting Started
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
npm run dev

# Mobile
cd mobile
flutter pub get
flutter run
```

## Status
🚧 In development — Phase 1 (Gym ERP)