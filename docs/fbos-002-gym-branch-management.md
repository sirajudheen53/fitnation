# FBOS-002: Gym Branch Management

## Overview

Defines the branch model, CRUD API, and branch-level relationships with customers and trainers. A branch is a physical location of a gym vendor. Each tenant (vendor) can have 1–N branches depending on their subscription plan.

**Depends on:** FBOS-010 (Tenant model, `TenantModelMixin`), FBOS-001 (Tenant + owner user must exist)
**Tenant scoping:** All branch data is filtered by `tenant_id` via `TenantManager.for_tenant()`

---

## 1. Database Schema

### Branch Model

```python
# branches/models.py

from django.db import models
from tenants.models import TenantModelMixin


class Branch(TenantModelMixin):
    """A physical gym location belonging to a vendor (tenant)."""

    class BranchType(models.TextChoices):
        MAIN = "main", "Main"
        SUB = "sub", "Sub-branch"

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    branch_type = models.CharField(max_length=10, choices=BranchType.choices, default=BranchType.MAIN)
    address_line1 = models.CharField(max_length=300)
    address_line2 = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="India")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    opening_time = models.TimeField(default="05:00")
    closing_time = models.TimeField(default="23:00")
    operating_days = models.JSONField(
        default=list,  # ["mon","tue","wed","thu","fri","sat"]
        help_text="List of operating days (3-letter lowercase)"
    )
    is_active = models.BooleanField(default=True)
    is_headquarters = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "branches"
        ordering = ["-created_at"]
        constraints = [
            # Branch name must be unique within a tenant
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uq_branch_tenant_name",
            ),
        ]

    def __str__(self):
        return f"{self.name} — {self.city}"


class BranchAmenity(models.Model):
    """Amenities/facilities available at a branch (e.g., parking, showers, sauna)."""

    id = models.BigAutoField(primary_key=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="amenities")
    name = models.CharField(max_length=100)
    is_available = models.BooleanField(default=True)

    class Meta:
        db_table = "branch_amenities"
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "name"],
                name="uq_amenity_branch_name",
            ),
        ]


class BranchImage(models.Model):
    """Images uploaded for a branch (photos of gym, equipment, etc.)."""

    id = models.BigAutoField(primary_key=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="images")
    image_url = models.URLField()
    caption = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "branch_images"
        ordering = ["sort_order"]
```

### SQL Migration

```sql
CREATE TABLE branches (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    uuid UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    name VARCHAR(200) NOT NULL,
    branch_type VARCHAR(10) NOT NULL DEFAULT 'main',
    address_line1 VARCHAR(300) NOT NULL,
    address_line2 VARCHAR(300) DEFAULT '',
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    country VARCHAR(100) DEFAULT 'India',
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    phone VARCHAR(20) DEFAULT '',
    email VARCHAR(254) DEFAULT '',
    opening_time TIME NOT NULL DEFAULT '05:00',
    closing_time TIME NOT NULL DEFAULT '23:00',
    operating_days JSONB DEFAULT '["mon","tue","wed","thu","fri","sat"]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_headquarters BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

CREATE INDEX idx_branches_tenant_id ON branches(tenant_id);
CREATE INDEX idx_branches_tenant_active ON branches(tenant_id, is_active);
CREATE INDEX idx_branches_city ON branches(city);

CREATE TABLE branch_amenities (
    id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(branch_id, name)
);

CREATE TABLE branch_images (
    id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    caption VARCHAR(200) DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 2. Relationship Diagram

```
┌──────────┐       1     N ┌──────────┐
│  Tenant  │──────────────▶│  Branch  │
│ (Vendor) │               │          │
└──────────┘               └────┬─────┘
                                │ 1
                    ┌───────────┼───────────┐
                    │ N         │ N         │ N
               ┌────┴───┐  ┌────┴───┐  ┌────┴──────┐
               │Customer│  │Trainer │  │Attendance │
               │        │  │        │  │           │
               └────────┘  └────────┘  └───────────┘
