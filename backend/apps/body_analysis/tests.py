"""Tests for the body analysis app."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.body_analysis.models import (
    BodyAnalysis,
    BodyPhoto,
    BodyProgressLog,
)
from apps.body_analysis.services import (
    build_progress_trend,
    create_photo_for_analysis,
)
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

User = get_user_model()


def _make_tenant_and_owner(email: str = "owner@local.test"):
    """Provision a tenant and owner user, returning both."""
    tenant = provision_tenant(
        name="Iron Peak",
        contact_email=email,
    )
    owner = create_owner_user(
        tenant=tenant,
        email=email,
        password_hash="pbkdf2_sha256$hashed",
        contact_name="Owner User",
    )
    return tenant, owner


class BodyAnalysisModelTests(TestCase):
    """Unit tests for BodyAnalysis model."""

    def setUp(self) -> None:
        """Create tenant and owner."""
        self.tenant, self.owner = _make_tenant_and_owner()

    def _customer(self, email: str) -> User:
        """Create a customer user."""
        return User.objects.create_user(
            email=email,
            password="F1tNati0n!",
            first_name="Test",
            last_name="User",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    def test_body_analysis_requires_tenant(self) -> None:
        """Creating an analysis without a tenant raises ValueError."""
        user = self._customer("orphan@example.com")
        with self.assertRaises(ValueError):
            BodyAnalysis.objects.create(
                user=user,
                height_cm="170.00",
                weight_kg="70.00",
            )

    def test_bmi_auto_calculated(self) -> None:
        """BMI is auto-calculated from height and weight."""
        user = self._customer("bmi@example.com")
        analysis = BodyAnalysis.objects.create(
            tenant=self.tenant,
            user=user,
            height_cm="170.00",
            weight_kg="70.00",
        )
        expected = round(70.0 / (1.70 * 1.70), 2)
        self.assertEqual(Decimal(str(analysis.bmi)), Decimal(str(expected)))

    def test_bmi_blank_when_height_zero(self) -> None:
        """BMI is left null when height cannot be used."""
        user = self._customer("bmi0@example.com")
        analysis = BodyAnalysis(
            tenant=self.tenant,
            user=user,
            height_cm="0.00",
            weight_kg="70.00",
        )
        self.assertIsNone(analysis.bmi)

    def test_photo_count_defaults_to_zero(self) -> None:
        """New analyses start with a zero photo count."""
        user = self._customer("photos@example.com")
        analysis = BodyAnalysis.objects.create(
            tenant=self.tenant,
            user=user,
            height_cm="170.00",
            weight_kg="70.00",
        )
        self.assertEqual(analysis.photo_count, 0)

    def test_tenant_isolation(self) -> None:
        """Analyses are scoped to their tenant."""
        user = self._customer("iso@example.com")
        BodyAnalysis.objects.create(
            tenant=self.tenant,
            user=user,
            height_cm="170.00",
            weight_kg="70.00",
        )
        other_tenant, other_owner = _make_tenant_and_owner("other@example.com")
        other_user = User.objects.create_user(
            email="otheruser@example.com",
            password="F1tNati0n!",
            role=User.Role.CUSTOMER,
            tenant=other_tenant,
        )
        BodyAnalysis.objects.create(
            tenant=other_tenant,
            user=other_user,
            height_cm="160.00",
            weight_kg="55.00",
        )
        self.assertEqual(BodyAnalysis.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(BodyAnalysis.objects.for_tenant(other_tenant).count(), 1)

    def test_str_method(self) -> None:
        """String representation includes the user and date."""
        user = self._customer("str@example.com")
        analysis = BodyAnalysis.objects.create(
            tenant=self.tenant,
            user=user,
            height_cm="170.00",
            weight_kg="70.00",
        )
        self.assertIn(str(user.id), str(analysis))


class BodyPhotoModelTests(TestCase):
    """Unit tests for BodyPhoto model."""

    def setUp(self) -> None:
        """Create tenant, owner, and an analysis."""
        self.tenant, self.owner = _make_tenant_and_owner()
        self.user = User.objects.create_user(
            email="photo@example.com",
            password="F1tNati0n!",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.analysis = BodyAnalysis.objects.create(
            tenant=self.tenant,
            user=self.user,
            height_cm="170.00",
            weight_kg="70.00",
        )

    def test_photo_requires_tenant(self) -> None:
        """Creating a photo without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            BodyPhoto.objects.create(
                analysis=self.analysis,
                photo_type=BodyPhoto.PhotoType.FRONT,
                image_url="https://cdn.example.com/a.jpg",
            )

    def test_photo_defaults(self) -> None:
        """Photo defaults: front type, unprocessed, no result."""
        photo = BodyPhoto.objects.create(
            tenant=self.tenant,
            analysis=self.analysis,
            image_url="https://cdn.example.com/front.jpg",
        )
        self.assertEqual(photo.photo_type, BodyPhoto.PhotoType.FRONT)
        self.assertFalse(photo.is_processed)
        self.assertIsNone(photo.analysis_result)

    def test_photo_tenant_isolation(self) -> None:
        """Photos are scoped to their tenant via the analysis."""
        BodyPhoto.objects.create(
            tenant=self.tenant,
            analysis=self.analysis,
            photo_type="side",
            image_url="https://cdn.example.com/side.jpg",
        )
        other_tenant, _ = _make_tenant_and_owner("photoother@example.com")
        self.assertEqual(BodyPhoto.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(BodyPhoto.objects.for_tenant(other_tenant).count(), 0)


class BodyProgressLogModelTests(TestCase):
    """Unit tests for BodyProgressLog model."""

    def setUp(self) -> None:
        """Create tenant and owner."""
        self.tenant, self.owner = _make_tenant_and_owner()
        self.user = User.objects.create_user(
            email="progress@example.com",
            password="F1tNati0n!",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    def test_progress_requires_tenant(self) -> None:
        """Creating a progress log without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            BodyProgressLog.objects.create(
                user=self.user,
                metric_type=BodyProgressLog.MetricType.WEIGHT,
                value="70.00",
            )

    def test_progress_str(self) -> None:
        """String includes metric and value."""
        log = BodyProgressLog.objects.create(
            tenant=self.tenant,
            user=self.user,
            metric_type=BodyProgressLog.MetricType.WEIGHT,
            value="70.00",
            unit="kg",
        )
        self.assertIn("weight", str(log))

    def test_progress_tenant_isolation(self) -> None:
        """Progress logs are scoped to their tenant."""
        BodyProgressLog.objects.create(
            tenant=self.tenant,
            user=self.user,
            metric_type=BodyProgressLog.MetricType.WEIGHT,
            value="70.00",
        )
        other_tenant, _ = _make_tenant_and_owner("progother@example.com")
        self.assertEqual(
            BodyProgressLog.objects.for_tenant(self.tenant).count(),
            1,
        )
        self.assertEqual(
            BodyProgressLog.objects.for_tenant(other_tenant).count(),
            0,
        )


class BodyAnalysisAPITests(APITestCase):
    """Integration tests for body analysis endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, token, and a customer."""
        self.tenant, self.owner = _make_tenant_and_owner()
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.user = User.objects.create_user(
            email="customer@example.com",
            password="F1tNati0n!",
            first_name="Customer",
            last_name="User",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    def _create_analysis(self, weight: str = "70.00") -> BodyAnalysis:
        """Create an analysis for the customer."""
        return BodyAnalysis.objects.create(
            tenant=self.tenant,
            user=self.user,
            height_cm="170.00",
            weight_kg=weight,
        )

    def test_list_analyses(self) -> None:
        """Owners can list analyses in their tenant."""
        self._create_analysis()
        response = self.client.get("/api/v1/ai/body-analysis/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["user"],
            self.user.id,
        )

    def test_create_analysis_auto_calculates_bmi(self) -> None:
        """Creating an analysis computes BMI server-side."""
        response = self.client.post(
            "/api/v1/ai/body-analysis/",
            {
                "user": self.user.id,
                "analysis_date": date.today().isoformat(),
                "height_cm": "170.00",
                "weight_kg": "70.00",
                "body_fat_pct": "20.00",
                "notes": "First scan",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        expected = round(70.0 / (1.70 * 1.70), 2)
        self.assertEqual(float(response.data["bmi"]), expected)
        self.assertEqual(response.data["photo_count"], 0)

    def test_create_analysis_requires_authentication(self) -> None:
        """Unauthenticated create requests are rejected."""
        self.client.credentials()
        response = self.client.post(
            "/api/v1/ai/body-analysis/",
            {
                "user": self.user.id,
                "height_cm": "170.00",
                "weight_kg": "70.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_retrieve_analysis(self) -> None:
        """Owners can retrieve a single analysis."""
        analysis = self._create_analysis()
        response = self.client.get(f"/api/v1/ai/body-analysis/{analysis.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], analysis.id)

    def test_update_analysis(self) -> None:
        """Owners can partially update an analysis."""
        analysis = self._create_analysis()
        response = self.client.patch(
            f"/api/v1/ai/body-analysis/{analysis.id}/",
            {"body_fat_pct": "18.50"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["body_fat_pct"], "18.50")

    def test_delete_analysis(self) -> None:
        """Owners can delete an analysis."""
        analysis = self._create_analysis()
        response = self.client.delete(f"/api/v1/ai/body-analysis/{analysis.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            BodyAnalysis.objects.filter(id=analysis.id).exists(),
        )

    def test_tenant_isolation_list(self) -> None:
        """Analyses from other tenants are invisible."""
        other_tenant, _ = _make_tenant_and_owner("isoother@example.com")
        other_user = User.objects.create_user(
            email="isootheruser@example.com",
            password="F1tNati0n!",
            role=User.Role.CUSTOMER,
            tenant=other_tenant,
        )
        BodyAnalysis.objects.create(
            tenant=other_tenant,
            user=other_user,
            height_cm="160.00",
            weight_kg="55.00",
        )
        response = self.client.get("/api/v1/ai/body-analysis/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 0)


class BodyPhotoUploadAPITests(APITestCase):
    """Integration tests for the body-photo upload endpoint."""

    def setUp(self) -> None:
        """Create tenant, owner, token, and an analysis."""
        self.tenant, self.owner = _make_tenant_and_owner()
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.user = User.objects.create_user(
            email="photoapi@example.com",
            password="F1!Nati0n",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )
        self.analysis = BodyAnalysis.objects.create(
            tenant=self.tenant,
            user=self.user,
            height_cm="170.00",
            weight_kg="70.00",
        )

    def test_upload_photo_multipart(self) -> None:
        """Multipart upload creates a photo and bumps photo_count."""
        response = self.client.post(
            "/api/v1/ai/body-photo/upload/",
            {
                "analysis_id": self.analysis.id,
                "photo_type": "front",
                "image_url": "https://cdn.example.com/front.jpg",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["photo_type"], "front")
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.photo_count, 1)

    def test_upload_photo_unknown_analysis(self) -> None:
        """Uploading to a missing analysis returns 404."""
        response = self.client.post(
            "/api/v1/ai/body-photo/upload/",
            {
                "analysis_id": 99999,
                "photo_type": "front",
                "image_url": "https://cdn.example.com/x.jpg",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

    def test_upload_photo_other_tenant_analysis(self) -> None:
        """A photo cannot be attached to another tenant's analysis."""
        other_tenant, _ = _make_tenant_and_owner("uploadother@example.com")
        other_user = User.objects.create_user(
            email="upother@example.com",
            password="F1!Nati0n",
            role=User.Role.CUSTOMER,
            tenant=other_tenant,
        )
        other_analysis = BodyAnalysis.objects.create(
            tenant=other_tenant,
            user=other_user,
            height_cm="160.00",
            weight_kg="55.00",
        )
        response = self.client.post(
            "/api/v1/ai/body-photo/upload/",
            {
                "analysis_id": other_analysis.id,
                "photo_type": "front",
                "image_url": "https://cdn.example.com/other.jpg",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)


class BodyProgressAPITests(APITestCase):
    """Integration tests for body progress endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, token, and a customer."""
        self.tenant, self.owner = _make_tenant_and_owner()
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.user = User.objects.create_user(
            email="progapi@example.com",
            password="F1!Nati0n",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    def test_log_measurement(self) -> None:
        """Customers can log a new measurement."""
        response = self.client.post(
            "/api/v1/ai/body-progress/",
            {
                "user": self.user.id,
                "date": date.today().isoformat(),
                "metric_type": "weight",
                "value": "80.00",
                "unit": "kg",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["metric_type"], "weight")

    def test_list_progress_logs(self) -> None:
        """Owners can list progress logs."""
        BodyProgressLog.objects.create(
            tenant=self.tenant,
            user=self.user,
            metric_type="weight",
            value="80.00",
        )
        response = self.client.get("/api/v1/ai/body-progress/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_trend_returns_time_series(self) -> None:
        """The trend endpoint returns chronological data points."""
        today = date.today()
        for i, weight in enumerate(["80.00", "79.00", "78.00"]):
            BodyProgressLog.objects.create(
                tenant=self.tenant,
                user=self.user,
                date=today + timedelta(days=i),
                metric_type="weight",
                value=weight,
                unit="kg",
            )
        response = self.client.get(
            f"/api/v1/ai/body-progress/trend/?user={self.user.id}&metric_type=weight",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        self.assertEqual(response.data[0]["value"], 80.0)
        self.assertEqual(response.data[2]["value"], 78.0)

    def test_trend_requires_metric_type(self) -> None:
        """Missing metric_type returns 400."""
        response = self.client.get("/api/v1/ai/body-progress/trend/")
        self.assertEqual(response.status_code, 400)

    def test_trend_invalid_metric_type(self) -> None:
        """Invalid metric_type returns 400."""
        response = self.client.get(
            "/api/v1/ai/body-progress/trend/?metric_type=banana",
        )
        self.assertEqual(response.status_code, 400)

    def test_trend_filters_by_date_range(self) -> None:
        """Trend respects start_date/end_date filters."""
        today = date.today()
        BodyProgressLog.objects.create(
            tenant=self.tenant,
            user=self.user,
            date=today - timedelta(days=30),
            metric_type="weight",
            value="85.00",
        )
        BodyProgressLog.objects.create(
            tenant=self.tenant,
            user=self.user,
            date=today,
            metric_type="weight",
            value="80.00",
        )
        response = self.client.get(
            f"/api/v1/ai/body-progress/trend/?metric_type=weight&start_date={today.isoformat()}&user={self.user.id}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["value"], 80.0)


class ServiceTests(TestCase):
    """Unit tests for body analysis services."""

    def setUp(self) -> None:
        """Create tenant, owner, and a customer."""
        self.tenant, self.owner = _make_tenant_and_owner()
        self.user = User.objects.create_user(
            email="service@example.com",
            password="F1!Nati0n",
            role=User.Role.CUSTOMER,
            tenant=self.tenant,
        )

    def test_create_photo_bumps_count(self) -> None:
        """create_photo_for_analysis increments photo_count."""
        analysis = BodyAnalysis.objects.create(
            tenant=self.tenant,
            user=self.user,
            height_cm="170.00",
            weight_kg="70.00",
        )
        create_photo_for_analysis(
            tenant=self.tenant,
            analysis_id=analysis.id,
            photo_type="front",
            image_url="https://cdn.example.com/a.jpg",
        )
        analysis.refresh_from_db()
        self.assertEqual(analysis.photo_count, 1)

    def test_create_photo_missing_analysis_raises(self) -> None:
        """create_photo_for_analysis raises for a missing analysis."""
        with self.assertRaises(BodyAnalysis.DoesNotExist):
            create_photo_for_analysis(
                tenant=self.tenant,
                analysis_id=99999,
                photo_type="front",
                image_url="https://cdn.example.com/a.jpg",
            )

    def test_build_progress_trend_latest_value_wins_per_date(self) -> None:
        """Duplicate dates keep only the latest value."""
        today = date.today()
        first = BodyProgressLog.objects.create(
            tenant=self.tenant,
            user=self.user,
            date=today,
            metric_type="weight",
            value="80.00",
        )
        second = BodyProgressLog.objects.create(
            tenant=self.tenant,
            user=self.user,
            date=today,
            metric_type="weight",
            value="79.50",
        )
        # Simulate the second log being created later.
        BodyProgressLog.objects.filter(pk=second.pk).update(
            created_at=first.created_at + timedelta(hours=1),
        )
        data = build_progress_trend(
            tenant=self.tenant,
            user_id=self.user.id,
            metric_type="weight",
        )
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["value"], 79.5)
