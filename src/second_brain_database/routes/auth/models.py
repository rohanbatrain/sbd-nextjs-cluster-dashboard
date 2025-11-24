"""
# Authentication Models

This module defines the **Pydantic models** used for all authentication-related operations,
including user registration, login, token management, and two-factor authentication.
It enforces strict validation rules to ensure data integrity and security.

## Domain Model Overview

The authentication system is built around several core entities:

- **User**: The primary identity, with separate models for Input (`UserIn`), Output (`UserOut`), and Database (`UserInDB`).
- **Token**: JWT credentials (`Token`) for session management.
- **Permanent Token**: Long-lived API keys (`PermanentToken`) for machine-to-machine access.
- **2FA**: Models for Time-based One-Time Password (TOTP) setup and verification.

## Key Features

### 1. Robust Validation
- **Password Strength**: Enforces complexity (length, case, digits, special chars).
- **Input Sanitization**: Normalizes usernames and emails to lowercase.
- **Plan Control**: Restricts new registrations to the 'free' plan.

### 2. Security Best Practices
- **Data Hiding**: `UserOut` automatically excludes sensitive fields (passwords, secrets).
- **Audit Logging**: Dedicated models (`LoginLog`, `RegistrationLog`) for security auditing.

## Usage Examples

### Validating a New User Registration

```python
try:
    user = UserIn(
        username="john_doe",
        email="john@example.com",
        password="SecurePassword123!"
    )
except ValueError as e:
    print(f"Validation failed: {e}")
```

## Module Attributes

Attributes:
    PASSWORD_MIN_LENGTH (int): Minimum required password length (8).
    USERNAME_MIN_LENGTH (int): Minimum username length (3).
    USERNAME_REGEX (str): Regex pattern for valid usernames.
"""

from datetime import datetime
import re
from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, EmailStr, Field, field_validator

from second_brain_database.docs.models import BaseDocumentedModel
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Auth Models]")

# Constants for password validation
PASSWORD_MIN_LENGTH: int = 8
USERNAME_MIN_LENGTH: int = 3
USERNAME_MAX_LENGTH: int = 50
PASSWORD_SPECIAL_CHARS: str = r"!@#$%^&*(),.?\":{}|<>"
USERNAME_REGEX: str = r"^[a-zA-Z0-9_-]+$"


class PasswordValidationResult(TypedDict):
    """
    A TypedDict representing the result of a password validation check.

    Attributes:
        valid (bool): Indicates whether the password passed validation.
        reason (str): Provides the reason for validation failure, or an explanatory message.
    """

    valid: bool
    reason: str


