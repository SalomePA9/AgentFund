"""
Unit tests for authentication module.
"""

from datetime import timedelta

import pytest
from jose import jwt


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        from api.auth import get_password_hash

        password = "secure_password_123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert hashed.startswith("$2b$")

    def test_password_verification_correct(self):
        """Test password verification with correct password."""
        from api.auth import get_password_hash, verify_password

        password = "secure_password_123"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_password_verification_incorrect(self):
        """Test password verification with incorrect password."""
        from api.auth import get_password_hash, verify_password

        password = "secure_password_123"
        hashed = get_password_hash(password)

        assert verify_password("wrong_password", hashed) is False

    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        from api.auth import get_password_hash

        hash1 = get_password_hash("password1")
        hash2 = get_password_hash("password2")

        assert hash1 != hash2

    def test_same_password_different_hashes(self):
        """Test that same password produces different hashes (due to salt)."""
        from api.auth import get_password_hash

        hash1 = get_password_hash("same_password")
        hash2 = get_password_hash("same_password")

        # Bcrypt includes random salt, so hashes should differ
        assert hash1 != hash2


class TestTokenCreation:
    """Tests for JWT token creation."""

    def test_create_access_token(self):
        """Test access token creation."""
        from api.auth import create_access_token

        user_id = "test-user-id-123"
        token = create_access_token(data={"sub": user_id})

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_user_id(self):
        """Test that token contains the user ID."""
        from api.auth import create_access_token
        from config import get_settings

        settings = get_settings()
        user_id = "test-user-id-123"
        token = create_access_token(data={"sub": user_id})

        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )

        assert payload["sub"] == user_id

    def test_token_has_expiration(self):
        """Test that token has an expiration time."""
        from api.auth import create_access_token
        from config import get_settings

        settings = get_settings()
        token = create_access_token(data={"sub": "test-user"})

        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )

        assert "exp" in payload

    def test_custom_expiration(self):
        """Test token with custom expiration delta."""
        from api.auth import create_access_token
        from config import get_settings

        settings = get_settings()
        token = create_access_token(
            data={"sub": "test-user"}, expires_delta=timedelta(minutes=5)
        )

        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )

        assert "exp" in payload


class TestUserSchemas:
    """Tests for user-related Pydantic schemas."""

    def test_user_create_valid(self):
        """Test UserCreate schema with valid data."""
        from api.auth import UserCreate

        user = UserCreate(email="test@example.com", password="password123")

        assert user.email == "test@example.com"
        assert user.password == "password123"

    def test_user_create_invalid_email(self):
        """Test UserCreate schema with invalid email."""
        from pydantic import ValidationError

        from api.auth import UserCreate

        with pytest.raises(ValidationError):
            UserCreate(email="invalid-email", password="password123")

    def test_user_settings_defaults(self):
        """Test UserSettings schema has correct defaults."""
        from api.auth import UserSettings

        settings = UserSettings()

        assert settings.timezone is None
        assert settings.report_time is None
        assert settings.email_reports is None
        assert settings.email_alerts is None


class TestAuthEndpoints:
    """Tests for authentication API endpoints."""

    @pytest.mark.api
    def test_register_success(self, client, mock_db):
        """Test successful user registration."""
        # Configure mock to return no existing user, then return created user
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {
                "id": "new-user-id",
                "email": "newuser@example.com",
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]

        response = client.post(
            "/api/auth/register",
            json={"email": "newuser@example.com", "password": "password123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"

    @pytest.mark.api
    def test_register_duplicate_email(self, client, mock_db):
        """Test registration with existing email."""
        # Configure mock to return existing user
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "existing-user"}
        ]

        response = client.post(
            "/api/auth/register",
            json={"email": "existing@example.com", "password": "password123"},
        )

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    @pytest.mark.api
    def test_login_success(self, client, mock_db, sample_user):
        """Test successful login."""
        from api.auth import get_password_hash

        # Create user with known password hash
        password = "test_password_123"
        sample_user["password_hash"] = get_password_hash(password)

        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]

        response = client.post(
            "/api/auth/login",
            data={"username": sample_user["email"], "password": password},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.api
    def test_login_wrong_password(self, client, mock_db, sample_user):
        """Test login with wrong password."""
        from api.auth import get_password_hash

        sample_user["password_hash"] = get_password_hash("correct_password")

        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]

        response = client.post(
            "/api/auth/login",
            data={"username": sample_user["email"], "password": "wrong_password"},
        )

        assert response.status_code == 401

    @pytest.mark.api
    def test_login_nonexistent_user(self, client, mock_db):
        """Test login with non-existent user."""
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )

        response = client.post(
            "/api/auth/login",
            data={"username": "nonexistent@example.com", "password": "password"},
        )

        assert response.status_code == 401

    @pytest.mark.api
    def test_get_current_user(self, client, mock_db, sample_user, auth_headers):
        """Test getting current user info."""
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]

        response = client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == sample_user["email"]

    @pytest.mark.api
    def test_get_current_user_unauthorized(self, client):
        """Test getting user info without token."""
        response = client.get("/api/auth/me")

        assert response.status_code == 401

    @pytest.mark.api
    def test_get_current_user_invalid_token(self, client):
        """Test getting user info with invalid token."""
        response = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer invalid-token"}
        )

        assert response.status_code == 401

    @pytest.mark.api
    def test_logout(self, client):
        """Test logout endpoint."""
        response = client.post("/api/auth/logout")

        assert response.status_code == 200
        assert "logged out" in response.json()["message"].lower()
