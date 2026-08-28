"""Tests for the reviews app (FBOS-034)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.branches.models import Branch
from apps.reviews.models import Review, ReviewResponse
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, create_user, issue_token

User = get_user_model()


def make_customer_user(tenant, email):
    """Create a customer user plus its customer profile within a tenant."""
    return create_user(
        tenant=tenant,
        email=email,
        first_name="Customer",
        last_name="One",
        role=User.Role.CUSTOMER,
    )


def make_branch(tenant, name="Main Branch"):
    """Create a branch within a tenant."""
    return Branch.objects.create(
        tenant=tenant,
        name=name,
        address_line1="MG Road",
    )


class ReviewModelTests(TestCase):
    """Unit tests for review models."""

    def setUp(self) -> None:
        """Create a tenant, branch, and customer for model tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.branch = make_branch(self.tenant)
        self.user = make_customer_user(self.tenant, "c@local.test")
        self.customer = self.user.customer_profile

    def test_review_requires_tenant(self) -> None:
        """Creating a review without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            Review.objects.create(
                customer=self.customer,
                branch=self.branch,
                rating=5,
            )

    def test_review_creates_successfully(self) -> None:
        """A review record persists with default values."""
        review = Review.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            rating=4,
            text="Great gym!",
        )
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.text, "Great gym!")
        self.assertEqual(str(review), "Review (4/5) by Customer One")

    def test_review_tenant_isolation(self) -> None:
        """Reviews are scoped to their tenant."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_user = make_customer_user(other_tenant, "other@local.test")
        other_branch = make_branch(other_tenant, "Other Branch")
        Review.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            rating=5,
        )
        Review.objects.create(
            tenant=other_tenant,
            customer=other_user.customer_profile,
            branch=other_branch,
            rating=3,
        )
        self.assertEqual(Review.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(Review.objects.for_tenant(other_tenant).count(), 1)

    def test_review_response_requires_tenant(self) -> None:
        """Creating a response without a tenant raises ValueError."""
        review = Review.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            rating=5,
        )
        with self.assertRaises(ValueError):
            ReviewResponse.objects.create(review=review, text="Thanks!")

    def test_review_response_creates_successfully(self) -> None:
        """A response links to its review and author."""
        review = Review.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            rating=5,
        )
        response = ReviewResponse.objects.create(
            tenant=self.tenant,
            review=review,
            text="Thanks for the review!",
        )
        self.assertEqual(review.response, response)
        self.assertEqual(response.text, "Thanks for the review!")
        self.assertIn("Response to review", str(response))

    def test_review_response_tenant_isolation(self) -> None:
        """Responses are scoped to their tenant."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_user = make_customer_user(other_tenant, "other@local.test")
        other_branch = make_branch(other_tenant, "Other Branch")
        review = Review.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            rating=5,
        )
        other_review = Review.objects.create(
            tenant=other_tenant,
            customer=other_user.customer_profile,
            branch=other_branch,
            rating=3,
        )
        ReviewResponse.objects.create(tenant=self.tenant, review=review, text="A")
        ReviewResponse.objects.create(tenant=other_tenant, review=other_review, text="B")
        self.assertEqual(ReviewResponse.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(ReviewResponse.objects.for_tenant(other_tenant).count(), 1)


class ReviewAPITests(APITestCase):
    """Integration tests for review endpoints."""

    def setUp(self) -> None:
        """Create tenant, owner, branch, customer, and auth tokens."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.owner_token = issue_token(self.owner, self.tenant)
        self.branch = make_branch(self.tenant)
        self.customer_user = make_customer_user(self.tenant, "cust@local.test")
        self.customer = self.customer_user.customer_profile
        self.customer_token = issue_token(self.customer_user, self.tenant)

    def _auth(self, token) -> None:
        """Set the client auth header to the given token."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _create_review(self, **overrides) -> Review:
        """Create a review record for the default customer."""
        data = {
            "tenant": self.tenant,
            "customer": self.customer,
            "branch": self.branch,
            "rating": 5,
            "text": "Excellent!",
        }
        data.update(overrides)
        return Review.objects.create(**data)

    def test_customer_submits_review(self) -> None:
        """A customer can submit a review for a branch."""
        self._auth(self.customer_token)
        response = self.client.post(
            "/api/v1/reviews/",
            {"branch": self.branch.id, "rating": 5, "text": "Great gym"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["rating"], 5)
        self.assertEqual(response.data["customer"], self.customer.id)
        self.assertEqual(response.data["branch"], self.branch.id)
        self.assertEqual(
            Review.objects.for_tenant(self.tenant).filter(customer=self.customer).count(),
            1,
        )

    def test_customer_sees_only_own_reviews(self) -> None:
        """A customer cannot see other customers' reviews."""
        other_user = make_customer_user(self.tenant, "other@local.test")
        self._create_review()
        Review.objects.create(
            tenant=self.tenant,
            customer=other_user.customer_profile,
            branch=self.branch,
            rating=2,
            text="Other review",
        )
        self._auth(self.customer_token)
        response = self.client.get("/api/v1/reviews/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_owner_sees_all_reviews(self) -> None:
        """Owners can view all reviews in the tenant."""
        self._create_review()
        self._auth(self.owner_token)
        response = self.client.get("/api/v1/reviews/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_list_filters_by_branch(self) -> None:
        """Reviews can be filtered by branch_id."""
        other_branch = make_branch(self.tenant, "Second Branch")
        self._create_review()
        Review.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            branch=other_branch,
            rating=3,
        )
        self._auth(self.owner_token)
        response = self.client.get(f"/api/v1/reviews/?branch_id={self.branch.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["branch"], self.branch.id)

    def test_list_includes_aggregate_rating(self) -> None:
        """The list endpoint returns average rating and count."""
        self._create_review(rating=5)
        self._create_review(rating=3)
        self._auth(self.owner_token)
        response = self.client.get("/api/v1/reviews/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["average_rating"], 4.0)

    def test_list_aggregate_empty(self) -> None:
        """An empty tenant returns null average and zero count."""
        self._auth(self.owner_token)
        response = self.client.get("/api/v1/reviews/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertIsNone(response.data["average_rating"])

    def test_owner_responds_to_review(self) -> None:
        """Owners can post a response to a review."""
        review = self._create_review()
        self._auth(self.owner_token)
        response = self.client.post(
            f"/api/v1/reviews/{review.id}/respond/",
            {"text": "Thanks for the review!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["text"], "Thanks for the review!")
        self.assertEqual(response.data["author"], self.owner.id)
        review.refresh_from_db()
        self.assertEqual(review.response.text, "Thanks for the review!")

    def test_respond_requires_text(self) -> None:
        """A response without text returns a 400."""
        review = self._create_review()
        self._auth(self.owner_token)
        response = self.client.post(
            f"/api/v1/reviews/{review.id}/respond/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_respond_updates_existing_response(self) -> None:
        """Responding twice updates the existing response rather than duplicating."""
        review = self._create_review()
        self._auth(self.owner_token)
        self.client.post(
            f"/api/v1/reviews/{review.id}/respond/",
            {"text": "First response"},
            format="json",
        )
        response = self.client.post(
            f"/api/v1/reviews/{review.id}/respond/",
            {"text": "Updated response"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["text"], "Updated response")
        self.assertEqual(ReviewResponse.objects.for_tenant(self.tenant).count(), 1)

    def test_customer_cannot_respond(self) -> None:
        """Customers cannot respond to reviews."""
        review = self._create_review()
        self._auth(self.customer_token)
        response = self.client.post(
            f"/api/v1/reviews/{review.id}/respond/",
            {"text": "self response"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_rating_validation(self) -> None:
        """Ratings outside 1-5 are rejected."""
        self._auth(self.customer_token)
        response = self.client.post(
            "/api/v1/reviews/",
            {"branch": self.branch.id, "rating": 6},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_tenant_isolation_api(self) -> None:
        """Reviews from another tenant are not visible."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_user = make_customer_user(other_tenant, "o@local.test")
        other_branch = make_branch(other_tenant, "Other Branch")
        other_review = Review.objects.create(
            tenant=other_tenant,
            customer=other_user.customer_profile,
            branch=other_branch,
            rating=4,
        )
        self._auth(self.owner_token)
        response = self.client.get(f"/api/v1/reviews/{other_review.id}/")
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_rejected(self) -> None:
        """Requests without a token are rejected."""
        self.client.credentials()
        response = self.client.get("/api/v1/reviews/")
        self.assertEqual(response.status_code, 401)


class ReviewSerializerTests(TestCase):
    """Tests for the review serializers."""

    def setUp(self) -> None:
        """Create tenant, branch, customer, and review."""
        self.tenant = provision_tenant(name="Gym", contact_email="owner@local.test")
        self.branch = make_branch(self.tenant)
        self.user = make_customer_user(self.tenant, "s@local.test")
        self.customer = self.user.customer_profile
        self.review = Review.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            branch=self.branch,
            rating=4,
            text="Nice place.",
        )

    def test_read_serializer_includes_customer_detail(self) -> None:
        """The read serializer nests the customer detail."""
        from apps.reviews.serializers import ReviewSerializer

        data = ReviewSerializer(self.review).data
        self.assertEqual(data["customer_detail"]["id"], self.customer.id)
        self.assertEqual(data["rating"], 4)
        self.assertEqual(data["branch"], self.branch.id)

    def test_write_serializer_rejects_customer(self) -> None:
        """Customers cannot set the customer field through the write serializer."""
        from apps.reviews.serializers import ReviewWriteSerializer

        serializer = ReviewWriteSerializer(
            data={"branch": self.branch.id, "rating": 5, "customer": 999}
        )
        self.assertTrue(serializer.is_valid())
        self.assertNotIn("customer", serializer.validated_data)

    def test_write_serializer_rating_validation(self) -> None:
        """The write serializer rejects out-of-range ratings."""
        from apps.reviews.serializers import ReviewWriteSerializer

        serializer = ReviewWriteSerializer(data={"branch": self.branch.id, "rating": 0})
        self.assertFalse(serializer.is_valid())
        self.assertIn("rating", serializer.errors)