def validate_password_strength(password: str) -> bool:
    """
    Validates that a password meets the defined strength requirements.

    This function performs a comprehensive check against multiple security criteria to ensure
    user passwords are robust against brute-force and dictionary attacks.

    **Requirements:**
    1.  **Length**: Minimum 8 characters (`PASSWORD_MIN_LENGTH`).
    2.  **Uppercase**: At least one uppercase letter (A-Z).
    3.  **Lowercase**: At least one lowercase letter (a-z).
    4.  **Digit**: At least one numeric digit (0-9).
    5.  **Special Character**: At least one special character from `!@#$%^&*(),.?":{}|<>`.

    Args:
        password (str): The plain-text password to validate.

    Returns:
        bool: `True` if the password meets all requirements, `False` otherwise.

    Side Effects:
        Logs a warning message with the specific reason for failure if validation fails.
        This helps in debugging and monitoring password policy compliance.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        logger.warning("Password validation failed: too short")
        return False
    if not re.search(r"[A-Z]", password):
        logger.warning("Password validation failed: missing uppercase letter")
        return False
    if not re.search(r"[a-z]", password):
        logger.warning("Password validation failed: missing lowercase letter")
        return False
    if not re.search(r"\d", password):
        logger.warning("Password validation failed: missing digit")
        return False
    if not re.search(f"[{PASSWORD_SPECIAL_CHARS}]", password):
        logger.warning("Password validation failed: missing special character")
        return False
    return True


class UserIn(BaseDocumentedModel):
    """
    Input model for new user registration.

    This model handles the validation and normalization of user data during the sign-up process.
    It enforces strict rules on usernames, emails, and passwords to ensure system consistency
    and security.

    **Validation Rules:**
    *   **Username**: Must be 3-50 characters long, containing only alphanumeric characters,
        dashes, or underscores. Automatically converted to lowercase to ensure uniqueness.
    *   **Email**: Must be a valid email format. Automatically converted to lowercase.
    *   **Password**: Must meet strict strength requirements (length, complexity) as defined
        in `validate_password_strength`.
    *   **Plan**: Defaults to 'free'. Attempts to register with other plans will raise an error.
    *   **Role**: Defaults to 'user'. Cannot be overridden during registration.

    **Security Note:**
    This model accepts a plain-text password. It should only be used in the registration endpoint
    where the password will be immediately hashed before storage.
    """

    username: str = Field(
        ...,
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        description="Unique username for the account. Must be 3-50 characters, containing only letters, numbers, dashes, and underscores. Will be converted to lowercase.",
        example="john_doe",
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address for account verification and communication. Will be converted to lowercase.",
        example="john.doe@example.com",
    )
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        description="Account password. Must be at least 8 characters and include uppercase, lowercase, number, and special character.",
        example="SecurePassword123!",
    )
    plan: Optional[str] = Field(
        default="free", description="User subscription plan. Only 'free' plan allowed for new registrations.", example="free"
    )
    team: Optional[List[str]] = Field(
        default_factory=list,
        description="List of team identifiers the user belongs to. Empty by default.",
        example=["team_alpha", "project_beta"],
    )
    role: Optional[str] = Field(
        default="user", description="User role in the system. Defaults to 'user' for standard accounts.", example="user"
    )
    is_verified: bool = Field(
        default=False,
        description="Email verification status. Always false for new registrations until email is verified.",
        example=False,
    )
    client_side_encryption: bool = Field(
        default=False,
        description="Whether the user wants to enable client-side encryption for their data.",
        example=False,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "email": "john.doe@example.com",
                "password": "SecurePassword123!",
                "plan": "free",
                "team": [],
                "role": "user",
                "is_verified": False,
                "client_side_encryption": False,
            }
        }
    }

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Validate username contains only alphanumeric characters, dashes, and underscores. Unicode is not allowed.
        Args:
            v (str): The username to validate.
        Returns:
            str: The validated username in lowercase.
        Raises:
            ValueError: If username is invalid.
        Side-effects:
            Logs error if username is invalid.
        """
        if not re.match(USERNAME_REGEX, v):
            logger.error("Invalid username: %s", v)
            raise ValueError("Username must contain only alphanumeric characters, dashes, and underscores (no Unicode)")
        return v.lower()

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """
        Validate and normalize email address.
        Args:
            v (str): The email to validate.
        Returns:
            str: The validated email in lowercase.
        """
        return v.lower()

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: Optional[str]) -> str:
        """
        Validate and enforce plan restrictions for new user registrations.
        
        Only allows 'free' plan for new registrations. This prevents users from
        self-assigning premium plans during signup, ensuring proper subscription controls.
        
        Args:
            v (Optional[str]): The plan value to validate.
        Returns:
            str: Always returns 'free' for new registrations.
        Raises:
            ValueError: If user attempts to register with non-free plan.
        Side-effects:
            Logs security events for attempted premium plan registrations.
        """
        if v is None:
            return "free"
        
        if v.lower() != "free":
            logger.warning("Attempted registration with non-free plan: %s", v)
            raise ValueError("Only 'free' plan is allowed for new user registrations. Premium plans must be upgraded after account creation.")
        
        return "free"


