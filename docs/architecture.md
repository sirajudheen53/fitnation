# FitNation — Architecture Documentation

## System Overview

### Components
1. **Backend API** (Django + DRF) — serves REST APIs for ERP and mobile app
2. **ERP Frontend** (Next.js) — web application for gym owners, trainers, admins
3. **Customer Mobile App** (Flutter) — mobile app for customers
4. **Database** (PostgreSQL) — primary data store, multi-tenant
5. **Cache** (Redis) — caching + Celery task queue
6. **Search** (Elasticsearch) — full-text search for exercises, food, products
7. **Storage** (GCP Cloud Storage + CDN) — exercise videos, progress photos, product images
8. **Payments** (Razorpay) — payment processing
9. **Notifications** (WhatsApp Business API) — attendance, membership expiry, workout reminders

### Multi-Tenancy Strategy
- Row-level multi-tenancy: all entities have `tenant_id` (vendor_id)
- Django middleware extracts tenant from auth token
- Queryset filtering enforced at model manager level
- No raw queries without tenant filter

### Architecture Diagram (Text)
```
[Customer Mobile App (Flutter)]
        |
        v
[ERP Frontend (Next.js)] ---> [Backend API (Django + DRF)]
                                     |
                    +----------------+----------------+
                    |                |                |
              [PostgreSQL]      [Redis]        [Elasticsearch]
                               (cache +         (search)
                               Celery)
                                     |
                    +----------------+----------------+
                    |                |                |
              [Razorpay]    [WhatsApp API]    [GCP Storage]
              (payments)    (notifications)    (videos/photos)
```

## Database Schema (Core Entities)

### tenant (Vendor)
- id (PK)
- name
- subscription_plan (starter/pro/enterprise)
- created_at

### branch
- id (PK)
- tenant_id (FK → tenant)
- name
- address
- phone
- created_at

### user
- id (PK)
- tenant_id (FK → tenant, nullable for platform admins)
- role (platform_admin/gym_owner/manager/trainer/dietitian/customer)
- email
- phone
- name
- is_active
- created_at

### customer
- id (PK)
- tenant_id (FK → tenant)
- branch_id (FK → branch)
- user_id (FK → user)
- height
- weight
- bmi (auto-calculated)
- fitness_goal
- medical_info (JSON)
- injuries (text)
- created_at

### membership_plan
- id (PK)
- tenant_id (FK → tenant)
- name
- type (monthly/yearly/pt/trial)
- price
- duration_days
- is_active

### membership
- id (PK)
- tenant_id (FK → tenant)
- customer_id (FK → customer)
- plan_id (FK → membership_plan)
- start_date
- end_date
- status (active/expired/cancelled)
- created_at

### payment
- id (PK)
- tenant_id (FK → tenant)
- customer_id (FK → customer)
- amount
- method (cash/card/online/uppi)
- razorpay_payment_id
- invoice_number
- created_at

### trainer
- id (PK)
- tenant_id (FK → tenant)
- user_id (FK → user)
- specialization
- certifications (JSON)
- is_active
- created_at

### attendance
- id (PK)
- tenant_id (FK → tenant)
- customer_id (FK → customer)
- branch_id (FK → branch)
- check_in_time
- check_out_method (qr/manual)
- created_at

### exercise
- id (PK)
- name
- category (strength/cardio/flexibility/yoga)
- muscle_group
- difficulty (beginner/intermediate/advanced)
- equipment_required
- video_url
- instructions

### workout_plan
- id (PK)
- tenant_id (FK → tenant)
- customer_id (FK → customer)
- trainer_id (FK → trainer)
- title
- duration (daily/weekly/monthly)
- created_at

### workout_exercise
- id (PK)
- workout_plan_id (FK → workout_plan)
- exercise_id (FK → exercise)
- day_number
- sets
- reps
- weight
- rest_seconds
- notes

### diet_plan
- id (PK)
- tenant_id (FK → tenant)
- customer_id (FK → customer)
- dietitian_id (FK → user)
- title
- total_calories
- created_at

### meal
- id (PK)
- diet_plan_id (FK → diet_plan)
- meal_type (breakfast/lunch/dinner/snack)
- food_items (JSON)
- calories
- protein_g
- carbs_g
- fat_g

### product
- id (PK)
- tenant_id (FK → tenant)
- name
- category (supplement/equipment/merchandise/health)
- price
- stock
- image_url
- is_active