```

**Key Relationships:**
- A `Tenant` has many `Branches` (limited by subscription plan's `max_branches`)
- A `Customer` belongs to one `Branch` (via `branch_id` FK)
- A `Trainer` can be assigned to multiple `Branches` (via M2M `BranchTrainerAssignment`)
- `Attendance` is logged per `Branch` (knows which location the customer checked into)
- A `Branch` has `BranchAmenities` and `BranchImages`

---

## 3. BranchTrainerAssignment Model

```python
# branches/models.py (continued)

class BranchTrainerAssignment(models.Model):
    """Maps trainers to branches (M2M). A trainer can work at multiple branches."""

    id = models.BigAutoField(primary_key=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="trainer_assignments")
    trainer = models.ForeignKey(
        "trainers.Trainer",  # lazy ref — Trainer model is in trainers app
        on_delete=models.CASCADE,
        related_name="branch_assignments",
    )
    is_primary = models.BooleanField(default=False)  # primary branch for this trainer
    assigned_at = models.DateTimeField(auto_now_add=True)
    unassigned_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "branch_trainer_assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "trainer"],
                name="uq_branch_trainer",
            ),
        ]
```

### SQL

```sql
CREATE TABLE branch_trainer_assignments (
    id BIGSERIAL PRIMARY KEY,
    branch_id BIGINT NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    trainer_id BIGINT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unassigned_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(branch_id, trainer_id)
);