class UserOut(BaseDocumentedModel):
    """
    User output model for API responses.

    Contains safe user information without sensitive data like passwords.
    Used in API responses to provide user profile information securely.

    **Security Note:** This model excludes sensitive fields like passwords,
    2FA secrets, and internal security tracking data.
    """

    username: str = Field(..., description="The user's unique username, always in lowercase", example="john_doe")
    email: str = Field(
        ..., description="The user's email address, used for communication and login", example="john.doe@example.com"
    )
    created_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the user account was created",
        example="2024-01-01T10:00:00Z",
    )
    last_login: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of the user's last successful login",
        example="2024-01-01T15:30:00Z",
    )
    is_active: bool = Field(
        default=True, description="Whether the user account is active and can be used for login", example=True
    )
    plan: Optional[str] = Field(default="free", description="The user's current subscription plan", example="free")
    team: Optional[List[str]] = Field(
        default_factory=list,
        description="List of team identifiers the user belongs to",
        example=["team_alpha", "project_beta"],
    )
    role: Optional[str] = Field(
        default="user", description="The user's role in the system (user, admin, etc.)", example="user"
    )
    is_verified: bool = Field(
        default=False, description="Whether the user's email address has been verified", example=True
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "john_doe",
                "email": "john.doe@example.com",
                "created_at": "2024-01-01T10:00:00Z",
                "last_login": "2024-01-01T15:30:00Z",
                "is_active": True,
                "plan": "free",
                "team": ["team_alpha"],
                "role": "user",
                "is_verified": True,
            }
        }
    }


class UserInDB(BaseModel):
    """
    User database model representing the complete user document stored in MongoDB.

    This model contains the **full state** of a user account, including sensitive security credentials
    and internal tracking fields that are never exposed via the API. It serves as the source of truth
    for user authentication and authorization.

    **Sensitive Fields (Internal Only):**
    *   **hashed_password**: The bcrypt hash of the user's password. Never store plain text.
    *   **totp_secret**: The encrypted secret key for 2FA generation.
    *   **backup_codes**: Hashed one-time codes for emergency account access.
    *   **reset_blocklist**: List of used password reset tokens to prevent replay attacks.

    **Security Tracking:**
    *   **failed_login_attempts**: Counter for rate limiting and account locking.
    *   **reset_whitelist**: List of active password reset tokens.

    **Usage:**
    This model is used exclusively by the `UserService` and `AuthService` for database interactions.
    It should **never** be returned directly to the client. Use `UserOut` for API responses.
    """

    username: str
    email: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow, description="UTC time when the user was created")
    is_active: bool = True
    failed_login_attempts: int = 0
    last_login: Optional[datetime] = Field(
        default_factory=datetime.utcnow, description="UTC time when the user last logged in"
    )
    plan: Optional[str] = "free"
    team: Optional[List[str]] = Field(default_factory=list)
    role: Optional[str] = "user"
    is_verified: bool = False
    two_fa_enabled: bool = False
    totp_secret: Optional[str] = None
    backup_codes: Optional[List[str]] = None
    backup_codes_used: Optional[List[int]] = None
    reset_blocklist: Optional[List[str]] = Field(default_factory=list)
    reset_whitelist: Optional[List[str]] = Field(default_factory=list)


class Token(BaseDocumentedModel):
    """
    JWT token response model containing access and refresh tokens.

    This model is returned upon successful authentication (login, registration, refresh).
    It provides the client with the necessary credentials to access protected API endpoints.

    **Token Structure:**
    *   **access_token**: A short-lived (15 min) JWT used for API authorization.
        Must be included in the `Authorization` header as `Bearer <token>`.
    *   **refresh_token**: A long-lived (7 days) JWT used to obtain new access tokens
        when the current one expires. This enables a seamless user experience without
        frequent re-logins.
    *   **token_type**: Always "bearer" for OAuth2 compatibility.
    *   **expires_in**: The lifetime of the access token in seconds.
    *   **refresh_expires_in**: The lifetime of the refresh token in seconds.

    **Refresh Flow:**
    1.  Client uses `access_token` for API requests.
    2.  When `access_token` expires (401 Unauthorized), client sends `refresh_token`
        to the `/auth/refresh` endpoint.
    3.  Server validates `refresh_token` and issues a new pair of tokens.
    """

    access_token: str = Field(
        ...,
        description="JWT access token for API authentication. Include in Authorization header as 'Bearer <token>'. Expires in 15 minutes.",
        example="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb2huX2RvZSIsImV4cCI6MTY0MDk5NTIwMH0.example_signature",
    )
    refresh_token: Optional[str] = Field(
        None,
        description="JWT refresh token for obtaining new access tokens. Use at /auth/refresh endpoint. Expires in 7 days.",
        example="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb2huX2RvZSIsInR5cGUiOiJyZWZyZXNoIn0.example_signature",
    )
    token_type: str = Field(
        default="bearer", description="Token type, always 'bearer' for JWT tokens", example="bearer"
    )
    expires_in: Optional[int] = Field(
        None,
        description="Access token expiration time in seconds (900 = 15 minutes)",
        example=900,
    )
    refresh_expires_in: Optional[int] = Field(
        None,
        description="Refresh token expiration time in seconds (604800 = 7 days)",
        example=604800,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb2huX2RvZSIsImV4cCI6MTY0MDk5NTIwMH0.example_signature",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb2huX2RvZSIsInR5cGUiOiJyZWZyZXNoIn0.example_signature",
                "token_type": "bearer",
                "expires_in": 900,
                "refresh_expires_in": 604800,
            }
        }
    }


