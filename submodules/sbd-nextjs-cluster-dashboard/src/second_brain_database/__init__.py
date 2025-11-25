"""
# Second Brain Database

A **production-grade, comprehensive FastAPI-based knowledge management system** for managing your "second brain".
This package provides a **complete backend API** for storing, organizing, and retrieving information efficiently across
multiple domains including notes, documents, family management, digital assets, IP address management (IPAM), chat/RAG,
and more.

## Architecture Overview

The application is built on **modern async Python** with a **microservices-inspired modular architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│          Second Brain Database Architecture                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   FastAPI    │  │   Routers    │  │  Middleware   │     │
│  │  (Core App)  │◄─┤  (25+ APIs)  │◄─┤  (CORS, Auth) │     │
│  └──────┬───────┘  └──────────────┘  └──────────────┘     │
│         │                                                    │
│         ├──► Services Layer (Business Logic)                │
│         ├──► Managers Layer (Resource Management)           │
│         └──► Database Layer (Multi-Tenant MongoDB)          │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                    Data Stores                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ MongoDB  │  │  Redis   │  │  Qdrant  │  │ Ollama   │  │
│  │ (Primary)│  │ (Cache)  │  │ (Vector) │  │  (LLM)   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Key Technologies

- **FastAPI**: High-performance async web framework with automatic OpenAPI documentation
- **Motor**: Async MongoDB driver for data persistence
- **Redis**: Caching and session management
- **Qdrant**: Vector database for semantic search and RAG (Retrieval-Augmented Generation)
- **LangGraph**: Conversational AI workflows with LLM integration
- **WebRTC**: Real-time peer-to-peer communication for clubs
- **Pydantic**: Data validation and settings management
- **uvicorn**: ASGI server for production deployments

## Package Structure

### Core Modules

- **`main`**: Application entry point, lifespan management, and route aggregation
- **`config`**: Pydantic-based configuration management with environment variable support
- **`database`**: MongoDB connection management, indexing, and multi-tenancy support
- **`websocket_manager`**: WebSocket connection lifecycle for real-time messaging

### Feature Modules

**Authentication & Security** (`routes/auth/`, `services/`)
- JWT-based authentication with refresh tokens
- Two-factor authentication (2FA/TOTP)
- Permanent API tokens for integrations
- Rate limiting and abuse detection
- Session management and trusted device tracking

**Family Management** (`routes/family/`, `models/family_models.py`)
- Family creation and membership management
- Bidirectional relationship tracking
- Shared virtual SBD token accounts
- Invitation and notification systems
- Admin action audit trails

**IPAM (IP Address Management)** (`routes/ipam/`, `services/ipam_service.py`)
- Hierarchical IP allocation (Continent → Country → Region → Host)
- Capacity monitoring and forecasting
- Reservation and sharing systems
- Webhook integrations and bulk operations
- CSV import/export for migration

**Digital Shop** (`routes/shop/`, `models/shop_models.py`)
- Avatar, banner, and theme marketplace
- Purchase and rental management
- Inventory tracking with featured items

**Chat & RAG** (`chat/`, `rag/`)
- LangGraph-based conversational AI workflows
- Semantic search with vector embeddings
- Hybrid search (keyword + semantic)
- Conversation history and session management
- Token usage tracking and analytics

**MemEx (Spaced Repetition)** (`routes/anki/`, `models/memex_models.py`)
- Anki-compatible spaced repetition system
- SuperMemo-2 algorithm implementation
- Deck and card management with scheduling

**Blog Platform** (`routes/blog/`, `models/blog_models.py`)
- Multi-author blog management
- SEO optimization and sitemap generation
- Draft auto-save and version history
- Analytics and newsletter integration

**University Clubs** (`routes/clubs/`, `routers/club_webrtc_router.py`)
- Club creation and membership management
- Event scheduling and RSVP tracking
- WebRTC-based real-time communication

**Workspaces & Documents** (`routes/workspaces/`, `routes/documents/`)
- Collaborative workspace management
- Document storage with OCR and table extraction (Docling)
- Vector search for document retrieval

### Infrastructure & Support

**Multi-Tenancy** (`middleware/tenant_context.py`, `database/tenant_collection.py`)
- Strict tenant isolation with automatic filtering
- Per-tenant quotas and limits
- RBAC (Role-Based Access Control)

**Distributed Cluster** (`managers/cluster_manager.py`, `services/replication_service.py`)
- Master-slave replication
- Automatic failover and leader election
- Data migration with bandwidth control
- Split-brain detection

**MCP (Model Context Protocol)** (`integrations/mcp/`)
- FastMCP server for LLM tool integration
- HTTP and stdio transport support
- Authentication and rate limiting
- Tool registration for family, auth, shop, and workspace management

**Monitoring & Observability** (`utils/logging_utils.py`, `managers/logging_manager.py`)
- Structured logging with Loki integration
- Prometheus metrics instrumentation
- Performance tracking and audit trails

## Configuration

Configuration is managed via environment variables, `.env`, or `.sbd` files. See `config.py`
for the full list of settings. Key configuration groups include:

- **Server**: `HOST`, `PORT`, `DEBUG`
- **Database**: `MONGODB_URL`, `MONGODB_DATABASE`
- **Security**: `SECRET_KEY`, `FERNET_KEY`, `TURNSTILE_SECRET`
- **Features**: `MCP_ENABLED`, `CHAT_ENABLED`, `CLUSTER_ENABLED`

## Getting Started

From the project root:

```bash
# Install dependencies using uv
uv sync --extra dev

# Run the application (development mode with hot-reload)
uv run uvicorn src.second_brain_database.main:app --reload

# Run with production settings
uvicorn src.second_brain_database.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

When running the application, interactive API documentation is available at:

- **Swagger UI**: `http://localhost:8000/docs` - Interactive API testing
- **ReDoc**: `http://localhost:8000/redoc` - Clean, organized reference
- **OpenAPI Schema**: `http://localhost:8000/openapi.json` - Raw schema for tooling

## Usage Examples

### Accessing Configuration

```python
from second_brain_database.config import settings

# Access configuration
mongodb_url = settings.MONGODB_URL
is_prod = settings.is_production

# Check feature flags
if settings.CLUSTER_ENABLED:
    print("Running in cluster mode")
```

### Database Operations

```python
from second_brain_database.database import db_manager

# Get a regular collection
users = db_manager.get_collection("users")
user = await users.find_one({"username": "john_doe"})

# Get a tenant-aware collection (automatic tenant filtering)
users = db_manager.get_tenant_collection("users", tenant_id="tenant_123")
# All queries on this collection are automatically filtered by tenant_id
```

### WebSocket Communication

```python
from second_brain_database.websocket_manager import manager

# Send a message to all user devices
await manager.send_personal_message(
    message=json.dumps({"type": "notification", "text": "Hello!"}),
    user_id="user123"
)

# Broadcast to multiple users
await manager.broadcast_to_users(
    message=json.dumps({"event": "system_announcement"}),
    user_ids=["user1", "user2", "user3"]
)
```

## Module-Level Attributes

Attributes:
    __version__ (str): Package version following semantic versioning. Default: `"1.0.0"`.
    
    __author__ (str): Package author name. Default: `"Rohan Batrain"`.
    
    __email__ (str): Contact email for the package maintainer. Default: `"contact@rohanbatrain.com"`.
    
    __description__ (str): Brief package description for metadata. Default:
        `"A FastAPI application for second brain database management"`.
    
    settings (Settings): Re-exported global configuration singleton from `config.py`.
        This is the **primary interface** for accessing configuration:
        
        ```python
        from second_brain_database import settings
        
        # Access any setting
        db_url = settings.MONGODB_URL
        is_production = settings.is_production
        ```

## License

This project is licensed under the terms specified in the repository.

## Related Documentation

See Also:
    - **Project README**: `/README.md` - Project overview and setup instructions
    - **Deployment Guide**: `/docs/deployment.md` - Production deployment instructions
    - **API Examples**: `/docs/api_examples.md` - Sample API usage scenarios
    - **Configuration Reference**: `src/second_brain_database/config.py` - Complete settings documentation
    - **Main Module**: `src/second_brain_database/main.py` - Application entry point documentation
"""

__version__ = "1.0.0"
__author__ = "Rohan Batrain"
__email__ = "contact@rohanbatrain.com"

# Re-export commonly used objects for convenience
from second_brain_database.config import settings
__description__ = "A FastAPI application for second brain database management"
