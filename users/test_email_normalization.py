"""
Regression tests for G3 — email is a case-insensitive identity.

A case variant of an existing email must not create a second account, emails
are stored canonically lower-cased, and login works regardless of the case the
user types.
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

REGISTER = "/api/auth/register/"
LOGIN = "/api/auth/login/"


def _reg_payload(username, email):
    return {
        "username": username, "email": email, "name": "X",
        "first_name": "X", "last_name": "Y", "phone": "9999999999",
        "password": "TestPass123!", "password2": "TestPass123!",
    }


@pytest.mark.django_db
class TestEmailNormalization:
    def test_email_stored_lowercase(self, db):
        u = User.objects.create_user(username="up", email="Mixed.Case@Example.COM", password="x")
        u.refresh_from_db()
        assert u.email == "mixed.case@example.com"

    def test_register_lowercases_email(self, api_client):
        r = api_client.post(REGISTER, _reg_payload("u1", "New.User@Example.com"), format="json")
        assert r.status_code in (200, 201)
        assert User.objects.filter(email="new.user@example.com").exists()

    def test_case_variant_registration_rejected(self, api_client):
        first = api_client.post(REGISTER, _reg_payload("u1", "dup@example.com"), format="json")
        assert first.status_code in (200, 201)
        second = api_client.post(REGISTER, _reg_payload("u2", "DUP@example.com"), format="json")
        assert second.status_code == 400
        assert User.objects.filter(email__iexact="dup@example.com").count() == 1

    def test_login_is_case_insensitive(self, api_client):
        api_client.post(REGISTER, _reg_payload("u1", "case@example.com"), format="json")
        for typed in ("case@example.com", "CASE@example.com", "Case@Example.Com"):
            r = api_client.post(LOGIN, {"email": typed, "password": "TestPass123!"}, format="json")
            assert r.status_code == 200, f"login failed for {typed!r}"


@pytest.mark.django_db
class TestProfileEmailUpdate:
    """G8 — the profile update path must apply the same email rules, not 500."""

    def test_case_variant_of_other_user_rejected_cleanly(self, authenticated_client, test_user):
        # another account owns victim@example.com
        User.objects.create_user(username="victim", email="victim@example.com", password="x")
        r = authenticated_client.patch("/api/auth/profile/", {"email": "VICTIM@example.com"}, format="json")
        assert r.status_code == 400            # clean validation error, NOT a 500
        test_user.refresh_from_db()
        assert test_user.email != "victim@example.com"

    def test_profile_email_is_normalized(self, authenticated_client, test_user):
        r = authenticated_client.patch("/api/auth/profile/", {"email": "New.Me@Example.COM"}, format="json")
        assert r.status_code == 200
        test_user.refresh_from_db()
        assert test_user.email == "new.me@example.com"

    def test_can_keep_own_email_unchanged(self, authenticated_client, test_user):
        # PATCHing the same email (any case) must not trip the uniqueness check on self.
        r = authenticated_client.patch(
            "/api/auth/profile/", {"email": test_user.email.upper(), "city": "Pune"}, format="json")
        assert r.status_code == 200
        test_user.refresh_from_db()
        assert test_user.city == "Pune"