class TokenData(BaseModel):
    """
    Internal model for decoded JWT payload data.

    This model represents the structured data extracted from a validated JWT access token.
    It is used throughout the application to identify the authenticated user associated
    with the current request.

    **Fields:**
    *   **username**: The subject (`sub` claim) of the token, identifying the user.

    **Usage:**
    The `get_current_user` dependency decodes the bearer token into this model
    before fetching the full user record from the database.
    """

    username: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    """
    Request model for changing a user's password.

    This model requires both the current password (for verification) and the new password.
    The new password must meet the same strict complexity requirements as registration.

    **Validation:**
    *   **old_password**: Verified against the stored hash in the database.
    *   **new_password**: Must be at least 8 characters, with mix of case, numbers, and special chars.

    **Security:**
    Changing the password will invalidate all existing sessions (except the current one)
    and revoke all refresh tokens to ensure account security.
    """

    old_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        description="New password. Must meet strength requirements (8+ chars, mixed case, special chars).",
        example="NewSecurePassword456!",
    )


class TwoFASetupRequest(BaseModel):
    """
    Request model for initiating Two-Factor Authentication (2FA) setup.

    **Supported Methods:**
    *   **totp**: Time-based One-Time Password (e.g., Google Authenticator, Authy).
        Generates a QR code for the user to scan.
    *   **email**: (Future) Send OTP codes via email.
    *   **passkey**: (Future) WebAuthn/FIDO2 passkey support.

    **Flow:**
    1. Client sends this request with desired method.
    2. Server returns `TwoFASetupResponse` with secret/QR code.
    3. Client verifies setup with `TwoFAVerifyRequest`.
    """

    method: str = Field(..., description="The 2FA method to enable.", example="totp")


class TwoFAVerifyRequest(BaseModel):
    """
    Request model for verifying and finalizing 2FA setup.

    This step confirms that the user has successfully configured their authenticator app
    and can generate valid codes.

    **Validation:**
    *   **code**: Must be a valid 6-digit TOTP code generated from the secret provided in setup.
    *   **method**: Must match the method requested in setup.

    **Outcome:**
    On success, 2FA is enabled for the account and backup codes are generated/returned.
    """

    method: str = Field(..., description="The 2FA method being verified.", example="totp")
    code: str = Field(..., description="The 6-digit verification code.", example="123456")


class TwoFAStatus(BaseModel):
    """
    Response model for current 2FA configuration status.

    Provides the client with the current security state of the account regarding 2FA.

    **Fields:**
    *   **enabled**: Global flag indicating if 2FA is enforced for login.
    *   **methods**: List of active 2FA methods (e.g., `['totp']`).
    *   **pending**: If `True`, setup was started but not verified.
    *   **backup_codes**: **Only** returned immediately after successful setup/verification.
        Otherwise `None`.
    """

    enabled: bool
    methods: Optional[List[str]] = Field(default_factory=list)
    pending: Optional[bool] = False
    backup_codes: Optional[List[str]] = None


class TwoFASetupResponse(BaseModel):
    """
    Response model for 2FA setup, including secret and provisioning URI for TOTP.
    """

    enabled: bool
    methods: Optional[List[str]] = Field(default_factory=list)
    totp_secret: Optional[str] = None
    provisioning_uri: Optional[str] = None
    qr_code_data: Optional[str] = None
    backup_codes: Optional[List[str]] = None


