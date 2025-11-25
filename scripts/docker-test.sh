#!/bin/bash
set -e

# ============================================================================
# Docker Test Script for Second Brain Database
# ============================================================================
# This script builds, starts, tests, and tears down the Docker environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INFRA_DIR="$PROJECT_ROOT/infra"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILES="-f $INFRA_DIR/docker-compose.yml -f $INFRA_DIR/docker-compose.test.yml"
ENV_FILE="$PROJECT_ROOT/.env.test"
MAX_WAIT=120  # Maximum seconds to wait for services

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cleanup() {
    log_info "Cleaning up Docker resources..."
    cd "$INFRA_DIR"
    docker-compose $COMPOSE_FILES down -v --remove-orphans 2>/dev/null || true
}

wait_for_health() {
    local service=$1
    local max_wait=$2
    local elapsed=0
    
    log_info "Waiting for $service to be healthy..."
    
    while [ $elapsed -lt $max_wait ]; do
        if docker-compose $COMPOSE_FILES ps | grep "$service" | grep -q "healthy"; then
            log_info "$service is healthy!"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
        echo -n "."
    done
    
    echo ""
    log_error "$service failed to become healthy within ${max_wait}s"
    return 1
}

# ============================================================================
# Main Test Flow
# ============================================================================

main() {
    log_info "Starting Docker integration tests..."
    
    # Trap cleanup on exit
    trap cleanup EXIT INT TERM
    
    # Step 1: Check prerequisites
    log_info "Checking prerequisites..."
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Step 2: Create test environment file if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        log_warn ".env.test not found, copying from example..."
        cp "$PROJECT_ROOT/.env.test.example" "$ENV_FILE"
    fi
    
    # Step 3: Build Docker images
    log_info "Building Docker images..."
    cd "$INFRA_DIR"
    docker-compose $COMPOSE_FILES build --no-cache
    
    if [ $? -ne 0 ]; then
        log_error "Docker build failed"
        exit 1
    fi
    
    # Step 4: Start services
    log_info "Starting Docker services..."
    docker-compose $COMPOSE_FILES up -d
    
    if [ $? -ne 0 ]; then
        log_error "Failed to start Docker services"
        exit 1
    fi
    
    # Step 5: Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    
    wait_for_health "mongo" $MAX_WAIT || exit 1
    wait_for_health "redis" $MAX_WAIT || exit 1
    wait_for_health "qdrant" $MAX_WAIT || exit 1
    wait_for_health "api" $MAX_WAIT || exit 1
    
    # Step 6: Show service status
    log_info "Service status:"
    docker-compose $COMPOSE_FILES ps
    
    # Step 7: Run integration tests
    log_info "Running integration tests..."
    cd "$PROJECT_ROOT"
    
    # Run Docker-specific integration tests
    if [ -f "tests/test_docker_services.py" ]; then
        uv run pytest tests/test_docker_services.py -v --tb=short
        TEST_RESULT=$?
    else
        log_warn "Docker integration tests not found, skipping..."
        TEST_RESULT=0
    fi
    
    # Step 8: Show logs if tests failed
    if [ $TEST_RESULT -ne 0 ]; then
        log_error "Tests failed! Showing service logs..."
        cd "$INFRA_DIR"
        docker-compose $COMPOSE_FILES logs --tail=50
        exit $TEST_RESULT
    fi
    
    # Step 9: Success!
    log_info "All tests passed successfully!"
    
    # Step 10: Cleanup (handled by trap)
    return 0
}

# Run main function
main "$@"