CREATE INDEX idx_bta_branch ON branch_trainer_assignments(branch_id, is_active);
CREATE INDEX idx_bta_trainer ON branch_trainer_assignments(trainer_id, is_active);
```

---

## 4. API Endpoints

All endpoints require `Authorization: Token <token>` and the authenticated user's tenant must match the branch's tenant.

### 4.1 List Branches

```
GET /api/v1/branches/
```

**Query params:**
- `is_active` (bool) — filter active/inactive branches
- `city` (string) — filter by city
- `search` (string) — search by name or city
- `page` (int) — pagination (default 20 per page)

**Response (200):**
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "uuid": "a1b2c3d4-...",
      "name": "Kochi Main",
      "branch_type": "main",
      "address": {
        "line1": "MG Road",
        "line2": "Near Marine Drive",
        "city": "Kochi",
        "state": "Kerala",
        "postal_code": "682011",
        "country": "India",
        "latitude": "9.965500",
        "longitude": "76.242500"
      },
      "phone": "+914841234567",
      "email": "kochi@ironpeak.com",
      "hours": {
        "opening": "05:00",
        "closing": "23:00",
        "operating_days": ["mon","tue","wed","thu","fri","sat"]
      },
      "is_active": true,
      "is_headquarters": true,
      "amenities": [
        {"name": "Parking", "is_available": true},
        {"name": "Showers", "is_available": true},
        {"name": "Sauna", "is_available": false}
      ],
      "stats": {
        "customers_count": 85,
        "trainers_count": 4,
        "active_memberships": 72
      },
      "created_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

### 4.2 Create Branch

```
POST /api/v1/branches/
```

**Request:**
```json
{
  "name": "Kochi Main",
  "branch_type": "main",
  "address_line1": "MG Road",
  "address_line2": "Near Marine Drive",
  "city": "Kochi",
  "state": "Kerala",
  "postal_code": "682011",
  "country": "India",
  "latitude": 9.9655,
  "longitude": 76.2425,
  "phone": "+914841234567",
  "email": "kochi@ironpeak.com",
  "opening_time": "05:00",
  "closing_time": "23:00",
  "operating_days": ["mon","tue","wed","thu","fri","sat"],
  "amenities": [
    {"name": "Parking", "is_available": true},
    {"name": "Showers", "is_available": true}
  ]
}
```

**Response (201):**
```json
{
  "id": 1,
  "uuid": "a1b2c3d4-...",
  "name": "Kochi Main",
  "message": "Branch created successfully"
}
```

**Validation:**
- `name` — unique within tenant
- Branch count must not exceed `tenant.config.max_branches`
- `opening_time` < `closing_time`
- `operating_days` — list of 3-letter day codes, must be subset of `["mon","tue","wed","thu","fri","sat","sun"]`

### 4.3 Retrieve Branch

```
GET /api/v1/branches/{id}/
```

Returns full branch detail including amenities, images, and stats.

### 4.4 Update Branch

```
PATCH /api/v1/branches/{id}/
```

Partial update. Only the tenant's owner, managers, and platform admins can edit.

### 4.5 Deactivate Branch

```
DELETE /api/v1/branches/{id}/
```

**Behavior:** Soft delete — sets `is_active = False`. Does NOT delete the record. Customers and trainers assigned to the branch must be reassigned before deactivation (returns 400 if active customers/memberships exist).

**Response (200):**
```json
{
  "message": "Branch deactivated",
  "reassign_customers": false  // true if there were active customers
}
```

**Response (400 — has active customers):**
```json
{
  "error": "Cannot deactivate branch with active customers. Reassign them first.",
  "active_customers": 15,
  "active_memberships": 10
}
```

### 4.6 List Branch Trainers

```
GET /api/v1/branches/{branch_id}/trainers/
```

**Response (200):**
```json
{
  "branch_id": 1,
  "trainers": [
    {
      "trainer_id": 5,
      "user": {"name": "Rahul S", "email": "rahul@ironpeak.com", "phone": "+919876543210"},
      "specialization": "Strength Training",
      "is_primary": true,
      "assigned_at": "2025-01-20T09:00:00Z"
    }
  ]
}
```

### 4.7 Assign Trainer to Branch

```
POST /api/v1/branches/{branch_id}/trainers/
```

**Request:**
```json
{
  "trainer_id": 5,
  "is_primary": false
}
```

**Response (201):**
```json
{
  "message": "Trainer assigned to branch",
  "assignment_id": 12
}
```

### 4.8 Unassign Trainer from Branch

```
DELETE /api/v1/branches/{branch_id}/trainers/{trainer_id}/
```

Sets `is_active = False` and `unassigned_at = NOW()`.

### 4.9 List Branch Customers

```
GET /api/v1/branches/{branch_id}/customers/
```

Returns customers assigned to this branch. Supports `?status=active` and `?search=` filters.

### 4.10 Branch Stats

```
GET /api/v1/branches/{branch_id}/stats/
```

**Response (200):**
```json
{
  "branch_id": 1,
  "customers_count": 85,
  "active_memberships": 72,
  "trainers_count": 4,
  "today_attendance": 42,
  "revenue_this_month": 84915.00
}
```

### 4.11 Upload Branch Image

```
POST /api/v1/branches/{branch_id}/images/
```

**Request:** multipart form-data with `image` file + optional `caption`

**Response (201):**
```json
{
  "id": 7,
  "image_url": "https://storage.googleapis.com/fitnation/branches/1/img_7.jpg",
  "caption": "Main gym floor"
}
```

---

## 5. DRF Serializers

```python
# branches/serializers.py

from rest_framework import serializers
from branches.models import Branch, BranchAmenity, BranchImage, BranchTrainerAssignment


class BranchAmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchAmenity
        fields = ["id", "name", "is_available"]


class BranchImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BranchImage
        fields = ["id", "image_url", "caption", "sort_order"]


class BranchCreateSerializer(serializers.ModelSerializer):
    amenities = BranchAmenitySerializer(many=True, required=False)

    class Meta:
        model = Branch
        fields = [
            "name", "branch_type", "address_line1", "address_line2",
            "city", "state", "postal_code", "country",
            "latitude", "longitude", "phone", "email",
            "opening_time", "closing_time", "operating_days",
            "amenities",
        ]

    def validate_name(self, value):
        tenant = self.context["request"].tenant
        if Branch.objects.for_tenant(tenant).filter(name__iexact=value).exists():
            raise serializers.ValidationError("A branch with this name already exists.")
        return value

    def validate_operating_days(self, value):
        valid_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        invalid = set(value) - valid_days
        if invalid:
            raise serializers.ValidationError(f"Invalid day codes: {invalid}")
        return value

    def create(self, validated_data):
        tenant = self.context["request"].tenant
        amenities_data = validated_data.pop("amenities", [])
        branch = Branch.objects.create(tenant=tenant, **validated_data)
        for amenity in amenities_data:
            BranchAmenity.objects.create(branch=branch, **amenity)
        return branch


