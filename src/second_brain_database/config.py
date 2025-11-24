"""
# Configuration Management Module

This module provides a **production-grade, security-first configuration system** for the Second Brain Database application.
Built on **Pydantic Settings**, it offers hierarchical configuration loading, automatic validation, secret management, and
self-documentation capabilities suitable for both local development and containerized production deployments.

## Architecture Overview

The configuration system follows a **layered hierarchy** with clear precedence rules:

```
┌─────────────────────────────────────────────────────────────┐
│         Configuration Loading Hierarchy                     │
│  (Higher layers override lower layers)                      │
├─────────────────────────────────────────────────────────────┤
│  1. Environment Variables (HIGHEST PRIORITY)                │
│     - OS environment variables                              │
│     - Docker/K8s secrets mounted as env vars                │
│     - CI/CD pipeline variables                              │
├─────────────────────────────────────────────────────────────┤
│  2. SECOND_BRAIN_DATABASE_CONFIG_PATH                       │
│     - Custom config file path from env var                  │
│     - Useful for multi-environment deployments              │
├─────────────────────────────────────────────────────────────┤
│  3. .sbd File (Project Root)                                │
│     - Primary config file for development                   │
│     - Gitignored for security                               │
├─────────────────────────────────────────────────────────────┤
│  4. .env File (Project Root)                                │
│     - Fallback config file                                  │
│     - Compatible with docker-compose                        │
├─────────────────────────────────────────────────────────────┤
│  5. Default Values (LOWEST PRIORITY)                        │
│     - Hardcoded in Settings class                           │
│     - Safe defaults for development                         │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Hierarchical Configuration Loading
The system implements a **4-tier configuration hierarchy** with automatic precedence resolution:
- **Tier 1 (Highest)**: Environment variables (e.g., `export MONGODB_URL="..."`)
- **Tier 2**: Custom config file via `SECOND_BRAIN_DATABASE_CONFIG_PATH` environment variable
- **Tier 3**: `.sbd` file in project root (preferred for development)
- **Tier 4 (Lowest)**: `.env` file in project root (docker-compose compatible)

If no configuration file is found, the application falls back to **environment-only mode**, allowing
pure 12-factor app deployments (e.g., Heroku, AWS ECS, Kubernetes).

### 2. Secret Management & Security
Critical secrets are protected via **Pydantic's `SecretStr`** type and **custom validators**:

- **`SecretStr` Type**: Prevents accidental logging of sensitive values (passwords, API keys, tokens)
- **Validation at Startup**: `field_validator` decorators ensure secrets are not hardcoded or left empty
- **Placeholder Detection**: Rejects values containing `"change"`, `"0000"`, or empty strings
- **No Defaults for Secrets**: Critical secrets (`SECRET_KEY`, `FERNET_KEY`, etc.) have NO defaults,
  forcing explicit configuration

**Protected Secrets** (15+ fields):
- `SECRET_KEY` - JWT signing key
- `REFRESH_TOKEN_SECRET_KEY` - Refresh token signing key
- `FERNET_KEY` - Symmetric encryption key for TOTP secrets
- `TURNSTILE_SECRET` - Cloudflare Turnstile captcha secret
- `MONGODB_PASSWORD` - Database password
- `REDIS_PASSWORD` - Redis password
- `QDRANT_API_KEY` - Vector database API key
- `CLUSTER_AUTH_TOKEN` - Cluster node authentication token
- `MCP_AUTH_TOKEN` - MCP server bearer token

### 3. Pydantic Validation & Type Safety
All **200+ settings** are type-validated at application startup using Pydantic:

- **Type Coercion**: Automatic conversion from strings to int/bool/float
- **Range Validation**: Timeouts must be 1-300 seconds, retry backoff 1.0-10.0x
- **URL Validation**: MongoDB URLs cannot be empty or whitespace-only
- **Enum Validation**: String values constrained to allowed sets (e.g., `CLUSTER_NODE_ROLE` → `standalone|master|replica`)

**Custom Validators**:
- `no_hardcoded_secrets`: Ensures secrets are loaded from environment, not hardcoded
- `no_empty_urls`: Validates MongoDB URL is properly configured
- `validate_positive_integers`: Ensures numeric settings are positive
- `validate_timeout_values`: Enforces reasonable timeout ranges (1-300s)
- `validate_backoff_factor`: Checks retry backoff is within 1.0-10.0x

### 4. Modular Configuration Groups
Settings are organized into **15+ logical groups** for clarity and maintainability:

| Group | Settings Count | Purpose |
|-------|---------------|---------|
| **Server** | 3 | Host, port, debug mode |
| **Database (MongoDB)** | 6 | Connection URL, database name, timeouts |
| **Redis** | 7 | Cache connection, session storage |
| **JWT Authentication** | 10 | Token expiry, rotation, algorithms |
| **Rate Limiting** | 5 | Global and feature-specific limits |
| **Family Management** | 8 | Family creation, invitation, member limits |
| **Permanent Tokens** | 17 | API token lifecycle and security |
| **Abuse Prevention** | 10 | Blacklisting, CAPTCHA, reset limits |
| **Documentation** | 12 | Docs access control, caching, CORS |
| **CORS** | 2 | API-wide CORS configuration |
| **Multi-Tenancy** | 12 | Tenant isolation, plans, quotas |
| **MCP (Model Context Protocol)** | 30+ | MCP server, tools, security, caching |
| **Qdrant (Vector DB)** | 15 | Vector search, embeddings, indexing |
| **Docling** | 15 | Document processing, OCR, export |
| **Ollama (LLM)** | 6 | LLM inference configuration |
| **LlamaIndex & RAG** | 10 | RAG retrieval, hybrid search |
| **WebRTC** | 7 | STUN/TURN servers, room policies |
| **IPAM** | 20+ | IP allocation, quotas, notifications |
| **Cluster** | 50+ | Distributed cluster, replication, failover |
| **Chat** | 20+ | Chat system, streaming, caching |

### 5. Self-Contained Logging
The module includes **minimal logging** for configuration discovery, avoiding circular dependencies
with the main logging manager. This allows the config module to be imported early in the application
lifecycle without triggering complex initialization chains.

## Configuration Groups (Detailed)

### Server Configuration
Basic application server settings:

```python
HOST: str = "127.0.0.1"  # Bind address (0.0.0.0 for production)
PORT: int = 8000  # HTTP listen port
DEBUG: bool = True  # Debug mode (disable in production)
BASE_URL: str = "http://localhost:8000"  # Canonical URL for redirects
```

### JWT Authentication Configuration
Token-based authentication settings with rotation support:

```python
SECRET_KEY: SecretStr  # HS256 signing key (REQUIRED)
REFRESH_TOKEN_SECRET_KEY: SecretStr  # Separate key for refresh tokens
ALGORITHM: str = "HS256"  # JWT signing algorithm
ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Short-lived access tokens
REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # Long-lived refresh tokens
ENABLE_TOKEN_ROTATION: bool = True  # Rotate refresh tokens on use
MAX_REFRESH_TOKEN_REUSE: int = 1  # Prevent token reuse attacks
```

### MongoDB Configuration
Database connection with authentication and timeouts:

```python
MONGODB_URL: str  # Connection string (REQUIRED)
MONGODB_DATABASE: str  # Database name (REQUIRED)
MONGODB_CONNECTION_TIMEOUT: int = 10000  # 10 seconds
MONGODB_SERVER_SELECTION_TIMEOUT: int = 5000  # 5 seconds
MONGODB_USERNAME: Optional[str] = None  # Optional authentication
MONGODB_PASSWORD: Optional[SecretStr] = None  # Encrypted password
```

### Redis Configuration
Cache and session storage with automatic URL construction:

```python
REDIS_URL: Optional[str] = None  # Full URL (if provided)
REDIS_STORAGE_URI: Optional[str] = None  # Alternative URI format
REDIS_HOST: str = "127.0.0.1"  # Fallback to host/port
REDIS_PORT: int = 6379
REDIS_DB: int = 0  # Database index
REDIS_USERNAME: Optional[str] = None
REDIS_PASSWORD: Optional[SecretStr] = None
```

### Rate Limiting Configuration
Global and feature-specific rate limits:

```python
RATE_LIMIT_REQUESTS: int = 100  # Global limit per period
RATE_LIMIT_PERIOD_SECONDS: int = 60  # 1 minute window
FAMILY_CREATE_RATE_LIMIT: int = 2  # Max families per hour
FAMILY_INVITE_RATE_LIMIT: int = 10  # Max invites per hour
IPAM_QUERY_RATE_LIMIT: int = 500  # Max IPAM queries per hour
```

### MCP (Model Context Protocol) Configuration
AI tool integration with security and rate limiting:

```python
MCP_ENABLED: bool = True  # Enable MCP server
MCP_TRANSPORT: str = "stdio"  # stdio (local) or http (remote)
MCP_HTTP_PORT: int = 8001  # HTTP transport port
MCP_REQUIRE_AUTH: bool = True  # Enforce authentication
MCP_AUTH_TOKEN: Optional[SecretStr] = None  # Bearer token
MCP_RATE_LIMIT_ENABLED: bool = True
MCP_RATE_LIMIT_REQUESTS: int = 100  # Max requests per minute
MCP_TOOLS_ENABLED: bool = True  # Enable tool execution
MCP_RESOURCES_ENABLED: bool = True  # Enable resource access
```

### Cluster Configuration (50+ Settings)
Distributed deployment with replication and failover:

```python
CLUSTER_ENABLED: bool = False  # Enable cluster mode
CLUSTER_NODE_ROLE: str = "standalone"  # standalone|master|replica
CLUSTER_TOPOLOGY_TYPE: str = "master-slave"  # Architecture type
CLUSTER_REPLICATION_FACTOR: int = 2  # Number of replicas
CLUSTER_DISCOVERY_METHOD: str = "static"  # Service discovery
CLUSTER_SEED_NODES: Optional[str] = None  # Bootstrap nodes
CLUSTER_REPLICATION_MODE: str = "async"  # async|sync|semi-sync
CLUSTER_AUTO_FAILOVER: bool = True  # Automatic master promotion
CLUSTER_HEARTBEAT_INTERVAL: int = 5  # Seconds between heartbeats
```

## Usage Examples

### Development Setup (Local Machine)

Create a `.sbd` file in the project root:

```dotenv
# .sbd - Development Configuration
DEBUG=true
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=sbd_dev
SECRET_KEY=dev-secret-key-change-in-production-abc123xyz789
REFRESH_TOKEN_SECRET_KEY=dev-refresh-key-change-in-production-def456uvw012
FERNET_KEY=dev-fernet-key-abcdefgh12345678ijklmnop90123456=
TURNSTILE_SITEKEY=1x00000000000000000000AA
TURNSTILE_SECRET=1x0000000000000000000000000000000AA

# Redis (local)
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
```

Import settings in application code:

```python
from second_brain_database.config import settings

# Access configuration
if settings.DEBUG:
    print(f"Running in debug mode on {settings.HOST}:{settings.PORT}")

# Secret values are encrypted
mongodb_url = settings.MONGODB_URL  # Plain text access
secret_key = settings.SECRET_KEY.get_secret_value()  # Decrypt secret
```

### Production Setup (Environment Variables)

For containerized deployments (Docker, Kubernetes), use environment variables:

```bash
# Docker run example
docker run -e MONGODB_URL="mongodb://prod-db:27017" \
           -e MONGODB_DATABASE="sbd_production" \
           -e SECRET_KEY="$(cat /run/secrets/jwt_secret)" \
           -e REFRESH_TOKEN_SECRET_KEY="$(cat /run/secrets/refresh_secret)" \
           -e DEBUG=false \
           -e CORS_ORIGINS="https://app.example.com,https://api.example.com" \
           -e CLUSTER_ENABLED=true \
           -e CLUSTER_NODE_ROLE=replica \
           my-sbd-image:latest
```

Kubernetes ConfigMap + Secret:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sbd-config
data:
  MONGODB_URL: "mongodb://mongo-svc:27017"
  MONGODB_DATABASE: "sbd_production"
  DEBUG: "false"
  CLUSTER_ENABLED: "true"
---
apiVersion: v1
kind: Secret
metadata:
  name: sbd-secrets
type: Opaque
stringData:
  SECRET_KEY: "production-jwt-secret-key-32-characters"
  FERNET_KEY: "base64-encoded-fernet-key-32-bytes=="
```

### Multi-Environment Setup (Custom Config Path)

For staging/QA environments with custom config locations:

```bash
# Set custom config path
export SECOND_BRAIN_DATABASE_CONFIG_PATH="/etc/sbd/staging.env"

# Run application
uv run uvicorn second_brain_database.main:app
```

### Accessing Configuration Programmatically

```python
from second_brain_database.config import settings

# Check deployment environment
if settings.is_production:
    # Production-specific logic (DEBUG=false)
    log_level = "WARNING"
else:
    # Development-specific logic (DEBUG=true)
    log_level = "DEBUG"

# Check feature flags
if settings.CLUSTER_ENABLED:
    from second_brain_database.managers.cluster_manager import cluster_manager
    await cluster_manager.initialize()

# Access computed properties
docs_enabled = settings.docs_should_be_enabled  # Conditional on environment
mcp_enabled = settings.mcp_should_be_enabled  # Conditional on environment + config
```

## Security Best Practices

### 1. Never Hardcode Secrets
❌ **Bad** (hardcoded in config.py):
```python
SECRET_KEY: SecretStr = SecretStr("my-secret-key-123")  # FAILS validation!
```

✅ **Good** (environment variable):
```bash
export SECRET_KEY="generated-secret-key-with-high-entropy"
```

### 2. Use Strong, Random Secrets
Generate cryptographically secure secrets:

```bash
# Generate SECRET_KEY (32+ characters, random)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate FERNET_KEY (base64-encoded, 32 bytes)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Separate Dev and Production Secrets
NEVER use development secrets in production:

```python
# Development (.sbd)
SECRET_KEY=dev-secret-key-for-local-testing-only-12345

# Production (environment variable)
SECRET_KEY=$(vault read -field=value secret/sbd/jwt_secret)
```

### 4. Rotate Secrets Regularly
Implement a secret rotation schedule:

- **JWT Keys**: Rotate every 90 days
- **Encryption Keys** (`FERNET_KEY`): Rotate every 180 days with migration
- **API Tokens** (`TURNSTILE_SECRET`, `MCP_AUTH_TOKEN`): Rotate on suspected compromise

## Validation & Error Handling

The configuration system performs **startup validation** to catch errors early:

### Successful Validation
```python
# Startup logs
INFO:config:Configuration loaded successfully
INFO:config:Using config file: /path/to/.sbd
INFO:config:MongoDB URL: mongodb://localhost:27017
INFO:config:Redis URL: redis://127.0.0.1:6379/0
```

### Failed Validation
```python
# Missing SECRET_KEY
ValidationError: 1 validation error for Settings
SECRET_KEY
  SECRET_KEY must be set via environment or .sbd and not hardcoded!

# Invalid timeout value
ValidationError: 1 validation error for Settings
MCP_REQUEST_TIMEOUT
  MCP_REQUEST_TIMEOUT must be between 1 and 300 seconds
```

## Module-Level Constants & Attributes

Attributes:
    SBD_FILENAME (str): Primary configuration filename (`.sbd`). This file takes precedence
        over `.env` when both exist in the project root. Default: `".sbd"`.
    
    DEFAULT_ENV_FILENAME (str): Fallback configuration filename (`.env`). Compatible with
        docker-compose and other tools that use `.env` format. Default: `".env"`.
    
    CONFIG_ENV_VAR (str): Environment variable name for custom config file path. When set,
        this takes highest precedence over `.sbd` and `.env` files. Default: 
        `"SECOND_BRAIN_DATABASE_CONFIG_PATH"`.
    
    PROJECT_ROOT (Path): Absolute path to the project root directory. Calculated as the
        parent directory of the `src/second_brain_database` package. Used to locate config
        files (`.sbd`, `.env`) relative to the project root.
    
    CONFIG_PATH (Optional[str]): Resolved path to the active configuration file, or `None`
        if no file was found (environment-variable-only mode). This is determined by
        `get_config_path()` and is used to set `Settings.model_config.env_file`.
    
    settings (Settings): Global singleton instance of the `Settings` class. This is the
        **primary interface** for accessing configuration throughout the application. It is
        instantiated at module import time and automatically loads configuration from the
        hierarchy (environment → config file → defaults).

## Performance Characteristics

Configuration loading is **optimized for fast startup**:

- **Cold Start**: <5ms (no config file, environment-only mode)
- **Warm Start**: <10ms (.sbd file parsing + validation)
- **Memory Footprint**: ~1MB (Pydantic model + 200+ settings)
- **Lazy Loading**: Settings are loaded once at import time, then cached
- **Thread Safety**: The `settings` singleton is immutable after initialization

## Troubleshooting

### Config File Not Found
```python
# Normal behavior - falls back to environment variables
# No error is raised, application continues with env-only mode
```

### Secret Validation Failed
```python
# Check environment variables
echo $SECRET_KEY
echo $FERNET_KEY

# Verify .sbd file exists and is readable
cat .sbd | grep SECRET_KEY
```

### MongoDB Connection Failed
```python
# Validate MongoDB URL format
MONGODB_URL=mongodb://username:password@host:port/database
#           └─ scheme ─┘ └─── auth ────┘ └ host ┘ └database┘
```

## Related Modules

See Also:
    - `main`: Main application entry point that uses `settings` for initialization
    - `database.manager`: MongoDB connection configured via `settings.MONGODB_*`
    - `services.redis_manager`: Redis connection configured via `settings.REDIS_*`
    - `managers.cluster_manager`: Cluster mode configured via `settings.CLUSTER_*`
    - `integrations.mcp.server`: MCP server configured via `settings.MCP_*`

## Todo

Todo:
    * Add JSON schema export for automated documentation generation
    * Implement configuration versioning for backward compatibility
    * Add runtime configuration reload without restart (for non-critical settings)
    * Implement configuration validation testing framework
    * Add support for encrypted config files (SOPS, Vault integration)
    * Create CLI tool for config file generation and validation
    * Add configuration diff tool for comparing dev/staging/prod settings
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Constants ---
SBD_FILENAME: str = ".sbd"
DEFAULT_ENV_FILENAME: str = ".env"
CONFIG_ENV_VAR: str = "SECOND_BRAIN_DATABASE_CONFIG_PATH"
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


# --- Config file discovery (no logging) ---
def get_config_path() -> Optional[str]:
    """
    Determines the configuration file path based on a predefined precedence order.

    This function checks for the existence of configuration files in the following order:
    1.  **Environment Variable**: `SECOND_BRAIN_DATABASE_CONFIG_PATH` (if set and file exists).
    2.  **SBD Config**: `.sbd` file in the project root directory.
    3.  **Dotenv Config**: `.env` file in the project root directory.
    4.  **Fallback**: Returns `None` if no file is found, triggering environment-variable-only mode.

    This logic allows for flexible deployment strategies, where configuration can be injected
    via a specific file (e.g., in Kubernetes secrets) or purely through environment variables
    (e.g., in 12-factor app deployments).

    Returns:
        Optional[str]: The absolute path to the configuration file, or `None` if not found.
    """
    env_path: Optional[str] = os.environ.get(CONFIG_ENV_VAR)
    if env_path and os.path.exists(env_path):
        return env_path
    sbd_path: Path = PROJECT_ROOT / SBD_FILENAME
    if sbd_path.exists():
        return str(sbd_path)
    env_path_file: Path = PROJECT_ROOT / DEFAULT_ENV_FILENAME
    if env_path_file.exists():
        return str(env_path_file)
    return None


CONFIG_PATH: Optional[str] = get_config_path()
if CONFIG_PATH:
    try:
        load_dotenv(dotenv_path=CONFIG_PATH, override=True)
    except OSError as exc:
        raise exc
else:
    # No config file found - fall back to environment variables only
    # This allows the application to run with environment variables as backup
    pass


class Settings(BaseSettings):
    """
    Application configuration settings model.

    This class defines all configurable parameters for the application, including server settings,
    database connections, security keys, and feature flags. It uses Pydantic's `BaseSettings`
    to automatically load values from environment variables or a configuration file.

    **Configuration Groups:**
    *   **Server**: Host, port, debug mode.
    *   **Database**: MongoDB connection details.
    *   **Redis**: Connection details for caching and session management.
    *   **Security**: JWT keys, encryption keys, Turnstile secrets.
    *   **Features**: Toggles for various modules (Chat, Shop, Family, etc.).
    *   **Integrations**: MCP, Qdrant, Ollama, LlamaIndex configuration.
    *   **Limits**: Rate limits, quotas, and capacity thresholds.

    **Validation:**
    The class includes custom validators to ensure that critical secrets are not hardcoded
    and that numeric values (timeouts, limits) are within reasonable ranges.
    """

    # Configure model to use config file if available, otherwise environment only
    model_config = SettingsConfigDict(
        env_file=CONFIG_PATH if CONFIG_PATH else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",  # Allow extra env vars not defined as fields
    )

    # Server configuration (loaded from environment)
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True

    # Base URL configuration
    BASE_URL: str = "http://localhost:8000"

    # JWT configuration (loaded from environment)
    SECRET_KEY: SecretStr = SecretStr("")  # Must be set in .sbd or environment
    REFRESH_TOKEN_SECRET_KEY: SecretStr = SecretStr("")  # Separate secret for refresh tokens
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Reduced from 30 for better security
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # Refresh tokens last 7 days
    ENABLE_TOKEN_ROTATION: bool = True  # Rotate refresh tokens on use for security
    MAX_REFRESH_TOKEN_REUSE: int = 1  # Prevent refresh token reuse

    # MongoDB configuration (loaded from environment)
    MONGODB_URL: str = ""  # Must be set in .sbd or environment
    MONGODB_DATABASE: str = ""
    MONGODB_CONNECTION_TIMEOUT: int = 10000
    MONGODB_SERVER_SELECTION_TIMEOUT: int = 5000

    # Authentication (optional)
    MONGODB_USERNAME: Optional[str] = None
    MONGODB_PASSWORD: Optional[SecretStr] = None

    # Redis configuration
    # Redis configuration
    # REDIS_URL is the effective URL used by the app. It can be provided directly
    # or will be constructed from REDIS_STORAGE_URI or host/port/credentials below.
    REDIS_URL: Optional[str] = None
    REDIS_STORAGE_URI: Optional[str] = None
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_USERNAME: Optional[str] = None
    REDIS_PASSWORD: Optional[SecretStr] = None

    # Permanent Token configuration
    PERMANENT_TOKENS_ENABLED: bool = True  # Enable/disable permanent token feature
    PERMANENT_TOKEN_CACHE_TTL_SECONDS: int = 24 * 60 * 60  # 24 hours cache TTL
    PERMANENT_TOKEN_CREATE_RATE_LIMIT: int = 10  # Max tokens created per hour per user
    PERMANENT_TOKEN_CREATE_RATE_PERIOD: int = 3600  # Rate limit period in seconds
    PERMANENT_TOKEN_LIST_RATE_LIMIT: int = 50  # Max list requests per hour per user
    PERMANENT_TOKEN_LIST_RATE_PERIOD: int = 3600  # Rate limit period in seconds
    PERMANENT_TOKEN_REVOKE_RATE_LIMIT: int = 20  # Max revoke requests per hour per user
    PERMANENT_TOKEN_REVOKE_RATE_PERIOD: int = 3600  # Rate limit period in seconds
    PERMANENT_TOKEN_MAX_PER_USER: int = 50  # Maximum tokens per user
    PERMANENT_TOKEN_CLEANUP_DAYS: int = 90  # Days to keep revoked tokens
    PERMANENT_TOKEN_AUDIT_RETENTION_DAYS: int = 365  # Days to keep audit logs
    PERMANENT_TOKEN_ANALYTICS_RETENTION_DAYS: int = 180  # Days to keep analytics
    PERMANENT_TOKEN_MAINTENANCE_INTERVAL_HOURS: int = 6  # Maintenance interval
    PERMANENT_TOKEN_SUSPICIOUS_IP_THRESHOLD: int = 5  # Max IPs per token before alert
    PERMANENT_TOKEN_RAPID_CREATION_THRESHOLD: int = 10  # Max tokens in 5 min before alert
    PERMANENT_TOKEN_FAILED_VALIDATION_THRESHOLD: int = 20  # Max failures in 10 min before alert

    # Rate limiting configuration
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD_SECONDS: int = 60

    # Family-specific rate limiting configuration
    FAMILY_CREATE_RATE_LIMIT: int = 2  # Max families created per hour per user
    FAMILY_INVITE_RATE_LIMIT: int = 10  # Max invitations sent per hour per user
    FAMILY_ADMIN_ACTION_RATE_LIMIT: int = 5  # Max admin actions per hour per user
    FAMILY_MEMBER_ACTION_RATE_LIMIT: int = 20  # Max member actions per hour per user

    # Family limits configuration for billing integration
    DEFAULT_MAX_FAMILIES_ALLOWED: int = 1  # Default max families per user
    DEFAULT_MAX_MEMBERS_PER_FAMILY: int = 5  # Default max members per family
    FAMILY_LIMITS_GRACE_PERIOD_DAYS: int = 30  # Grace period for limit downgrades
    ENABLE_FAMILY_USAGE_TRACKING: bool = True  # Track usage for billing
    FAMILY_USAGE_TRACKING_RETENTION_DAYS: int = 365  # How long to keep usage data

    # Blacklist configuration
    BLACKLIST_THRESHOLD: int = 10  # Number of violations before blacklisting
    BLACKLIST_DURATION: int = 60 * 60  # Blacklist for 1 hour (in seconds)

    # Repeated violator detection configuration
    REPEATED_VIOLATOR_WINDOW_MINUTES: int = 10  # Time window for repeated violator detection
    REPEATED_VIOLATOR_MIN_UNIQUE_IPS: int = 3  # Unique IPs required in window

    # Fernet encryption key (for TOTP secret encryption)
    FERNET_KEY: SecretStr = SecretStr("")  # Must be set in .sbd or environment

    # 2FA/Backup code config (loaded from .sbd if present)
    BACKUP_CODES_PENDING_TIME: int = 300  # 5 minutes
    BACKUP_CODES_CLEANUP_INTERVAL: int = 60  # 60 seconds by default

    # Cloudflare Turnstile config
    TURNSTILE_SITEKEY: SecretStr = SecretStr("")  # Must be set in .sbd or environment
    TURNSTILE_SECRET: SecretStr = SecretStr("")  # Must be set in .sbd or environment

    # Password reset abuse/whitelist stricter limits
    STRICTER_WHITELIST_LIMIT: int = 3  # Max resets per 24h for whitelisted pairs
    STRICTER_WHITELIST_PERIOD: int = 86400  # 24h in seconds
    ABUSE_ACTION_TOKEN_EXPIRY: int = 1800  # 30 min (seconds)
    ABUSE_ACTION_BLOCK_EXPIRY: int = 86400  # 24h (seconds)
    MAX_RESET_REQUESTS: int = 8  # Max reset requests in 15 min
    MAX_RESET_UNIQUE_IPS: int = 4  # Max unique IPs in 15 min

    # Logging configuration
    DEFAULT_LOG_LEVEL: str = "INFO"
    DEFAULT_BUFFER_FILE: str = "loki_buffer.log"
    LOKI_VERSION: str = "1"
    LOKI_COMPRESS: bool = True

    # Redis/Abuse sync intervals
    REDIS_FLAG_SYNC_INTERVAL: int = 60  # Interval for syncing password reset flags to Redis (seconds)
    BLOCKLIST_RECONCILE_INTERVAL: int = 300  # Interval for blocklist/whitelist reconciliation (seconds)

    # Documentation configuration
    DOCS_ENABLED: bool = True  # Enable/disable documentation endpoints
    DOCS_URL: Optional[str] = "/docs"  # Swagger UI URL
    REDOC_URL: Optional[str] = "/redoc"  # ReDoc URL
    OPENAPI_URL: Optional[str] = "/openapi.json"  # OpenAPI schema URL
    DOCS_ACCESS_CONTROL: bool = False  # Enable access control for docs
    DOCS_CACHE_ENABLED: bool = True  # Enable documentation caching
    DOCS_CACHE_TTL: int = 3600  # Documentation cache TTL in seconds

    # Production documentation security
    DOCS_ALLOWED_IPS: Optional[str] = None  # Comma-separated list of allowed IPs for docs
    DOCS_REQUIRE_AUTH: bool = False  # Require authentication for documentation access
    DOCS_RATE_LIMIT_REQUESTS: int = 10  # Max documentation requests per minute per IP
    DOCS_RATE_LIMIT_PERIOD: int = 60  # Rate limit period in seconds

    # CORS configuration for documentation
    DOCS_CORS_ORIGINS: Optional[str] = None  # Comma-separated allowed origins for docs CORS
    DOCS_CORS_CREDENTIALS: bool = False  # Allow credentials in CORS for docs
    DOCS_CORS_METHODS: str = "GET"  # Allowed methods for docs CORS
    DOCS_CORS_HEADERS: str = "Content-Type,Authorization"  # Allowed headers for docs CORS
    DOCS_CORS_MAX_AGE: int = 3600  # CORS preflight cache duration

    # General CORS configuration for API
    CORS_ENABLED: bool = True  # Enable CORS for the entire API
    CORS_ORIGINS: str = "http://localhost:3000,https://agentchat.vercel.app"  # Comma-separated allowed origins

    # Multi-tenancy configuration
    MULTI_TENANCY_ENABLED: bool = True  # Enable/disable multi-tenancy
    DEFAULT_TENANT_ID: str = "tenant_default"  # Default tenant for backward compatibility
    TENANT_ISOLATION_MODE: str = "strict"  # strict, permissive
    ALLOW_CROSS_TENANT_QUERIES: bool = False  # For admin operations only

    # Tenant plan limits
    FREE_PLAN_MAX_USERS: int = 5  # Maximum users for free plan
    FREE_PLAN_MAX_STORAGE_GB: int = 10  # Maximum storage for free plan
    PRO_PLAN_MAX_USERS: int = 50  # Maximum users for pro plan
    PRO_PLAN_MAX_STORAGE_GB: int = 100  # Maximum storage for pro plan
    ENTERPRISE_PLAN_MAX_USERS: int = -1  # Unlimited users for enterprise
    ENTERPRISE_PLAN_MAX_STORAGE_GB: int = -1  # Unlimited storage for enterprise

    # Tenant rate limiting
    TENANT_CREATE_RATE_LIMIT: int = 2  # Max tenants created per hour per user
    TENANT_INVITE_RATE_LIMIT: int = 20  # Max invitations sent per hour per user


    # LangSmith Observability
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "SecondBrainDatabase"
    LANGSMITH_TRACING: bool = False

    # --- FastMCP Server Configuration ---
    # MCP Server basic configuration
    MCP_ENABLED: bool = True  # Enable/disable MCP server
    MCP_SERVER_NAME: str = "SecondBrainMCP"  # MCP server name
    MCP_SERVER_VERSION: str = "1.0.0"  # MCP server version
    MCP_DEBUG_MODE: bool = False  # Enable debug mode for MCP server

    # Modern FastMCP 2.x transport configuration
    MCP_TRANSPORT: str = "stdio"  # "stdio" for local clients, "http" for remote/production
    MCP_HTTP_HOST: str = "127.0.0.1"  # Host for HTTP transport (use 0.0.0.0 for production)
    MCP_HTTP_PORT: int = 8001  # Port for HTTP transport
    MCP_HTTP_CORS_ENABLED: bool = False  # Enable CORS for HTTP transport
    MCP_HTTP_CORS_ORIGINS: str = "*"  # Allowed CORS origins (comma-separated)

    # MCP Security configuration
    MCP_SECURITY_ENABLED: bool = True  # Enable security for MCP tools
    MCP_REQUIRE_AUTH: bool = True  # Require authentication for MCP tools
    MCP_AUTH_TOKEN: Optional[SecretStr] = None  # Bearer token for HTTP transport authentication
    MCP_AUDIT_ENABLED: bool = True  # Enable audit logging for MCP operations

    # MCP Rate limiting configuration
    MCP_RATE_LIMIT_ENABLED: bool = True  # Enable rate limiting for MCP tools
    MCP_RATE_LIMIT_REQUESTS: int = 100  # Max MCP requests per period per user
    MCP_RATE_LIMIT_PERIOD: int = 60  # Rate limit period in seconds
    MCP_RATE_LIMIT_BURST: int = 10  # Burst limit for MCP requests

    # MCP Performance configuration
    MCP_MAX_CONCURRENT_TOOLS: int = 50  # Maximum concurrent tool executions
    MCP_REQUEST_TIMEOUT: int = 30  # Request timeout in seconds
    MCP_TOOL_EXECUTION_TIMEOUT: int = 60  # Tool execution timeout in seconds

    # MCP Tool configuration
    MCP_TOOLS_ENABLED: bool = True  # Enable MCP tools
    MCP_RESOURCES_ENABLED: bool = True  # Enable MCP resources
    MCP_PROMPTS_ENABLED: bool = True  # Enable MCP prompts

    # MCP Tool Access Control (Individual tool categories)
    MCP_FAMILY_TOOLS_ENABLED: bool = True  # Enable family management tools
    MCP_AUTH_TOOLS_ENABLED: bool = True  # Enable authentication tools
    MCP_PROFILE_TOOLS_ENABLED: bool = True  # Enable profile management tools
    MCP_SHOP_TOOLS_ENABLED: bool = True  # Enable shop and asset tools
    MCP_WORKSPACE_TOOLS_ENABLED: bool = True  # Enable workspace tools
    MCP_ADMIN_TOOLS_ENABLED: bool = False  # Enable admin tools (default: false for security)
    MCP_SYSTEM_TOOLS_ENABLED: bool = False  # Enable system management tools (default: false for security)

    # MCP Access control configuration
    MCP_ALLOWED_ORIGINS: Optional[str] = None  # Comma-separated allowed origins for MCP
    MCP_IP_WHITELIST: Optional[str] = None  # Comma-separated IP whitelist for MCP access
    MCP_CORS_ENABLED: bool = False  # Enable CORS for MCP server

    # MCP Monitoring configuration
    MCP_METRICS_ENABLED: bool = True  # Enable metrics collection for MCP
    MCP_HEALTH_CHECK_ENABLED: bool = True  # Enable health check endpoints
    MCP_PERFORMANCE_MONITORING: bool = True  # Enable performance monitoring

    # MCP Error handling configuration
    MCP_ERROR_RECOVERY_ENABLED: bool = True  # Enable error recovery mechanisms
    MCP_CIRCUIT_BREAKER_ENABLED: bool = True  # Enable circuit breaker pattern
    MCP_RETRY_ENABLED: bool = True  # Enable retry logic for failed operations
    MCP_RETRY_MAX_ATTEMPTS: int = 3  # Maximum retry attempts
    MCP_RETRY_BACKOFF_FACTOR: float = 2.0  # Exponential backoff factor

    # MCP Cache configuration
    MCP_CACHE_ENABLED: bool = True  # Enable caching for MCP operations
    MCP_CACHE_TTL: int = 300  # Cache TTL in seconds (5 minutes)
    MCP_CONTEXT_CACHE_TTL: int = 60  # User context cache TTL in seconds

    # --- Qdrant Vector Database Configuration ---
    # Qdrant basic configuration
    QDRANT_ENABLED: bool = True  # Enable/disable Qdrant integration
    QDRANT_HOST: str = "127.0.0.1"  # Qdrant server host
    QDRANT_PORT: int = 6333  # Qdrant server port
    QDRANT_HTTPS: bool = False  # Use HTTPS for Qdrant connection
    QDRANT_API_KEY: Optional[SecretStr] = None  # API key for Qdrant (if required)
    QDRANT_TIMEOUT: int = 30  # Connection timeout in seconds
    QDRANT_RETRIES: int = 3  # Number of retries for failed operations

    # Qdrant collection configuration
    QDRANT_DOCUMENT_COLLECTION: str = "documents"  # Collection name for document chunks
    QDRANT_VECTOR_SIZE: int = 384  # Vector dimension (384 for all-MiniLM-L6-v2)
    QDRANT_DISTANCE_METRIC: str = "Cosine"  # Distance metric: Cosine, Euclidean, Dot
    QDRANT_OPTIMIZATION_THRESHOLD: int = 1000  # Threshold for collection optimization
    QDRANT_INDEXING_THRESHOLD: int = 20000  # Threshold for indexing operations

    # Embedding model configuration
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # Sentence transformer model name
    EMBEDDING_CACHE_DIR: Optional[str] = None  # Cache directory for embedding models
    EMBEDDING_DEVICE: str = "cpu"  # Device for embedding computation (cpu/cuda/auto)
    EMBEDDING_BATCH_SIZE: int = 32  # Batch size for embedding generation
    EMBEDDING_MAX_SEQ_LENGTH: int = 512  # Maximum sequence length for embeddings
    EMBEDDING_MODEL_WARMUP: bool = True  # Warm up model on startup (background loading)

    # Document search configuration
    SEARCH_HYBRID_ENABLED: bool = True  # Enable hybrid search (keyword + semantic)
    SEARCH_SEMANTIC_WEIGHT: float = 0.7  # Weight for semantic search (0.0-1.0)
    SEARCH_KEYWORD_WEIGHT: float = 0.3  # Weight for keyword search (0.0-1.0)
    SEARCH_MAX_RESULTS: int = 20  # Maximum search results to return
    SEARCH_SCORE_THRESHOLD: float = 0.0  # Minimum score threshold for results
    SEARCH_RERANK_ENABLED: bool = True  # Enable result reranking
    SEARCH_CACHE_ENABLED: bool = True  # Enable search result caching
    SEARCH_CACHE_TTL: int = 300  # Search cache TTL in seconds

    # Document chunking configuration
    CHUNK_SIZE: int = 1000  # Target chunk size in characters
    CHUNK_OVERLAP: int = 200  # Overlap between chunks in characters
    CHUNK_STRATEGY: str = "semantic"  # Chunking strategy: fixed, semantic, hybrid
    CHUNK_MIN_SIZE: int = 100  # Minimum chunk size
    CHUNK_MAX_SIZE: int = 2000  # Maximum chunk size

    # --- Docling Enhanced Configuration ---
    # Docling basic configuration
    DOCLING_ENABLED: bool = True  # Enable/disable Docling integration
    DOCLING_MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB max file size
    DOCLING_SUPPORTED_FORMATS: str = "pdf,docx,pptx,html,txt,xlsx"  # Supported file formats
    DOCLING_OCR_ENABLED: bool = True  # Enable OCR for scanned documents
    DOCLING_TABLE_EXTRACTION: bool = True  # Enable table extraction
    DOCLING_IMAGE_EXTRACTION: bool = True  # Enable image/figure extraction
    DOCLING_LAYOUT_ANALYSIS: bool = True  # Enable advanced layout analysis

    # Docling OCR configuration
    DOCLING_OCR_LANGUAGES: str = "en"  # OCR languages (comma-separated)
    DOCLING_OCR_ENGINE: str = "tesseract"  # OCR engine: tesseract, easyocr
    DOCLING_OCR_RESOLUTION: int = 300  # OCR resolution DPI
    DOCLING_OCR_TIMEOUT: int = 60  # OCR timeout in seconds

    # Docling processing configuration
    DOCLING_PROCESS_TIMEOUT: int = 300  # Processing timeout in seconds
    DOCLING_MEMORY_LIMIT: int = 1024  # Memory limit in MB
    DOCLING_PARALLEL_PROCESSING: bool = True  # Enable parallel processing
    DOCLING_MAX_WORKERS: int = 4  # Maximum parallel workers

    # Docling export configuration
    DOCLING_EXPORT_FORMAT: str = "markdown"  # Export format: markdown, json, html
    DOCLING_EXPORT_IMAGES: bool = True  # Include images in export
    DOCLING_EXPORT_TABLES: bool = True  # Include tables in export
    DOCLING_EXPORT_METADATA: bool = True  # Include metadata in export

    # --- Ollama LLM Configuration ---
    OLLAMA_HOST: str = "http://127.0.0.1:11434"  # Ollama API host
    OLLAMA_MODEL: str = "llama3.2:latest"  # Default model for generation
    OLLAMA_CHAT_MODEL: str = "llama3.2:latest"  # Model for chat operations
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text:latest"  # Model for embeddings
    OLLAMA_TIMEOUT: int = 120  # Request timeout in seconds
    OLLAMA_CACHE_TTL: int = 3600  # Response cache TTL in seconds

    # --- LlamaIndex & RAG Configuration ---
    LLAMAINDEX_ENABLED: bool = True  # Enable LlamaIndex integration
    LLAMAINDEX_EMBED_MODEL: str = "local:BAAI/bge-small-en-v1.5"  # Embedding model for LlamaIndex
    LLAMAINDEX_CHUNK_SIZE: int = 1024  # Chunk size for indexing
    LLAMAINDEX_CHUNK_OVERLAP: int = 200  # Chunk overlap
    LLAMAINDEX_TOP_K: int = 5  # Top-k results for retrieval
    LLAMAINDEX_SIMILARITY_CUTOFF: float = 0.7  # Similarity threshold
    LLAMAINDEX_HYBRID_SEARCH_ENABLED: bool = True  # Enable hybrid search (dense + sparse)
    LLAMAINDEX_SPARSE_TOP_K: int = 12  # Top-k for sparse retrieval
    LLAMAINDEX_ALPHA: float = 0.5  # Weight for hybrid search (0=sparse, 1=dense)

    # Qdrant sparse vector configuration for hybrid search
    QDRANT_SPARSE_MODEL: str = "prithvida/Splade_PP_en_v1"  # FastEmbed sparse model

    # RAG service configuration
    RAG_TOP_K: int = 5  # Default top-k for RAG retrieval
    RAG_SIMILARITY_THRESHOLD: float = 0.7  # Minimum similarity for RAG
    RAG_MAX_CONTEXT_LENGTH: int = 8000  # Maximum context length in chars
    RAG_ENABLE_RERANKING: bool = False  # Enable reranking (future enhancement)

    # --- WebRTC Configuration ---
    # STUN servers (comma-separated list of URLs)
    WEBRTC_STUN_URLS: str = "stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302"
    
    # TURN servers (optional, comma-separated list of URLs)
    WEBRTC_TURN_URLS: Optional[str] = None  # e.g., "turn:turn.example.com:3478"
    WEBRTC_TURN_USERNAME: Optional[str] = None  # TURN server username
    WEBRTC_TURN_CREDENTIAL: Optional[SecretStr] = None  # TURN server password
    
    # WebRTC policies
    WEBRTC_ICE_TRANSPORT_POLICY: str = "all"  # all, relay (force TURN)
    WEBRTC_BUNDLE_POLICY: str = "balanced"  # balanced, max-compat, max-bundle
    WEBRTC_RTCP_MUX_POLICY: str = "require"  # require, negotiate
    
    # Room and presence configuration
    WEBRTC_ROOM_PRESENCE_TTL: int = 30  # Heartbeat timeout in seconds
    WEBRTC_MAX_PARTICIPANTS_PER_ROOM: int = 50  # Maximum participants per room

    # --- IPAM Configuration ---
    # IPAM rate limiting configuration
    IPAM_REGION_CREATE_RATE_LIMIT: int = 100  # Max regions per hour per user
    IPAM_HOST_CREATE_RATE_LIMIT: int = 1000  # Max hosts per hour per user
    IPAM_QUERY_RATE_LIMIT: int = 500  # Max queries per hour per user

    # IPAM audit and retention configuration
    IPAM_AUDIT_RETENTION_DAYS: int = 365  # Days to keep audit history

    # IPAM quota configuration
    IPAM_DEFAULT_REGION_QUOTA: int = 1000  # Default max regions per user
    IPAM_DEFAULT_HOST_QUOTA: int = 10000  # Default max hosts per user

    # IPAM capacity monitoring configuration
    IPAM_CAPACITY_WARNING_THRESHOLD: int = 80  # Warning at 80% utilization
    IPAM_CAPACITY_CRITICAL_THRESHOLD: int = 100  # Critical at 100% utilization
    IPAM_REGION_CAPACITY_THRESHOLD: int = 90  # Region warning at 90% utilization

    # IPAM notification configuration
    IPAM_NOTIFICATION_ENABLED: bool = True  # Enable/disable notifications
    IPAM_NOTIFICATION_CHANNELS: str = "email"  # Comma-separated: email,webhook,in-app
    IPAM_NOTIFICATION_EMAIL_ENABLED: bool = True  # Enable email notifications
    IPAM_NOTIFICATION_WEBHOOK_ENABLED: bool = False  # Enable webhook notifications
    IPAM_NOTIFICATION_WEBHOOK_URL: Optional[str] = None  # Webhook URL for notifications
    IPAM_NOTIFICATION_IN_APP_ENABLED: bool = False  # Enable in-app notifications

    # IPAM per-country threshold overrides (JSON format)
    # Example: {"India": {"warning": 70, "critical": 90}, "United States": {"warning": 85, "critical": 95}}
    IPAM_COUNTRY_THRESHOLDS: Optional[str] = None  # JSON string of country-specific thresholds

    # IPAM per-region threshold overrides (JSON format)
    # Example: {"region_id_1": 85, "region_id_2": 95}
    IPAM_REGION_THRESHOLDS: Optional[str] = None  # JSON string of region-specific thresholds

    # IPAM background task intervals
    IPAM_CAPACITY_MONITORING_INTERVAL: int = 900  # 15 minutes in seconds
    IPAM_RESERVATION_CLEANUP_INTERVAL: int = 3600  # 1 hour in seconds
    IPAM_RESERVATION_EXPIRATION_INTERVAL: int = 3600  # 1 hour in seconds

    # --- Cluster Configuration (Distributed SBD Architecture) ---
    # Cluster basic configuration
    CLUSTER_ENABLED: bool = False  # Enable/disable cluster mode
    CLUSTER_NODE_ID: Optional[str] = None  # Unique node identifier (auto-generated if not set)
    CLUSTER_NODE_ROLE: str = "standalone"  # standalone, master, replica
    CLUSTER_TOPOLOGY_TYPE: str = "master-slave"  # master-slave, master-master, multi-master
    CLUSTER_REPLICATION_FACTOR: int = 2  # Number of replicas

    # Node discovery configuration
    CLUSTER_DISCOVERY_METHOD: str = "static"  # static, dns, consul, etcd
    CLUSTER_SEED_NODES: Optional[str] = None  # Comma-separated list of seed nodes (host:port)
    CLUSTER_ADVERTISE_ADDRESS: Optional[str] = None  # Address to advertise to other nodes
    CLUSTER_BIND_ADDRESS: str = "0.0.0.0"  # Address to bind cluster communication

    # Replication configuration
    CLUSTER_REPLICATION_ENABLED: bool = True  # Enable/disable replication
    CLUSTER_REPLICATION_MODE: str = "async"  # async, sync, semi-sync
    CLUSTER_EVENT_LOG_RETENTION_DAYS: int = 30  # Days to keep replication event log
    CLUSTER_BATCH_SIZE: int = 100  # Batch size for replication events
    CLUSTER_REPLICATION_TIMEOUT: int = 30  # Replication timeout in seconds
    CLUSTER_MAX_REPLICATION_LAG: float = 10.0  # Max acceptable lag in seconds

    # Health check configuration
    CLUSTER_HEARTBEAT_INTERVAL: int = 5  # Heartbeat interval in seconds
    CLUSTER_HEALTH_CHECK_TIMEOUT: int = 3  # Health check timeout in seconds
    CLUSTER_FAILURE_THRESHOLD: int = 3  # Consecutive failures before marking unhealthy
    CLUSTER_RECOVERY_THRESHOLD: int = 2  # Consecutive successes before marking healthy

    # Load balancing configuration
    CLUSTER_LOAD_BALANCING_ALGORITHM: str = "round-robin"  # round-robin, least-connections, weighted, ip-hash
    CLUSTER_STICKY_SESSIONS: bool = True  # Enable sticky sessions
    CLUSTER_READ_PREFERENCE: str = "nearest"  # nearest, primary, secondary, any
    CLUSTER_WRITE_CONCERN: str = "majority"  # majority, all, one

    # Failover configuration
    CLUSTER_AUTO_FAILOVER: bool = True  # Enable automatic failover
    CLUSTER_FAILOVER_TIMEOUT: int = 30  # Seconds before triggering failover
    CLUSTER_MIN_HEALTHY_REPLICAS: int = 1  # Minimum healthy replicas required
    CLUSTER_PROMOTE_ON_MASTER_FAILURE: bool = True  # Auto-promote replica to master

    # Circuit breaker configuration
    CLUSTER_CIRCUIT_BREAKER_ENABLED: bool = True  # Enable circuit breaker pattern
    CLUSTER_CIRCUIT_BREAKER_THRESHOLD: int = 5  # Failures before opening circuit
    CLUSTER_CIRCUIT_BREAKER_TIMEOUT: int = 60  # Seconds before attempting recovery
    CLUSTER_CIRCUIT_BREAKER_HALF_OPEN_REQUESTS: int = 3  # Requests in half-open state

    # Security configuration
    CLUSTER_AUTH_TOKEN: Optional[SecretStr] = None  # Shared secret for node authentication
    CLUSTER_MTLS_ENABLED: bool = False  # Enable mutual TLS
    CLUSTER_MTLS_CERT_PATH: Optional[str] = None  # Path to TLS certificate
    CLUSTER_MTLS_KEY_PATH: Optional[str] = None  # Path to TLS private key
    CLUSTER_MTLS_CA_PATH: Optional[str] = None  # Path to CA certificate
    CLUSTER_ENCRYPTION_ENABLED: bool = False  # Enable data encryption in transit

    # Owner validation configuration
    CLUSTER_REQUIRE_OWNER_SYNC: bool = True  # Require owner account on all nodes
    CLUSTER_OWNER_VALIDATION_INTERVAL: int = 3600  # Owner validation interval in seconds
    CLUSTER_OWNER_AUTO_SYNC: bool = False  # Auto-sync owner account to new nodes

    # Monitoring and metrics configuration
    CLUSTER_METRICS_ENABLED: bool = True  # Enable cluster metrics collection
    CLUSTER_METRICS_INTERVAL: int = 10  # Metrics collection interval in seconds
    CLUSTER_AUDIT_ENABLED: bool = True  # Enable cluster audit logging
    CLUSTER_AUDIT_RETENTION_DAYS: int = 365  # Days to keep audit logs

    # Performance tuning
    CLUSTER_MAX_CONCURRENT_REPLICATIONS: int = 50  # Max concurrent replication operations
    CLUSTER_CONNECTION_POOL_SIZE: int = 20  # Connection pool size per node
    CLUSTER_REQUEST_TIMEOUT: int = 30  # Request timeout in seconds
    CLUSTER_RETRY_MAX_ATTEMPTS: int = 3  # Max retry attempts for failed operations
    CLUSTER_RETRY_BACKOFF_FACTOR: float = 2.0  # Exponential backoff factor

    # Consensus configuration (for leader election)
    CLUSTER_CONSENSUS_ALGORITHM: str = "raft"  # raft, paxos
    CLUSTER_ELECTION_TIMEOUT_MIN: int = 150  # Min election timeout in ms
    CLUSTER_ELECTION_TIMEOUT_MAX: int = 300  # Max election timeout in ms
    CLUSTER_LEADER_LEASE_DURATION: int = 500  # Leader lease duration in ms

    # --- Chat System Configuration ---
    # Chat feature toggle
    CHAT_ENABLED: bool = True  # Enable/disable chat system

    # Conversation history configuration
    CHAT_MAX_HISTORY_LENGTH: int = 20  # Maximum messages to include in conversation context
    CHAT_HISTORY_CACHE_TTL: int = 3600  # History cache TTL in seconds (1 hour)

    # Vector search configuration
    CHAT_DEFAULT_TOP_K: int = 5  # Default number of vector search results

    # Streaming configuration
    CHAT_STREAM_TIMEOUT: int = 300  # Streaming timeout in seconds (5 minutes)

    # Rate limiting configuration
    CHAT_ENABLE_RATE_LIMITING: bool = True  # Enable rate limiting for chat operations
    CHAT_MESSAGE_RATE_LIMIT: int = 20  # Max messages per minute per user
    CHAT_SESSION_CREATE_LIMIT: int = 5  # Max sessions created per hour per user

    # Query caching configuration
    CHAT_ENABLE_QUERY_CACHE: bool = True  # Enable query response caching
    CHAT_CACHE_TTL: int = 3600  # Query cache TTL in seconds (1 hour)

    # Input validation configuration
    CHAT_TOKEN_ENCODING: str = "cl100k_base"  # Token encoding for tiktoken (GPT-4 tokenizer)
    CHAT_MAX_QUERY_LENGTH: int = 10000  # Maximum query length in characters
    CHAT_MAX_MESSAGE_LENGTH: int = 50000  # Maximum message content length in characters

    # Error recovery configuration
    CHAT_LLM_MAX_RETRIES: int = 3  # Maximum retries for LLM calls
    CHAT_LLM_BACKOFF_FACTOR: float = 2.0  # Exponential backoff factor for LLM retries
    CHAT_VECTOR_MAX_RETRIES: int = 2  # Maximum retries for vector search
    CHAT_VECTOR_BACKOFF_FACTOR: float = 1.5  # Exponential backoff factor for vector retries

    # Session management configuration
    CHAT_AUTO_GENERATE_TITLES: bool = True  # Auto-generate session titles from first message
    CHAT_TITLE_MAX_LENGTH: int = 50  # Maximum length for session titles

    # Feedback and analytics configuration
    CHAT_ENABLE_MESSAGE_VOTING: bool = True  # Enable message voting (upvote/downvote)
    CHAT_ENABLE_SESSION_STATISTICS: bool = True  # Enable session statistics tracking

    # --- Admin/Abuse Service Constants ---
    WHITELIST_KEY: str = "abuse:reset:whitelist"
    BLOCKLIST_KEY: str = "abuse:reset:blocklist"
    ABUSE_FLAG_PREFIX: str = "abuse:reset:flagged"
    USERS_COLLECTION: str = "users"
    ABUSE_EVENTS_COLLECTION: str = "reset_abuse_events"

    @field_validator("SECRET_KEY", "FERNET_KEY", "TURNSTILE_SITEKEY", "TURNSTILE_SECRET", mode="before")
    @classmethod
    def no_hardcoded_secrets(cls, v: Any, info: Any) -> Any:
        """
        Validates that critical secrets are not hardcoded or empty.

        Checks if the value contains placeholder text like "change" or "0000", or if it is
        empty/whitespace. This enforces security best practices by ensuring secrets are
        loaded from a secure source (environment or config file).

        Args:
            v (Any): The value to validate.
            info (Any): Validation info containing the field name.

        Returns:
            Any: The validated value.

        Raises:
            ValueError: If the value is empty, hardcoded, or insecure.
        """
        if not v or "change" in str(v).lower() or "0000" in str(v) or not str(v).strip():
            raise ValueError(f"{info.field_name} must be set via environment or .sbd and not hardcoded!")
        return v

    @field_validator("MONGODB_URL", mode="before")
    @classmethod
    def no_empty_urls(cls, v: Any, info: Any) -> Any:
        """
        Validates that the MongoDB URL is not empty.

        Args:
            v (Any): The URL string.
            info (Any): Validation info.

        Returns:
            Any: The validated URL.

        Raises:
            ValueError: If the URL is empty or whitespace.
        """
        if not v or not str(v).strip():
            raise ValueError(f"{info.field_name} must be set via environment or .sbd and not empty!")
        return v

    @field_validator("MCP_RATE_LIMIT_REQUESTS", "MCP_MAX_CONCURRENT_TOOLS", mode="before")
    @classmethod
    def validate_positive_integers(cls, v: Any, info: Any) -> int:
        """
        Validates that numeric settings are positive integers.

        Args:
            v (Any): The value to validate.
            info (Any): Validation info.

        Returns:
            int: The validated positive integer.

        Raises:
            ValueError: If the value is not a positive integer.
        """
        value = int(v)
        if value <= 0:
            raise ValueError(f"{info.field_name} must be a positive integer")
        return value

    @field_validator("MCP_REQUEST_TIMEOUT", "MCP_TOOL_EXECUTION_TIMEOUT", mode="before")
    @classmethod
    def validate_timeout_values(cls, v: Any, info: Any) -> int:
        """
        Validates that timeout values are within a reasonable range (1-300 seconds).

        Args:
            v (Any): The timeout value.
            info (Any): Validation info.

        Returns:
            int: The validated timeout.

        Raises:
            ValueError: If the timeout is out of range.
        """
        timeout = int(v)
        if timeout < 1 or timeout > 300:
            raise ValueError(f"{info.field_name} must be between 1 and 300 seconds")
        return timeout

    @field_validator("MCP_RETRY_BACKOFF_FACTOR", mode="before")
    @classmethod
    def validate_backoff_factor(cls, v: Any) -> float:
        """
        Validates that the retry backoff factor is within a reasonable range (1.0-10.0).

        Args:
            v (Any): The backoff factor.

        Returns:
            float: The validated factor.

        Raises:
            ValueError: If the factor is out of range.
        """
        factor = float(v)
        if factor < 1.0 or factor > 10.0:
            raise ValueError("MCP_RETRY_BACKOFF_FACTOR must be between 1.0 and 10.0")
        return factor

    @property
    def is_production(self) -> bool:
        """
        Determine if the application is running in production mode.

        This property provides a simple boolean flag to check the deployment environment.
        **Production mode** is defined as `DEBUG=False`, which typically means:
        - Stricter security policies
        - Documentation may be restricted
        - Verbose error messages are suppressed
        - Performance optimizations are enabled

        Returns:
            `bool`: `True` if running in production (`DEBUG=False`), `False` otherwise.

        Example:
            ```python
            from second_brain_database.config import settings

            if settings.is_production:
                # Use production logging
                logger.setLevel(logging.WARNING)
            else:
                # Use debug logging
                logger.setLevel(logging.DEBUG)
            ```

        Note:
            This is the inverse of the `DEBUG` setting. It does **not** check for
            environment variables like `ENV=production`, only the `DEBUG` flag.

        See Also:
            - `docs_should_be_enabled`: For documentation access control
            - `mcp_should_be_enabled`: For MCP security in production
        """
        return not self.DEBUG

    @property
    def docs_should_be_enabled(self) -> bool:
        """
        Check if API documentation endpoints should be accessible.

        This property implements a smart policy for documentation access:
        - **Development** (`DEBUG=True`): Docs are **always** enabled for convenience
        - **Production** (`DEBUG=False`): Docs are enabled only if `DOCS_ENABLED=True`

        This allows for secure production deployments where docs can be disabled entirely,
        while ensuring developers always have access during local development.

        Returns:
            `bool`: `True` if documentation should be served, `False` otherwise.

        Example:
            ```python
            from second_brain_database.config import settings

            # In main.py
            app = FastAPI(
                docs_url="/docs" if settings.docs_should_be_enabled else None,
                redoc_url="/redoc" if settings.docs_should_be_enabled else None,
            )
            ```

        Note:
            Even if this returns `True`, you may want to apply additional access control
            via `DOCS_REQUIRE_AUTH` or `DOCS_ALLOWED_IPS` in production.

        See Also:
            - `DOCS_ENABLED`: The underlying configuration flag
            - `DOCS_REQUIRE_AUTH`: For requiring authentication
            - `DOCS_ALLOWED_IPS`: For IP-based access control
        """
        return self.DEBUG or self.DOCS_ENABLED

    @property
    def should_cache_docs(self) -> bool:
        """
        Check if OpenAPI documentation should be cached for performance.

        Documentation caching is a production optimization that prevents regenerating
        the OpenAPI schema on every request. Caching is only enabled when **both**:
        1. Running in production (`is_production=True`)
        2. Cache is explicitly enabled (`DOCS_CACHE_ENABLED=True`)

        In **development**, caching is disabled to ensure schema changes are immediately
        reflected (e.g., when adding new endpoints or modifying docstrings).

        Returns:
            `bool`: `True` if documentation should be cached, `False` for dynamic generation.

        Example:
            ```python
            from second_brain_database.config import settings

            @app.get("/openapi.json")
            async def get_openapi_schema():
                if settings.should_cache_docs and cached_schema:
                    return cached_schema
                return generate_openapi_schema()
            ```

        Note:
            Caching significantly improves Swagger UI load times in production by avoiding
            repeated schema generation. The cache TTL is controlled by `DOCS_CACHE_TTL`.

        See Also:
            - `DOCS_CACHE_TTL`: Time-to-live for cached documentation
            - `is_production`: Production environment check
        """
        return self.is_production and self.DOCS_CACHE_ENABLED

    @property
    def mcp_should_be_enabled(self) -> bool:
        """
        Determine if the Model Context Protocol (MCP) server should be started.

        This property implements a **security-first** policy for MCP server activation:
        - **Always enabled** if `MCP_ENABLED=True` **and** security is configured
        - **Disabled in production** if security is not enabled (`MCP_SECURITY_ENABLED=False`)
        - Development environments can run with security disabled for testing

        This prevents accidentally exposing an unsecured MCP server in production, which
        could allow unauthorized access to tools and resources.

        Returns:
            `bool`: `True` if MCP server should be initialized, `False` to skip startup.

        Example:
            ```python
            from second_brain_database.config import settings

            # In lifespan startup
            if settings.mcp_should_be_enabled:
                await mcp_server_manager.initialize()
                await mcp_server_manager.start_server()
            else:
                logger.info("MCP server disabled (security not configured)")
            ```

        Warning:
            In production, this will return `False` if `MCP_SECURITY_ENABLED=False`,
            even if `MCP_ENABLED=True`. Always configure security for production MCP.

        Note:
            Security features include:
            - Authentication via `MCP_AUTH_TOKEN`
            - Rate limiting via `MCP_RATE_LIMIT_ENABLED`
            - Audit logging via `MCP_AUDIT_ENABLED`

        See Also:
            - `MCP_SECURITY_ENABLED`: Master security toggle
            - `MCP_AUTH_TOKEN`: Bearer token for authentication
            - `integrations.mcp.server`: MCP server implementation
        """
        return self.MCP_ENABLED and not (self.is_production and not self.MCP_SECURITY_ENABLED)

    @property
    def mcp_allowed_origins_list(self) -> list:
        """
        Parse the comma-separated `MCP_ALLOWED_ORIGINS` into a list of origin strings.

        This property converts the environment variable format (comma-separated string)
        into a Python list for use with CORS middleware. Empty strings and whitespace
        are automatically stripped.

        Returns:
            `List[str]`: A list of allowed origins for MCP CORS. Empty list if not configured.

        Example:
            ```python
            from second_brain_database.config import settings

            # Environment: MCP_ALLOWED_ORIGINS="https://app.example.com,https://admin.example.com"
            origins = settings.mcp_allowed_origins_list
            # Result: ["https://app.example.com", "https://admin.example.com"]

            # Use with CORS middleware
            app.add_middleware(
                CORSMiddleware,
                allow_origins=settings.mcp_allowed_origins_list,
            )
            ```

        Note:
            - If `MCP_ALLOWED_ORIGINS` is `None` or empty, returns `[]`
            - Whitespace around each origin is automatically trimmed
            - For unrestricted access, set `MCP_ALLOWED_ORIGINS="*"` (not recommended in production)

        See Also:
            - `MCP_CORS_ENABLED`: Enable CORS for MCP server
            - `mcp_ip_whitelist_list`: For IP-based access control
        """
        if not self.MCP_ALLOWED_ORIGINS:
            return []
        return [origin.strip() for origin in self.MCP_ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def mcp_ip_whitelist_list(self) -> list:
        """
        Parse the comma-separated `MCP_IP_WHITELIST` into a list of IP addresses.

        This property converts the IP whitelist from environment variable format into
        a Python list for access control checks. Supports both IPv4 and IPv6 addresses.

        Returns:
            `List[str]`: A list of whitelisted IP addresses. Empty list if not configured.

        Example:
            ```python
            from second_brain_database.config import settings

            # Environment: MCP_IP_WHITELIST="192.168.1.100,10.0.0.5"
            whitelist = settings.mcp_ip_whitelist_list
            # Result: ["192.168.1.100", "10.0.0.5"]

            # Use in access control
            def check_ip_access(client_ip: str) -> bool:
                if not settings.mcp_ip_whitelist_list:
                    return True  # No whitelist = allow all
                return client_ip in settings.mcp_ip_whitelist_list
            ```

        Note:
            - If `MCP_IP_WHITELIST` is `None` or empty, returns `[]` (no restrictions)
            - Supports CIDR notation if your access control logic handles it
            - For localhost testing, include `127.0.0.1` and `::1` (IPv6)

        Warning:
            IP whitelisting is a basic security measure. For production, combine with
            authentication (`MCP_AUTH_TOKEN`) and TLS (`MCP_MTLS_ENABLED`).

        See Also:
            - `MCP_AUTH_TOKEN`: Token-based authentication
            - `mcp_allowed_origins_list`: For origin-based access control
        """
        if not self.MCP_IP_WHITELIST:
            return []
        return [ip.strip() for ip in self.MCP_IP_WHITELIST.split(",") if ip.strip()]

    @property
    def ipam_notification_channels_list(self) -> list:
        """
        Parse the comma-separated `IPAM_NOTIFICATION_CHANNELS` into a list of channel types.

        This property converts the notification channels configuration from environment
        variable format into a Python list. Supported channels include: `email`, `webhook`,
        and `in-app`.

        Returns:
            `List[str]`: A list of enabled notification channels. Defaults to `["email"]` if not configured.

        Example:
            ```python
            from second_brain_database.config import settings

            #Environment: IPAM_NOTIFICATION_CHANNELS="email,webhook,in-app"
            channels = settings.ipam_notification_channels_list
            # Result: ["email", "webhook", "in-app"]

            # Use in notification logic
            for channel in settings.ipam_notification_channels_list:
                if channel == "email":
                    send_email_notification(event)
                elif channel == "webhook":
                    trigger_webhook(event)
                elif channel == "in-app":
                    create_in_app_notification(event)
            ```

        Note:
            - If `IPAM_NOTIFICATION_CHANNELS` is `None` or empty, defaults to `["email"]`
            - Whitespace around each channel name is automatically trimmed
            - Channel-specific enable flags (e.g., `IPAM_NOTIFICATION_EMAIL_ENABLED`) take precedence

        See Also:
            - `IPAM_NOTIFICATION_ENABLED`: Master toggle for all IPAM notifications
            - `IPAM_NOTIFICATION_EMAIL_ENABLED`: Email-specific toggle
            - `IPAM_NOTIFICATION_WEBHOOK_ENABLED`: Webhook-specific toggle
        """
        if not self.IPAM_NOTIFICATION_CHANNELS:
            return ["email"]  # Default to email
        return [channel.strip() for channel in self.IPAM_NOTIFICATION_CHANNELS.split(",") if channel.strip()]

    @property
    def ipam_country_thresholds_dict(self) -> dict:
        """
        Parse the JSON-formatted `IPAM_COUNTRY_THRESHOLDS` into a dictionary.

        This property allows overriding default capacity thresholds on a per-country basis.
        The format is a JSON object mapping country names to threshold objects.

        Returns:
            `Dict[str, Dict[str, int]]`: A dictionary mapping country names to threshold configs.
                Empty dict if not configured or parsing fails.

        Example:
            ```python
            from second_brain_database.config import settings

            # Environment: IPAM_COUNTRY_THRESHOLDS='{"India": {"warning": 70, "critical": 90}}'
            thresholds = settings.ipam_country_thresholds_dict
            # Result: {"India": {"warning": 70, "critical": 90}}

            # Use in capacity monitoring
            country = "India"
            utilization = calculate_utilization(country)
            warning = thresholds.get(country, {}).get("warning", settings.IPAM_CAPACITY_WARNING_THRESHOLD)

            if utilization >= warning:
                send_warning_alert(country, utilization)
            ```

        Note:
            - JSON must be valid and properly escaped in environment variables
            - If parsing fails, returns `{}` (falls back to global thresholds)
            - Country names must match exactly (case-sensitive)

        See Also:
            - `IPAM_CAPACITY_WARNING_THRESHOLD`: Global warning threshold
            - `IPAM_CAPACITY_CRITICAL_THRESHOLD`: Global critical threshold
            - `ipam_region_thresholds_dict`: For region-specific overrides
        """
        if not self.IPAM_COUNTRY_THRESHOLDS:
            return {}
        try:
            import json
            return json.loads(self.IPAM_COUNTRY_THRESHOLDS)
        except Exception:
            return {}

    @property
    def ipam_region_thresholds_dict(self) -> dict:
        """
        Parse the JSON-formatted `IPAM_REGION_THRESHOLDS` into a dictionary.

        This property allows overriding default capacity thresholds on a per-region basis.
        Regions are identified by their `region_id` (UUID format).

        Returns:
            `Dict[str, int]`: A dictionary mapping `region_id` to warning threshold percentages.
                Empty dict if not configured or parsing fails.

        Example:
            ```python
            from second_brain_database.config import settings

            # Environment: IPAM_REGION_THRESHOLDS='{"region_abc123": 85, "region_def456": 95}'
            thresholds = settings.ipam_region_thresholds_dict
            # Result: {"region_abc123": 85, "region_def456": 95}

            # Use in region monitoring
            region_id = "region_abc123"
            utilization = calculate_region_utilization(region_id)
            threshold = thresholds.get(region_id, settings.IPAM_REGION_CAPACITY_THRESHOLD)

            if utilization >= threshold:
                send_region_alert(region_id, utilization)
            ```

        Note:
            - JSON must be valid and properly escaped
            - If parsing fails, returns `{}` (uses global `IPAM_REGION_CAPACITY_THRESHOLD`)
            - Region IDs are UUIDs generated when creating regions

        See Also:
            - `IPAM_REGION_CAPACITY_THRESHOLD`: Global region threshold (default 90%)
            - `ipam_country_thresholds_dict`: For country-specific overrides
        """
        if not self.IPAM_REGION_THRESHOLDS:
            return {}
        try:
            import json
            return json.loads(self.IPAM_REGION_THRESHOLDS)
        except Exception:
            return {}

    @property
    def cluster_seed_nodes_list(self) -> list:
        """
        Parse the comma-separated `CLUSTER_SEED_NODES` into a list of node addresses.

        Seed nodes are the initial contact points for cluster discovery. Each node is
        specified in `host:port` format (e.g., `"192.168.1.10:8000,192.168.1.11:8000"`).

        Returns:
            `List[str]`: A list of seed node addresses in `host:port` format. Empty if not configured.

        Example:
            ```python
            from second_brain_database.config import settings

            # Environment: CLUSTER_SEED_NODES="node1.example.com:8000,node2.example.com:8000"
            seeds = settings.cluster_seed_nodes_list
            # Result: ["node1.example.com:8000", "node2.example.com:8000"]

            # Use in cluster discovery
            for seed_node in settings.cluster_seed_nodes_list:
                try:
                    await discover_and_join_cluster(seed_node)
                    break  # Successfully joined
                except ConnectionError:
                    continue  # Try next seed
            ```

        Note:
            - If `CLUSTER_SEED_NODES` is `None` or empty, returns `[]` (standalone mode)
            - Whitespace is automatically trimmed
            - At least one seed node is typically required for cluster formation

        See Also:
            - `CLUSTER_DISCOVERY_METHOD`: Discovery mechanism (static, dns, consul)
            - `cluster_should_be_enabled`: Cluster activation check
        """
        if not self.CLUSTER_SEED_NODES:
            return []
        return [node.strip() for node in self.CLUSTER_SEED_NODES.split(",") if node.strip()]

    @property
    def cluster_should_be_enabled(self) -> bool:
        """
        Determine if cluster mode should be active based on configuration.

        Cluster mode is enabled only when **both** conditions are met:
        1. `CLUSTER_ENABLED=True`
        2. `CLUSTER_NODE_ROLE` is **not** `"standalone"`

        This prevents accidental cluster activation in standalone deployments.

        Returns:
            `bool`: `True` if cluster features should be initialized, `False` otherwise.

        Example:
            ```python
            from second_brain_database.config import settings

            # In application startup
            if settings.cluster_should_be_enabled:
                await cluster_manager.initialize()
                await replication_service.start()
            else:
                logger.info("Running in standalone mode")
            ```

        Note:
            Valid non-standalone roles: `"master"`, `"replica"`, `"multi-master"`

        See Also:
            - `cluster_is_master`: Check if this node is a master
            - `cluster_is_replica`: Check if this node is a replica
        """
        return self.CLUSTER_ENABLED and self.CLUSTER_NODE_ROLE != "standalone"

    @property
    def cluster_is_master(self) -> bool:
        """
        Check if this node is configured as a cluster master.

        Master nodes accept write operations and replicate data to replica nodes.

        Returns:
            `bool`: `True` if `CLUSTER_NODE_ROLE="master"`, `False` otherwise.

        Example:
            ```python
            from second_brain_database.config import settings

            # Route write operations to master
            if not settings.cluster_is_master:
                raise HTTPException(status_code=403, detail="Write operations only allowed on master")
            ```

        See Also:
            - `cluster_is_replica`: Check for replica role
            - `CLUSTER_NODE_ROLE`: The underlying configuration value
        """
        return self.CLUSTER_NODE_ROLE == "master"

    @property
    def cluster_is_replica(self) -> bool:
        """
        Check if this node is configured as a cluster replica.

        Replica nodes serve read operations and receive data from master nodes.

        Returns:
            `bool`: `True` if `CLUSTER_NODE_ROLE="replica"`, `False` otherwise.

        Example:
            ```python
            from second_brain_database.config import settings

            # Redirect writes to master
            if settings.cluster_is_replica:
                master_url = get_master_node_url()
                return RedirectResponse(url=f"{master_url}{request.url.path}")
            ```

        See Also:
            - `cluster_is_master`: Check for master role
            - `CLUSTER_READ_PREFERENCE`: Read routing preferences
        """
        return self.CLUSTER_NODE_ROLE == "replica"

    @property
    def cluster_mtls_configured(self) -> bool:
        """
        Check if mutual TLS (mTLS) is properly configured for cluster communication.

        mTLS requires **all three** certificate files to be specified:
        1. `CLUSTER_MTLS_CERT_PATH` - Node certificate
        2. `CLUSTER_MTLS_KEY_PATH` - Private key
        3. `CLUSTER_MTLS_CA_PATH` - Certificate Authority (CA) certificate

        Returns:
            `bool`: `True` if mTLS is enabled and all cert paths are configured, `False` otherwise.

        Example:
            ```python
            from second_brain_database.config import settings

            # In cluster connection setup
            if settings.cluster_mtls_configured:
                ssl_context = create_ssl_context(
                    certfile=settings.CLUSTER_MTLS_CERT_PATH,
                    keyfile=settings.CLUSTER_MTLS_KEY_PATH,
                    cafile=settings.CLUSTER_MTLS_CA_PATH,
                )
                connector = aiohttp.TCPConnector(ssl=ssl_context)
            else:
                connector = aiohttp.TCPConnector()  # Unencrypted
            ```

        Warning:
            Production clusters should **always** use mTLS to prevent eavesdropping and
            man-in-the-middle attacks. Unencrypted cluster traffic is a security risk.

        See Also:
            - `CLUSTER_MTLS_ENABLED`: Master mTLS toggle
            - `CLUSTER_AUTH_TOKEN`: Alternative authentication method
        """
        if not self.CLUSTER_MTLS_ENABLED:
            return False
        return all([
            self.CLUSTER_MTLS_CERT_PATH,
            self.CLUSTER_MTLS_KEY_PATH,
            self.CLUSTER_MTLS_CA_PATH
        ])


# Global settings instance
settings: Settings = Settings()

# Compute effective REDIS_URL if not explicitly provided.
# Precedence: explicit REDIS_URL -> REDIS_STORAGE_URI -> constructed from host/port/db and optional credentials.
if not settings.REDIS_URL:
    if settings.REDIS_STORAGE_URI:
        settings.REDIS_URL = settings.REDIS_STORAGE_URI
    else:
        # Build credentials part
        creds = ""
        if settings.REDIS_USERNAME or settings.REDIS_PASSWORD:
            username = settings.REDIS_USERNAME or ""
            password = settings.REDIS_PASSWORD.get_secret_value() if settings.REDIS_PASSWORD else ""
            # If only password present, use :password@ form
            if username and password:
                creds = f"{username}:{password}@"
            elif password and not username:
                creds = f":{password}@"

        settings.REDIS_URL = f"redis://{creds}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
