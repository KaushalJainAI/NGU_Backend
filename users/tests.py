"""
Comprehensive tests for the Users app.
Covers authentication, registration, profile management, and security testing.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()


# ==================== REGISTRATION TESTS ====================

@pytest.mark.django_db
class TestUserRegistration:
    """Tests for user registration endpoint."""
    
    url = '/api/auth/register/'
    
    def test_register_valid_user(self, api_client):
        """Test successful user registration with valid data."""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'first_name': 'New',
            'last_name': 'User',
            'phone': '9876543210'
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert 'user' in response.data
        assert response.data['user']['email'] == 'newuser@example.com'
        assert User.objects.filter(email='newuser@example.com').exists()
    
    def test_register_duplicate_email(self, api_client, test_user):
        """Test registration fails with duplicate email."""
        data = {
            'username': 'anotheruser',
            'email': test_user.email,  # Duplicate
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_register_duplicate_username(self, api_client, test_user):
        """Test registration fails with duplicate username."""
        data = {
            'username': test_user.username,  # Duplicate
            'email': 'unique@example.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_register_password_mismatch(self, api_client):
        """Test registration fails when passwords don't match."""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'StrongPass123!',
            'password2': 'DifferentPass123!',
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'password' in str(response.data).lower()
    
    def test_register_weak_password(self, api_client):
        """Test registration fails with weak password."""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': '123',  # Too weak
            'password2': '123',
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_register_missing_required_fields(self, api_client):
        """Test registration fails with missing required fields."""
        data = {
            'username': 'newuser',
            # Missing email, password, password2
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_register_invalid_email(self, api_client):
        """Test registration fails with invalid email format."""
        data = {
            'username': 'newuser',
            'email': 'not-an-email',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_register_sql_injection_in_username(self, api_client, malicious_inputs):
        """Test SQL injection attempts are handled safely."""
        for payload in malicious_inputs.SQL_INJECTION:
            data = {
                'username': payload,
                'email': 'test@example.com',
                'password': 'StrongPass123!',
                'password2': 'StrongPass123!',
            }
            response = api_client.post(self.url, data, format='json')
            # Should return 400 (invalid) or 201 (sanitized), never 500
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_register_xss_in_name_fields(self, api_client, malicious_inputs):
        """Test XSS payloads are handled safely."""
        for payload in malicious_inputs.XSS_PAYLOADS:
            data = {
                'username': 'testuser123',
                'email': 'xsstest@example.com',
                'password': 'StrongPass123!',
                'password2': 'StrongPass123!',
                'first_name': payload,
                'last_name': payload,
            }
            response = api_client.post(self.url, data, format='json')
            # Should not cause 500 error
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_register_oversized_payload(self, api_client, malicious_inputs):
        """Test oversized payloads are handled gracefully."""
        data = {
            'username': malicious_inputs.OVERSIZED_STRING[:150],  # Truncate for username
            'email': 'test@example.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'address': malicious_inputs.OVERSIZED_STRING,
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_register_unicode_characters(self, api_client, malicious_inputs):
        """Test Unicode characters are handled properly."""
        for payload in malicious_inputs.UNICODE_EDGE_CASES:
            data = {
                'username': f'user_{abs(hash(payload)) % 10000}',
                'email': f'unicode{abs(hash(payload)) % 10000}@example.com',
                'password': 'StrongPass123!',
                'password2': 'StrongPass123!',
                'first_name': payload,
            }
            response = api_client.post(self.url, data, format='json')
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR


# ==================== LOGIN TESTS ====================

@pytest.mark.django_db
class TestUserLogin:
    """Tests for user login endpoint."""
    
    url = '/api/auth/login/'
    
    def test_login_valid_credentials(self, api_client, test_user):
        """Test successful login with valid credentials."""
        data = {
            'email': test_user.email,
            'password': 'TestPass123!'
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
    
    def test_login_invalid_password(self, api_client, test_user):
        """Test login fails with wrong password."""
        data = {
            'email': test_user.email,
            'password': 'WrongPassword123!'
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_login_nonexistent_user(self, api_client):
        """Test login fails for non-existent user."""
        data = {
            'email': 'nonexistent@example.com',
            'password': 'SomePassword123!'
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_login_missing_fields(self, api_client):
        """Test login fails with missing fields."""
        response = api_client.post(self.url, {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_login_empty_password(self, api_client, test_user):
        """Test login fails with empty password."""
        data = {
            'email': test_user.email,
            'password': ''
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_login_sql_injection(self, api_client, malicious_inputs):
        """Test SQL injection in login is handled safely."""
        for payload in malicious_inputs.SQL_INJECTION:
            data = {
                'email': payload,
                'password': payload
            }
            response = api_client.post(self.url, data, format='json')
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR


# ==================== PROFILE TESTS ====================

@pytest.mark.django_db
class TestUserProfile:
    """Tests for user profile endpoint."""
    
    url = '/api/auth/profile/'
    
    def test_get_profile_authenticated(self, authenticated_client, test_user):
        """Test getting profile when authenticated."""
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == test_user.email
        assert response.data['username'] == test_user.username
    
    def test_get_profile_unauthenticated(self, api_client):
        """Test getting profile without authentication fails."""
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_update_profile(self, authenticated_client, test_user):
        """Test updating profile fields."""
        data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone': '1111111111'
        }
        response = authenticated_client.patch(self.url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'Updated'
        
        # Verify in database
        test_user.refresh_from_db()
        assert test_user.first_name == 'Updated'
    
    def test_update_profile_readonly_fields(self, authenticated_client, test_user):
        """Test that read-only fields cannot be modified."""
        original_id = test_user.id
        data = {
            'id': 999999,  # Should be read-only
        }
        response = authenticated_client.patch(self.url, data, format='json')
        # Should succeed but ignore read-only field
        test_user.refresh_from_db()
        assert test_user.id == original_id
    
    def test_update_profile_xss_payload(self, authenticated_client, malicious_inputs):
        """Test XSS payloads in profile update."""
        for payload in malicious_inputs.XSS_PAYLOADS:
            data = {'first_name': payload}
            response = authenticated_client.patch(self.url, data, format='json')
            assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_profile_with_invalid_token(self, api_client):
        """Test profile access with invalid token."""
        api_client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token_here')
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ==================== PASSWORD CHANGE TESTS ====================

@pytest.mark.django_db
class TestPasswordChange:
    """Tests for password change endpoint."""
    
    url = '/api/auth/change-password/'
    
    def test_change_password_valid(self, authenticated_client, test_user):
        """Test successful password change."""
        data = {
            'old_password': 'TestPass123!',
            'new_password': 'NewStrongPass456!'
        }
        response = authenticated_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        
        # Verify new password works
        test_user.refresh_from_db()
        assert test_user.check_password('NewStrongPass456!')
    
    def test_change_password_wrong_old_password(self, authenticated_client):
        """Test password change fails with wrong old password."""
        data = {
            'old_password': 'WrongOldPassword!',
            'new_password': 'NewStrongPass456!'
        }
        response = authenticated_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_change_password_missing_fields(self, authenticated_client):
        """Test password change fails with missing fields."""
        data = {
            'old_password': 'TestPass123!'
            # Missing new_password
        }
        response = authenticated_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_change_password_unauthenticated(self, api_client):
        """Test password change without authentication fails."""
        data = {
            'old_password': 'TestPass123!',
            'new_password': 'NewStrongPass456!'
        }
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_change_password_empty_new_password(self, authenticated_client):
        """Test password change fails with empty new password."""
        data = {
            'old_password': 'TestPass123!',
            'new_password': ''
        }
        response = authenticated_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==================== TOKEN REFRESH TESTS ====================

@pytest.mark.django_db
class TestTokenRefresh:
    """Tests for token refresh endpoint."""
    
    url = '/api/auth/token/refresh/'
    
    def test_refresh_valid_token(self, api_client, test_user):
        """Test token refresh with valid refresh token."""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(test_user)
        
        data = {'refresh': str(refresh)}
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
    
    def test_refresh_invalid_token(self, api_client):
        """Test token refresh with invalid token fails."""
        data = {'refresh': 'invalid_refresh_token'}
        response = api_client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_refresh_missing_token(self, api_client):
        """Test token refresh without token fails."""
        response = api_client.post(self.url, {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==================== EDGE CASES ====================

@pytest.mark.django_db
class TestUserEdgeCases:
    """Edge case tests for user-related endpoints."""
    
    def test_register_empty_request_body(self, api_client):
        """Test registration with empty request body."""
        response = api_client.post('/api/auth/register/', {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_register_null_values(self, api_client):
        """Test registration with null values."""
        data = {
            'username': None,
            'email': None,
            'password': None,
            'password2': None,
        }
        response = api_client.post('/api/auth/register/', data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_login_empty_request_body(self, api_client):
        """Test login with empty request body."""
        response = api_client.post('/api/auth/login/', {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_profile_put_vs_patch(self, authenticated_client):
        """Test PUT request to profile endpoint."""
        data = {
            'first_name': 'Updated'
        }
        response = authenticated_client.put('/api/auth/profile/', data, format='json')
        # PUT might require all fields - should not cause 500
        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_special_characters_in_address(self, authenticated_client):
        """Test special characters in address field."""
        data = {
            'address': '123 Main St. #Apt-5, (Near Park), City & State'
        }
        response = authenticated_client.patch('/api/auth/profile/', data, format='json')
        assert response.status_code == status.HTTP_200_OK