class LoginRequest(BaseDocumentedModel):
    """
    Login request model supporting 2FA fields.

    Accepts either username or email (at least one required), password, and optional 2FA code/method.
    Supports both standard login and two-factor authentication flows.

    **Authentication Flow:**
    1. Standard login: Provide username/email and password
    2. 2FA login: Include two_fa_code and two_fa_method after initial attempt

    **Supported 2FA Methods:** totp, backup
    """

    username: Optional[str] = Field(
        None, description="Username for login. Either username or email must be provided.", example="john_doe"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Email address for login. Either username or email must be provided.",
        example="john.doe@example.com",
    )
    password: str = Field(..., description="User's password for authentication", example="SecurePassword123!")
    two_fa_code: Optional[str] = Field(
        None,
        description="Two-factor authentication code. Required if 2FA is enabled for the account.",
        example="123456",
    )
    two_fa_method: Optional[str] = Field(
        None,
        description="Two-factor authentication method. Options: 'totp' (authenticator app), 'backup' (backup codes)",
        example="totp",
    )
    client_side_encryption: bool = Field(
        default=False, description="Whether to enable client-side encryption for this session", example=False
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Standard Login",
                    "summary": "Login with username and password",
                    "value": {
                        "username": "john_doe",
                        "password": "SecurePassword123!",
                        "client_side_encryption": False,
                    },
                },
                {
                    "name": "Email Login",
                    "summary": "Login with email and password",
                    "value": {
                        "email": "john.doe@example.com",
                        "password": "SecurePassword123!",
                        "client_side_encryption": False,
                    },
                },
                {
                    "name": "2FA Login",
                    "summary": "Login with 2FA authentication",
                    "value": {
                        "username": "john_doe",
                        "password": "SecurePassword123!",
                        "two_fa_code": "123456",
                        "two_fa_method": "totp",
                        "client_side_encryption": False,
                    },
                },
            ]
        }
    }

    @classmethod
    def model_validate(cls, data):
        # Pydantic v2: use model_validate for cross-field validation
        obj = super().model_validate(data)
        if not obj.username and not obj.email:
            raise ValueError("Either username or email must be provided.")
        return obj


class LoginLog(BaseModel):
    """
    Audit log model for tracking user login attempts.

    This model captures detailed information about every login attempt (successful or failed)
    to support security monitoring, threat detection, and compliance auditing.

    **Captured Data:**
    *   **Context**: Timestamp, IP address, and User Agent string.
    *   **Identity**: Username and email attempted.
    *   **Result**: Success/Failure status and detailed reason for failure.
    *   **Security**: MFA status (whether 2FA was challenged/completed).

    **Usage:**
    Instances of this model are asynchronously written to the `auth_logs` collection
    via the `AuthService.log_login_attempt` method.
    """

    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    username: str
    email: Optional[str] = None
    outcome: str  # 'success' or 'failure'
    reason: Optional[str] = None
    mfa_status: Optional[bool] = None


class RegistrationLog(BaseModel):
    """
    Audit log model for tracking new user registration events.

    This model records the details of every account creation attempt, helping to monitor
    growth, detect spam/bot registrations, and troubleshoot signup issues.

    **Captured Data:**
    *   **Context**: Timestamp, IP address, and User Agent.
    *   **Identity**: Registered username and email.
    *   **Configuration**: Selected plan and assigned role.
    *   **Result**: Success/Failure status and failure reason (e.g., "username_taken").

    **Usage:**
    Written to the `auth_logs` collection immediately after a registration attempt is processed.
    """

    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    username: str
    email: str
    outcome: str  # 'success' or 'failure:reason'
    reason: Optional[str] = None
    plan: Optional[str] = None
    role: Optional[str] = None


# Permanent Token Models


