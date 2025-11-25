# Docker Guide for Second Brain Database

This guide provides comprehensive instructions for building, running, and testing the Second Brain Database using Docker and Docker Compose.

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Services Overview](#services-overview)
- [Environment Configuration](#environment-configuration)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Development Environment

```bash
# 1. Copy environment file
cp .env.development.example .env

# 2. Start all services
cd infra
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 3. View logs
docker-compose logs -f api

# 4. Access the application
open http://localhost:8000/docs
```

### Testing

```bash
# Run automated Docker tests
bash scripts/docker-test.sh
```

### Production

```bash
# 1. Configure production environment
cp .env.production.example .env
# Edit .env with production secrets

# 2. Build and start services
cd infra
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Prerequisites

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Git**: For cloning the repository
- **uv**: For local development (optional)

### Installing Docker

**macOS:**
```bash
brew install --cask docker
```

**Linux:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

## Services Overview

The Docker Compose stack includes the following services:

### Core Services

| Service | Description | Port | Health Check |
|---------|-------------|------|--------------|
| **api** | FastAPI application | 8000 | `/health` |
| **mongo** | MongoDB database | 27017 | `mongosh ping` |
| **redis** | Cache and session store | 6379 | `redis-cli ping` |
| **qdrant** | Vector database for RAG | 6333 | `/healthz` |
| **celery-worker** | Async task processor | - | Celery inspect |
| **celery-beat** | Periodic task scheduler | - | - |

### Optional Services

| Service | Description | Port | Profile |
|---------|-------------|------|---------|
| **ollama** | Local LLM inference | 11434 | `ollama`, `full` |
| **docs** | MkDocs documentation | 8080 | `docs`, `full` |

### Service Dependencies

```mermaid
graph TD
    A[API] --> B[MongoDB]
    A --> C[Redis]
    A --> D[Qdrant]
    E[Celery Worker] --> B
    E --> C
    E --> D
    F[Celery Beat] --> B
    F --> C
    A -.optional.-> G[Ollama]
```

## Environment Configuration

### Environment Files

The project supports three environment configurations:

1. **Development** (`.env.development.example`)
   - Debug mode enabled
   - Hot-reloading
   - All ports exposed
   - Relaxed resource limits

2. **Test** (`.env.test.example`)
   - Minimal configuration
   - In-memory databases
   - Fast startup
   - Isolated network

3. **Production** (`.env.production.example`)
   - Security hardened
   - Resource limits enforced
   - Logging configured
   - Secrets required

### Creating Your Environment File

```bash
# For development
cp .env.development.example .env

# For testing
cp .env.test.example .env.test

# For production
cp .env.production.example .env.production
```

### Key Environment Variables

#### Database Configuration

```bash
# MongoDB
MONGODB_USERNAME=admin
MONGODB_PASSWORD=your_password
MONGODB_DATABASE=second_brain_database
MONGODB_URL=mongodb://admin:password@mongo:27017/second_brain_database?authSource=admin

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_API_KEY=your_api_key
```

#### Security

```bash
# Generate JWT secret
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Generate Fernet key
ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

## Development Workflow

### Starting Services

```bash
cd infra

# Start all services in development mode
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Start specific services
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d api mongo redis

# Start with Ollama
docker-compose -f docker-compose.yml -f docker-compose.dev.yml --profile ollama up -d
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail=100 api
```

### Executing Commands

```bash
# Execute command in API container
docker-compose exec api bash

# Run Python shell
docker-compose exec api python

# Run database migrations
docker-compose exec api python -m alembic upgrade head
```

### Hot Reloading

In development mode, the source code is mounted as a volume, enabling hot-reloading:

```yaml
volumes:
  - ../src:/app/src:ro  # Read-only mount for security
```

Changes to Python files will automatically reload the application.

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v

# Stop specific service
docker-compose stop api
```

## Testing

### Automated Testing

Run the comprehensive test suite:

```bash
bash scripts/docker-test.sh
```

This script:
1. Builds Docker images
2. Starts all services
3. Waits for health checks
4. Runs integration tests
5. Cleans up resources

### Manual Testing

```bash
# Start test environment
cd infra
docker-compose -f docker-compose.yml -f docker-compose.test.yml up -d

# Run specific tests
uv run pytest tests/test_docker_services.py -v

# Run with coverage
uv run pytest tests/test_docker_services.py --cov=src --cov-report=html

# Cleanup
docker-compose -f docker-compose.yml -f docker-compose.test.yml down -v
```

### Service Health Checks

```bash
# Check all service status
docker-compose ps

# Check specific service health
docker inspect --format='{{.State.Health.Status}}' sbd-api

# View health check logs
docker inspect --format='{{json .State.Health}}' sbd-api | jq
```

## Production Deployment

### Pre-Deployment Checklist

- [ ] Update all secrets in `.env.production`
- [ ] Configure CORS origins
- [ ] Set up SSL/TLS certificates
- [ ] Configure backup strategy
- [ ] Set up monitoring and logging
- [ ] Review resource limits
- [ ] Test disaster recovery

### Building for Production

```bash
# Build production images
bash scripts/docker-build.sh --tag v1.0.0

# Build multi-platform images
bash scripts/docker-build.sh --multi-platform --push --tag v1.0.0
```

### Deploying

```bash
cd infra

# Pull latest images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml pull

# Start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify deployment
docker-compose ps
docker-compose logs --tail=50
```

### Scaling Services

```bash
# Scale Celery workers
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale celery-worker=4

# Or set in environment
export CELERY_WORKER_REPLICAS=4
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Monitoring

```bash
# View resource usage
docker stats

# View service logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Export logs
docker-compose logs --no-color > logs/docker-$(date +%Y%m%d).log
```

## Troubleshooting

### Common Issues

#### Services Not Starting

```bash
# Check service logs
docker-compose logs api

# Check Docker daemon
docker info

# Restart Docker daemon (macOS)
killall Docker && open /Applications/Docker.app
```

#### Port Already in Use

```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in .env
API_PORT=8001
```

#### Database Connection Issues

```bash
# Check MongoDB is running
docker-compose ps mongo

# Test MongoDB connection
docker-compose exec mongo mongosh -u admin -p password

# Check Redis connection
docker-compose exec redis redis-cli ping
```

#### Out of Memory

```bash
# Check container memory usage
docker stats

# Increase Docker memory limit (Docker Desktop)
# Settings > Resources > Memory

# Or reduce worker concurrency
CELERY_WORKER_CONCURRENCY=2
UVICORN_WORKERS=2
```

#### Build Failures

```bash
# Clear build cache
docker builder prune -a

# Rebuild without cache
docker-compose build --no-cache

# Check disk space
docker system df
```

### Health Check Failures

```bash
# View health check logs
docker inspect sbd-api | jq '.[0].State.Health'

# Manually test health endpoint
curl http://localhost:8000/health

# Increase health check timeout
# Edit docker-compose.yml:
healthcheck:
  start_period: 90s  # Increase from 60s
```

### Performance Issues

```bash
# Check resource limits
docker-compose config | grep -A 5 "resources:"

# Monitor container performance
docker stats --no-stream

# Check for memory leaks
docker-compose exec api python -c "import psutil; print(psutil.virtual_memory())"
```

### Cleaning Up

```bash
# Remove stopped containers
docker container prune

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Full cleanup (WARNING: removes everything)
docker system prune -a --volumes
```

## Advanced Topics

### Custom Networks

```bash
# Create external network
docker network create sbd-external

# Use in docker-compose.yml
networks:
  sbd-network:
    external: true
    name: sbd-external
```

### Volume Backups

```bash
# Backup MongoDB data
docker run --rm \
  -v sbd_mongo_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/mongo-$(date +%Y%m%d).tar.gz /data

# Restore MongoDB data
docker run --rm \
  -v sbd_mongo_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/mongo-20250125.tar.gz -C /
```

### Docker Compose Profiles

```bash
# Start with all optional services
docker-compose --profile full up -d

# Start with only Ollama
docker-compose --profile ollama up -d

# Start with docs
docker-compose --profile docs up -d
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Docker Guide](https://fastapi.tiangolo.com/deployment/docker/)
- [MongoDB Docker Guide](https://hub.docker.com/_/mongo)
- [Redis Docker Guide](https://hub.docker.com/_/redis)
- [Qdrant Docker Guide](https://qdrant.tech/documentation/guides/installation/)
