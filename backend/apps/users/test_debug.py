import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token
from apps.users.trainer_services import create_trainer

User = get_user_model()

class DebugTest(APITestCase):
    def test_debug_create(self):
        tenant = provision_tenant(name="Gym", contact_email="gym@local.test")
        owner = create_owner_user(
            tenant=tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner",
        )
        token = issue_token(owner, tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        trainer = create_trainer(
            tenant=tenant,
            email="trainer@local.test",
            first_name="John",
            last_name="Doe",
            specialization="Strength",
            experience_years=5,
        )
        response = self.client.post(
            "/api/v1/users/trainers/",
            {
                "email": "newtrainer@local.test",
                "first_name": "New",
                "last_name": "Trainer",
                "password": "F1tNati0n!",
                "specialization": "Yoga",
                "bio": "Yoga instructor",
                "experience_years": 3,
                "max_clients": 25,
                "certifications": [
                    {"name": "RYT-200", "issuer": "Yoga Alliance", "year": 2019, "expiry": None},
                ],
                "profile_photo": "https://cdn.fitnation.com/photos/new.jpg",
            },
        )
        print(f"STATUS: {response.status_code}")
        print(f"DATA: {response.data}")
        assert True