class BranchListSerializer(serializers.ModelSerializer):
    amenities = BranchAmenitySerializer(many=True, read_only=True)
    stats = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id", "uuid", "name", "branch_type", "phone", "email",
            "address_line1", "city", "state", "is_active", "is_headquarters",
            "opening_time", "closing_time", "operating_days",
            "amenities", "stats", "created_at",
        ]

    def get_stats(self, obj):
        return {
            "customers_count": obj.customers.filter(is_active=True).count(),
            "trainers_count": obj.trainer_assignments.filter(is_active=True).count(),
            "active_memberships": obj.customers.filter(memberships__status="active").count(),
        }


class BranchDetailSerializer(serializers.ModelSerializer):
    amenities = BranchAmenitySerializer(many=True, read_only=True)
    images = BranchImageSerializer(many=True, read_only=True)

    class Meta:
        model = Branch
        fields = [
            "id", "uuid", "name", "branch_type",
            "address_line1", "address_line2", "city", "state", "postal_code", "country",
            "latitude", "longitude", "phone", "email",
            "opening_time", "closing_time", "operating_days",
            "is_active", "is_headquarters", "metadata",
            "amenities", "images", "created_at", "updated_at",
        ]


class BranchTrainerAssignmentSerializer(serializers.ModelSerializer):
    trainer_name = serializers.CharField(source="trainer.user.get_full_name", read_only=True)
    trainer_email = serializers.CharField(source="trainer.user.email", read_only=True)
    specialization = serializers.CharField(source="trainer.specialization", read_only=True)

    class Meta:
        model = BranchTrainerAssignment
        fields = ["id", "trainer_id", "trainer_name", "trainer_email",
                  "specialization", "is_primary", "assigned_at", "is_active"]
```

---

## 6. ViewSet

```python
# branches/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from tenants.permissions import IsTenantMember
from tenants.models import TenantModelMixin
from branches.models import Branch, BranchTrainerAssignment, BranchImage
from branches.serializers import *


class BranchViewSet(viewsets.ModelViewSet):
    """CRUD for gym branches. All operations are tenant-scoped."""

    permission_classes = [IsAuthenticated, IsTenantMember]

    def get_queryset(self):
        tenant = self.request.tenant
        qs = Branch.objects.for_tenant(tenant)
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active == "true")
        city = self.request.query_params.get("city")
        if city:
            qs = qs.filter(city__iexact=city)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(city__icontains=search)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return BranchListSerializer
        if self.action == "retrieve":
            return BranchDetailSerializer
        if self.action in ["create", "update", "partial_update"]:
            return BranchCreateSerializer
        return BranchListSerializer

    def perform_create(self, serializer):
        tenant = self.request.tenant
        # Check branch limit
        current_count = Branch.objects.for_tenant(tenant).filter(is_active=True).count()
        max_branches = tenant.config.max_branches if hasattr(tenant, "config") else 1
        if current_count >= max_branches:
            return Response(
                {"error": f"Branch limit reached ({max_branches}). Upgrade your plan to add more branches."},
                status=400,
            )
        serializer.save(tenant=tenant)

    def destroy(self, request, *args, **kwargs):
        branch = self.get_object()
        # Check for active customers
        active_customers = branch.customers.filter(is_active=True).count()
        if active_customers > 0:
            return Response({
                "error": f"Cannot deactivate branch with {active_customers} active customers. Reassign them first.",
                "active_customers": active_customers,
            }, status=400)
        branch.is_active = False
        branch.save()
        return Response({"message": "Branch deactivated"})

    @action(detail=True, methods=["get"])
    def trainers(self, request, pk=None):
        branch = self.get_object()
        assignments = BranchTrainerAssignment.objects.filter(branch=branch, is_active=True)
        serializer = BranchTrainerAssignmentSerializer(assignments, many=True)
        return Response({"branch_id": branch.id, "trainers": serializer.data})

    @action(detail=True, methods=["post"])
    def assign_trainer(self, request, pk=None):
        branch = self.get_object()
        trainer_id = request.data.get("trainer_id")
        is_primary = request.data.get("is_primary", False)
        assignment, created = BranchTrainerAssignment.objects.get_or_create(
            branch=branch, trainer_id=trainer_id,
            defaults={"is_primary": is_primary, "is_active": True},
        )
        if not created:
            assignment.is_active = True
            assignment.save()
        return Response({"message": "Trainer assigned to branch", "assignment_id": assignment.id}, status=201)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        branch = self.get_object()
        return Response({
            "branch_id": branch.id,
            "customers_count": branch.customers.filter(is_active=True).count(),
            "active_memberships": branch.customers.filter(memberships__status="active").count(),
            "trainers_count": branch.trainer_assignments.filter(is_active=True).count(),
            "today_attendance": branch.attendance_set.filter(created_at__date=timezone.now().date()).count(),
            "revenue_this_month": self._month_revenue(branch),
        })

    def _month_revenue(self, branch):
        from payments.models import Payment
        return Payment.objects.for_tenant(branch.tenant).filter(
            branch=branch,
            created_at__month=timezone.now().month,
        ).aggregate(total=models.Sum("amount"))["total"] or 0