class PermanentTokenRequest(BaseDocumentedModel):
    """
    Request model for creating a new permanent API token.

    Permanent tokens are distinct from regular user sessions in that they do not expire
    by default and are intended for machine-to-machine communication.

    **Use Cases:**
    *   **CI/CD Pipelines**: Authenticating deployment scripts (e.g., GitHub Actions).
    *   **Integrations**: Connecting third-party services (e.g., Slack bots, Zapier).
    *   **Background Jobs**: Long-running processes that need API access.

    **Security Features:**
    *   **IP Restrictions**: Optional allowlist of IP addresses/CIDRs to restrict usage.
    *   **Expiration**: Optional expiration date for temporary access.
    *   **Auditing**: All token usage is logged and tracked.

    **Note:** The generated token is cryptographically secure and stored as a hash.
    The plain-text token is only shown once upon creation.
    """

    description: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional description to identify the token's purpose. Helps with token management and auditing.",
        example="CI/CD Pipeline Token for GitHub Actions",
    )
    ip_restrictions: Optional[List[str]] = Field(
        None,
        description="Optional list of IP addresses or CIDR blocks that can use this token. Leave empty for no restrictions.",
        example=["192.168.1.0/24", "10.0.0.0/8"],
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Optional expiration date for the token. If not provided, token will not expire.",
        example="2024-12-31T23:59:59Z",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "CI/CD Token",
                    "summary": "Token for continuous integration",
                    "value": {
                        "description": "GitHub Actions CI/CD Pipeline",
                        "ip_restrictions": ["192.30.252.0/22", "185.199.108.0/22"],
                        "expires_at": None,
                    },
                },
                {
                    "name": "Integration Token",
                    "summary": "Token for third-party integration",
                    "value": {
                        "description": "Slack Bot Integration",
                        "ip_restrictions": [],
                        "expires_at": "2024-12-31T23:59:59Z",
                    },
                },
                {
                    "name": "Development Token",
                    "summary": "Token for local development",
                    "value": {
                        "description": "Local Development Environment",
                        "ip_restrictions": ["127.0.0.1/32", "192.168.1.0/24"],
                        "expires_at": "2024-06-30T23:59:59Z",
                    },
                },
            ]
        }
    }


class PermanentTokenResponse(BaseDocumentedModel):
    """
    Response model for permanent token creation.

    Contains the actual token (only returned once) and metadata.

    **IMPORTANT SECURITY NOTE:** The token value is only returned once during creation.
    Store it securely as it cannot be retrieved again. If lost, you must create a new token.

    **Token Format:** Permanent tokens start with 'sbd_permanent_' followed by a secure random string.
    """

    token: str = Field(
        ...,
        description="The permanent API token. Store this securely - it will not be shown again!",
        example="sbd_permanent_1234567890abcdef1234567890abcdef1234567890abcdef",
    )
    token_id: str = Field(
        ...,
        description="Unique identifier for the token, used for management operations",
        example="pt_1234567890abcdef",
    )
    created_at: datetime = Field(
        ..., description="UTC timestamp when the token was created", example="2024-01-01T12:00:00Z"
    )
    description: Optional[str] = Field(
        None,
        description="Description provided during token creation",
        example="CI/CD Pipeline Token for GitHub Actions",
    )
    expires_at: Optional[datetime] = Field(
        None, description="UTC timestamp when the token expires, or null if it never expires", example=None
    )
    ip_restrictions: Optional[List[str]] = Field(
        None,
        description="List of IP addresses or CIDR blocks that can use this token",
        example=["192.168.1.0/24", "10.0.0.0/8"],
    )
    last_used_at: Optional[datetime] = Field(
        None, description="UTC timestamp when the token was last used (null for new tokens)", example=None
    )
    usage_count: int = Field(
        default=0, description="Number of times the token has been used for authentication", example=0
    )
    is_revoked: bool = Field(default=False, description="Whether the token has been revoked", example=False)

    model_config = {
        "json_schema_extra": {
            "example": {
                "token": "sbd_permanent_1234567890abcdef1234567890abcdef1234567890abcdef",
                "token_id": "pt_1234567890abcdef",
                "created_at": "2024-01-01T12:00:00Z",
                "description": "CI/CD Pipeline Token for GitHub Actions",
                "expires_at": None,
                "ip_restrictions": ["192.30.252.0/22"],
                "last_used_at": None,
                "usage_count": 0,
                "is_revoked": False,
            }
        }
    }


