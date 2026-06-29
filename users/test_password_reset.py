"""
Password-reset OTP — model invariants + the full request → verify → confirm flow.

Security-sensitive surface: OTPs must be hashed at rest, expire, lock after
repeated failures, be single-use, and the request endpoint must not leak whether
an email exists. None of this was previously covered.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from users.models import PasswordResetOTP

REQ = "/api/auth/password-reset-request/"
VERIFY = "/api/auth/password-reset-verify/"
CONFIRM = "/api/auth/password-reset-confirm/"
LOGIN = "/api/auth/login/"


def _seed_otp(user, raw="654321", minutes=10):
    otp = PasswordResetOTP(user=user, expires_at=timezone.now() + timedelta(minutes=minutes))
    otp.set_otp(raw)
    otp.save()
    return otp


# --------------------------------------------------------------------------- #
# Model invariants (pure unit)
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestOTPModel:
    def test_otp_is_hashed_at_rest(self, test_user):
        otp = _seed_otp(test_user, "123456")
        assert otp.otp_code != "123456"          # never stored in clear
        assert "$" in otp.otp_code               # Django password-hash format

    def test_check_otp_accepts_correct_rejects_wrong(self, test_user):
        otp = _seed_otp(test_user, "123456")
        assert otp.check_otp("123456") is True
        assert otp.check_otp("000000") is False

    def test_is_expired_boundary(self, test_user):
        past = PasswordResetOTP(user=test_user, expires_at=timezone.now() - timedelta(seconds=1))
        future = PasswordResetOTP(user=test_user, expires_at=timezone.now() + timedelta(seconds=60))
        assert past.is_expired is True
        assert future.is_expired is False

    def test_is_locked_at_max_attempts(self, test_user):
        otp = PasswordResetOTP(user=test_user, expires_at=timezone.now() + timedelta(minutes=5))
        otp.failed_attempts = PasswordResetOTP.MAX_FAILED_ATTEMPTS - 1
        assert otp.is_locked is False
        otp.failed_attempts = PasswordResetOTP.MAX_FAILED_ATTEMPTS
        assert otp.is_locked is True


# --------------------------------------------------------------------------- #
# Request endpoint — must not enable email enumeration
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestResetRequest:
    def test_unknown_email_returns_generic_200(self, api_client):
        r = api_client.post(REQ, {"email": "nobody-here@example.com"}, format="json")
        assert r.status_code == 200
        assert not PasswordResetOTP.objects.exists()   # no record created

    def test_known_email_creates_otp_and_invalidates_prior(self, api_client, test_user):
        old = _seed_otp(test_user, "111111")
        r = api_client.post(REQ, {"email": test_user.email}, format="json")
        assert r.status_code == 200
        old.refresh_from_db()
        assert old.is_used is True                      # previous unused OTP retired
        # a fresh, unused OTP now exists
        assert PasswordResetOTP.objects.filter(user=test_user, is_used=False).exists()


# --------------------------------------------------------------------------- #
# Verify endpoint — wrong code, lockout, expiry, single use
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestResetVerify:
    def test_wrong_code_increments_then_locks(self, api_client, test_user):
        _seed_otp(test_user, "654321")
        last = None
        for _ in range(PasswordResetOTP.MAX_FAILED_ATTEMPTS):
            last = api_client.post(VERIFY, {"email": test_user.email, "otp_code": "000000"}, format="json")
        # 5th wrong attempt exhausts the allowance
        assert last.status_code == 429
        # a further attempt is locked out even if the code were correct
        again = api_client.post(VERIFY, {"email": test_user.email, "otp_code": "654321"}, format="json")
        assert again.status_code == 429

    def test_expired_otp_rejected(self, api_client, test_user):
        _seed_otp(test_user, "654321", minutes=-1)      # already expired
        r = api_client.post(VERIFY, {"email": test_user.email, "otp_code": "654321"}, format="json")
        assert r.status_code == 400

    def test_correct_code_is_single_use(self, api_client, test_user):
        _seed_otp(test_user, "654321")
        ok = api_client.post(VERIFY, {"email": test_user.email, "otp_code": "654321"}, format="json")
        assert ok.status_code == 200 and ok.json().get("reset_token")
        # verifying again finds no unused OTP -> rejected
        again = api_client.post(VERIFY, {"email": test_user.email, "otp_code": "654321"}, format="json")
        assert again.status_code == 400


# --------------------------------------------------------------------------- #
# Full happy path + confirm guards
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestResetConfirm:
    def test_full_flow_resets_password(self, api_client, test_user):
        _seed_otp(test_user, "654321")
        token = api_client.post(VERIFY, {"email": test_user.email, "otp_code": "654321"},
                                format="json").json()["reset_token"]
        new_pw = "BrandNewP@ss99"
        r = api_client.post(CONFIRM, {
            "email": test_user.email, "reset_token": token,
            "new_password": new_pw, "confirm_password": new_pw,
        }, format="json")
        assert r.status_code == 200
        # new password works, old one no longer does
        assert api_client.post(LOGIN, {"email": test_user.email, "password": new_pw},
                               format="json").status_code == 200
        assert api_client.post(LOGIN, {"email": test_user.email, "password": "TestPass123!"},
                               format="json").status_code in (400, 401)

    def test_confirm_with_bad_token_rejected(self, api_client, test_user):
        _seed_otp(test_user, "654321")
        r = api_client.post(CONFIRM, {
            "email": test_user.email, "reset_token": "not-a-real-token",
            "new_password": "Whatever123!", "confirm_password": "Whatever123!",
        }, format="json")
        assert r.status_code == 400

    def test_confirm_password_mismatch_rejected(self, api_client, test_user):
        _seed_otp(test_user, "654321")
        token = api_client.post(VERIFY, {"email": test_user.email, "otp_code": "654321"},
                                format="json").json()["reset_token"]
        r = api_client.post(CONFIRM, {
            "email": test_user.email, "reset_token": token,
            "new_password": "Mismatch123!", "confirm_password": "Different123!",
        }, format="json")
        assert r.status_code == 400