```

---

## 7. URL Configuration

```python
# branches/urls.py

from rest_framework.routers import DefaultRouter
from branches.views import BranchViewSet

router = DefaultRouter()
router.register(r"branches", BranchViewSet, basename="branch")

urlpatterns = router.urls
```

---

## 8. Frontend Pages (Next.js)

| Route | Component | Roles | Description |
|-------|-----------|-------|-------------|
| `/branches` | `BranchListPage` | gym_owner, manager | List all branches with stats |
| `/branches/new` | `BranchCreatePage` | gym_owner | Create branch form |
| `/branches/[id]` | `BranchDetailPage` | gym_owner, manager | Branch detail with tabs: info, trainers, customers, stats |
| `/branches/[id]/edit` | `BranchEditPage` | gym_owner | Edit branch form |

---

## 9. Implementation Checklist

| # | Task | Owner | Status |
|---|------|-------|--------|
| 1 | Create `branches` Django app | Backend | ☐ |
| 2 | Implement `Branch`, `BranchAmenity`, `BranchImage` models | Backend | ☐ |
| 3 | Implement `BranchTrainerAssignment` model | Backend | ☐ |
| 4 | Implement `BranchViewSet` with all actions | Backend | ☐ |
| 5 | Implement serializers with validation | Backend | ☐ |
| 6 | Add branch limit check (tenant subscription) | Backend | ☐ |
| 7 | Write tests: CRUD, tenant isolation, limit enforcement | Backend | ☐ |
| 8 | Frontend: branch list page | Frontend | ☐ |
| 9 | Frontend: branch create/edit form | Frontend | ☐ |
| 10 | Frontend: branch detail with tabs | Frontend | ☐ |
| 11 | Frontend: trainer assignment UI | Frontend | ☐ |
| 12 | Integration test: branch CRUD end-to-end | Backend + Frontend | ☐ |

---

## 10. Cross-Story Dependencies

- **Requires:** FBOS-010 (`TenantModelMixin`, `TenantManager`), FBOS-001 (tenant + user must exist)
- **Required by:** FBOS-003 (Customer management — customers are assigned to branches)
- **Required by:** FBOS-006 (Attendance — attendance is logged per branch)
- **Required by:** FBOS-007 (Trainer management — trainers are assigned to branches via `BranchTrainerAssignment`)
- **Required by:** FBOS-008 (Dashboard — branch-level stats rollup)
- **Future:** Branch-level settings, branch-level access control (branch managers)