class PermanentTokenInfo(BaseDocumentedModel):
    """
    Model for permanent token metadata (without the actual token).

    Used for listing tokens and displaying token information.
    This model provides safe token information without exposing the actual token value.

    **Security:** The actual token value is never included in this model for security reasons.
    """

    token_id: str = Field(
        ...,
        description="Unique identifier for the token, used for management operations like revocation",
        example="pt_1234567890abcdef",
    )
    description: Optional[str] = Field(
        None,
        description="User-provided description to identify the token's purpose",
        example="CI/CD Pipeline Token for GitHub Actions",
    )
    created_at: datetime = Field(
        ..., description="UTC timestamp when the token was created", example="2024-01-01T12:00:00Z"
    )
    last_used_at: Optional[datetime] = Field(
        None,
        description="UTC timestamp when the token was last used for authentication, or null if never used",
        example="2024-01-01T15:30:00Z",
    )
    usage_count: int = Field(
        default=0, description="Total number of times this token has been used for authentication", example=42
    )
    expires_at: Optional[datetime] = Field(
        None, description="UTC timestamp when the token expires, or null if it never expires", example=None
    )
    ip_restrictions: Optional[List[str]] = Field(
        None,
        description="List of IP addresses or CIDR blocks that can use this token",
        example=["192.168.1.0/24", "10.0.0.0/8"],
    )
    is_revoked: bool = Field(
        default=False, description="Whether the token has been revoked and can no longer be used", example=False
    )
    revoked_at: Optional[datetime] = Field(
        None, description="UTC timestamp when the token was revoked, or null if still active", example=None
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Active Token",
                    "summary": "An active permanent token with usage history",
                    "value": {
                        "token_id": "pt_1234567890abcdef",
                        "description": "CI/CD Pipeline Token for GitHub Actions",
                        "created_at": "2024-01-01T12:00:00Z",
                        "last_used_at": "2024-01-01T15:30:00Z",
                        "usage_count": 42,
                        "expires_at": None,
                        "ip_restrictions": ["192.30.252.0/22"],
                        "is_revoked": False,
                        "revoked_at": None,
                    },
                },
                {
                    "name": "Revoked Token",
                    "summary": "A revoked permanent token",
                    "value": {
                        "token_id": "pt_abcdef1234567890",
                        "description": "Old Development Token",
                        "created_at": "2023-12-01T10:00:00Z",
                        "last_used_at": "2023-12-15T14:20:00Z",
                        "usage_count": 15,
                        "expires_at": None,
                        "ip_restrictions": ["127.0.0.1/32"],
                        "is_revoked": True,
                        "revoked_at": "2023-12-20T09:00:00Z",
                    },
                },
            ]
        }
    }


class PermanentTokenListResponse(BaseDocumentedModel):
    """
    Response model for listing permanent tokens.

    Contains array of token metadata without actual token values.
    Provides comprehensive overview of all tokens for a user including usage statistics.

    **Security:** Token values are never included in list responses for security reasons.
    """

    tokens: List[PermanentTokenInfo] = Field(
        default_factory=list,
        description="List of permanent tokens for the user, including both active and revoked tokens",
    )
    total_count: int = Field(default=0, description="Total number of tokens (active + revoked)", example=5)
    active_count: int = Field(default=0, description="Number of active (non-revoked) tokens", example=3)
    revoked_count: int = Field(default=0, description="Number of revoked tokens", example=2)

    model_config = {
        "json_schema_extra": {
            "example": {
                "tokens": [
                    {
                        "token_id": "pt_1234567890abcdef",
                        "description": "CI/CD Pipeline Token for GitHub Actions",
                        "created_at": "2024-01-01T12:00:00Z",
                        "last_used_at": "2024-01-01T15:30:00Z",
                        "usage_count": 42,
                        "expires_at": None,
                        "ip_restrictions": ["192.30.252.0/22"],
                        "is_revoked": False,
                        "revoked_at": None,
                    },
                    {
                        "token_id": "pt_abcdef1234567890",
                        "description": "Mobile App Integration",
                        "created_at": "2024-01-02T09:00:00Z",
                        "last_used_at": "2024-01-02T10:15:00Z",
                        "usage_count": 15,
                        "expires_at": "2024-12-31T23:59:59Z",
                        "ip_restrictions": [],
                        "is_revoked": False,
                        "revoked_at": None,
                    },
                ],
                "total_count": 2,
                "active_count": 2,
                "revoked_count": 0,
            }
        }
    }


