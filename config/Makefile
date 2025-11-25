# Makefile for Second Brain Database development tasks

.PHONY: help lint lint-fix format check test install-dev clean docker-build docker-up docker-down docker-test docker-logs docker-clean

# Default target
help:
	@echo "Available commands:"
	@echo "  lint          - Run all linting tools (check only)"
	@echo "  lint-fix      - Run linting tools with auto-fix where possible"
	@echo "  format        - Format code with black and isort"
	@echo "  check         - Run type checking with mypy"
	@echo "  pylint        - Run pylint code quality checks"
	@echo "  test          - Run tests with pytest"
	@echo "  install-dev   - Install development dependencies with uv"
	@echo "  setup-dev     - Complete development environment setup"
	@echo "  validate-dev  - Validate development environment"
	@echo "  pre-commit    - Install pre-commit hooks"
	@echo "  clean         - Clean up temporary files"
	@echo ""
	@echo "Docker commands:"
	@echo "  docker-build  - Build Docker images"
	@echo "  docker-up     - Start all Docker services (development)"
	@echo "  docker-down   - Stop all Docker services"
	@echo "  docker-test   - Run Docker integration tests"
	@echo "  docker-logs   - View Docker service logs"
	@echo "  docker-clean  - Clean up Docker resources"
	@echo "  docker-prod   - Start Docker services (production)"

# Linting commands
lint:
	@echo "🔍 Running all linting tools..."
	python scripts/lint.py

lint-fix:
	@echo "🔧 Running linting tools with auto-fix..."
	python scripts/lint.py --fix

format:
	@echo "🎨 Formatting code..."
	python scripts/lint.py --tool black --fix
	python scripts/lint.py --tool isort --fix

check:
	@echo "🔍 Running type checks..."
	python scripts/lint.py --tool mypy

pylint:
	@echo "🔍 Running pylint..."
	python scripts/lint.py --tool pylint

# Testing
test:
	@echo "🧪 Running tests..."
	python -m pytest

test-cov:
	@echo "🧪 Running tests with coverage..."
	python -m pytest --cov=src --cov-report=html --cov-report=term

# Development setup
install-dev:
	@echo "📦 Installing development dependencies..."
	uv sync --extra dev

setup-dev:
	@echo "🚀 Setting up development environment..."
	uv run python scripts/setup_dev_environment.py

validate-dev:
	@echo "✅ Validating development environment..."
	uv run python scripts/validate_dev_environment.py

pre-commit:
	@echo "🪝 Installing pre-commit hooks..."
	pre-commit install

# Cleanup
clean:
	@echo "🧹 Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .coverage

# Quick development workflow
dev-setup: setup-dev pre-commit
	@echo "✅ Development environment setup complete!"

# CI/CD commands
ci-lint:
	@echo "🤖 Running CI linting checks..."
	python scripts/lint.py --skip mypy

ci-test:
	@echo "🤖 Running CI tests..."
	python -m pytest --cov=src --cov-report=xml

# File-specific linting
lint-file:
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make lint-file FILE=path/to/file.py"; \
	else \
		echo "🔍 Linting $(FILE)..."; \
		python scripts/lint.py $(FILE); \
	fi

# Directory-specific linting
lint-dir:
	@if [ -z "$(DIR)" ]; then \
		echo "Usage: make lint-dir DIR=path/to/directory"; \
	else \
		echo "🔍 Linting $(DIR)..."; \
		python scripts/lint.py $(DIR); \
	fi

# ============================================================================
# DOCKER COMMANDS
# ============================================================================

# Build Docker images
docker-build:
	@echo "🐳 Building Docker images..."
	bash scripts/docker-build.sh

docker-build-no-cache:
	@echo "🐳 Building Docker images (no cache)..."
	bash scripts/docker-build.sh --no-cache

# Start Docker services
docker-up:
	@echo "🐳 Starting Docker services (development)..."
	cd infra && docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
	@echo "✅ Services started! API: http://localhost:8000/docs"

docker-up-build:
	@echo "🐳 Building and starting Docker services..."
	cd infra && docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# Start with optional services
docker-up-full:
	@echo "🐳 Starting all Docker services (including Ollama)..."
	cd infra && docker-compose -f docker-compose.yml -f docker-compose.dev.yml --profile full up -d

# Production
docker-prod:
	@echo "🐳 Starting Docker services (production)..."
	cd infra && docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Stop Docker services
docker-down:
	@echo "🐳 Stopping Docker services..."
	cd infra && docker-compose down

docker-down-volumes:
	@echo "🐳 Stopping Docker services and removing volumes..."
	cd infra && docker-compose down -v

# View logs
docker-logs:
	@echo "🐳 Viewing Docker logs..."
	cd infra && docker-compose logs -f

docker-logs-api:
	@echo "🐳 Viewing API logs..."
	cd infra && docker-compose logs -f api

docker-logs-celery:
	@echo "🐳 Viewing Celery worker logs..."
	cd infra && docker-compose logs -f celery-worker

# Testing
docker-test:
	@echo "🐳 Running Docker integration tests..."
	bash scripts/docker-test.sh

# Service status
docker-ps:
	@echo "🐳 Docker service status..."
	cd infra && docker-compose ps

docker-stats:
	@echo "🐳 Docker resource usage..."
	docker stats --no-stream

# Cleanup
docker-clean:
	@echo "🐳 Cleaning up Docker resources..."
	cd infra && docker-compose down -v --remove-orphans
	docker system prune -f

docker-clean-all:
	@echo "🐳 Cleaning up all Docker resources (WARNING: removes everything)..."
	cd infra && docker-compose down -v --remove-orphans
	docker system prune -a -f --volumes

# Execute commands in containers
docker-shell:
	@echo "🐳 Opening shell in API container..."
	cd infra && docker-compose exec api bash

docker-python:
	@echo "🐳 Opening Python shell in API container..."
	cd infra && docker-compose exec api python

# Database access
docker-mongo:
	@echo "🐳 Connecting to MongoDB..."
	cd infra && docker-compose exec mongo mongosh -u admin -p devpassword

docker-redis:
	@echo "🐳 Connecting to Redis..."
	cd infra && docker-compose exec redis redis-cli

# Restart services
docker-restart:
	@echo "🐳 Restarting Docker services..."
	cd infra && docker-compose restart

docker-restart-api:
	@echo "🐳 Restarting API service..."
	cd infra && docker-compose restart api