class PermanentTokenCacheData(BaseModel):
    """
    Model for data stored in Redis cache.

    Contains user metadata for fast token validation.
    """

    user_id: str = Field(..., description="String representation of user ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="User email")
    role: str = Field(default="user", description="User role")
    is_verified: bool = Field(default=False, description="Email verification status")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")


class TokenRevocationResponse(BaseDocumentedModel):
    """
    Response model for token revocation.

    Confirms successful token revocation and provides revocation details.
    Once a token is revoked, it cannot be used for authentication and cannot be restored.

    **Security:** Revoked tokens are immediately invalidated and removed from cache.
    """

    message: str = Field(
        ..., description="Confirmation message indicating successful revocation", example="Token revoked successfully"
    )
    token_id: str = Field(..., description="Unique identifier of the revoked token", example="pt_1234567890abcdef")
    revoked_at: datetime = Field(
        ..., description="UTC timestamp when the token was revoked", example="2024-01-01T16:00:00Z"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Token revoked successfully",
                "token_id": "pt_1234567890abcdef",
                "revoked_at": "2024-01-01T16:00:00Z",
            }
        }
    }


class PermanentTokenDocument(BaseModel):
    """
    Database document model for permanent tokens collection.

    Represents the complete document structure stored in MongoDB.
    """

    user_id: str = Field(..., description="ObjectId of the token owner")
    token_id: str = Field(..., description="Unique token identifier for management operations")
    token_hash: str = Field(..., description="SHA-256 hash of the token")
    description: Optional[str] = Field(None, max_length=255, description="Optional token description")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Token creation timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")
    is_revoked: bool = Field(default=False, description="Revocation status")
    revoked_at: Optional[datetime] = Field(None, description="Revocation timestamp")


# WebAuthn support removed


class AuthMethodsResponse(BaseDocumentedModel):
    """
    Response model for authentication methods query.

    Contains information about available authentication methods,
    user preferences, and recent authentication activity.

    **Fields:**
    - available_methods: List of authentication methods available to the user
    - preferred_method: User's preferred authentication method
    - has_password: Whether the user has a password set
    - recent_auth_methods: List of recently used authentication methods
    - last_auth_method: The most recently used authentication method
    """

    available_methods: List[str] = Field(
        default_factory=list,
        description="List of authentication methods available to the user",
        example=["password"],
    )
    preferred_method: Optional[str] = Field(
        None,
        description="User's preferred authentication method",
        example="password",
    )
    has_password: bool = Field(
        default=True,
        description="Whether the user has a password set",
        example=True,
    )
    recent_auth_methods: List[str] = Field(
        default_factory=list,
        description="List of recently used authentication methods",
        example=["password", "password"],
    )
    last_auth_method: Optional[str] = Field(
        None,
        description="The most recently used authentication method",
        example="password",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "available_methods": ["password"],
                "preferred_method": "password",
                "has_password": True,
                "recent_auth_methods": ["password", "password"],
                "last_auth_method": "password",
            }
        }
    }


class AuthPreferenceResponse(BaseDocumentedModel):
    """
    Response model for authentication preference updates.

    Confirms successful update of user's preferred authentication method.

    **Fields:**
    - message: Confirmation message
    - preferred_method: The newly set preferred authentication method
    """

    message: str = Field(
        ...,
        description="Confirmation message indicating successful preference update",
        example="Authentication preference updated successfully",
    )
    preferred_method: str = Field(
        ...,
        description="The newly set preferred authentication method",
        example="password",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Authentication preference updated successfully",
                "preferred_method": "password",
            }
        }
    }


class AuthFallbackResponse(BaseDocumentedModel):
    """
    Response model for authentication fallback options.

    Provides information about alternative authentication methods
    available when a primary method fails.

    **Fields:**
    - fallback_available: Whether fallback options are available
    - available_fallbacks: List of available fallback authentication methods
    - recommended_fallback: Recommended fallback method to try
    """

    fallback_available: bool = Field(
        default=False,
        description="Whether fallback authentication options are available",
        example=True,
    )
    available_fallbacks: List[str] = Field(
        default_factory=list,
        description="List of available fallback authentication methods",
        example=["password"],
    )
    recommended_fallback: Optional[str] = Field(
        None,
        description="Recommended fallback authentication method",
        example="password",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "fallback_available": True,
                "available_fallbacks": ["password"],
                "recommended_fallback": "password",
            }
        }
    }



