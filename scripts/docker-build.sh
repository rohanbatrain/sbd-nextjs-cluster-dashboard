#!/bin/bash
set -e

# ============================================================================
# Docker Build Script for Second Brain Database
# ============================================================================
# This script builds Docker images with proper tagging and caching

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INFRA_DIR="$PROJECT_ROOT/infra"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
IMAGE_NAME="${IMAGE_NAME:-second-brain-database}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Parse arguments
MULTI_PLATFORM=false
NO_CACHE=false
PUSH=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --multi-platform)
            MULTI_PLATFORM=true
            shift
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --push)
            PUSH=true
            shift
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--multi-platform] [--no-cache] [--push] [--tag TAG]"
            exit 1
            ;;
    esac
done

log_info "Building Docker image: $IMAGE_NAME:$IMAGE_TAG"
log_info "Build date: $BUILD_DATE"
log_info "VCS ref: $VCS_REF"

cd "$INFRA_DIR"

# Build arguments
BUILD_ARGS=(
    --build-arg "BUILD_DATE=$BUILD_DATE"
    --build-arg "VCS_REF=$VCS_REF"
    -t "$IMAGE_NAME:$IMAGE_TAG"
    -t "$IMAGE_NAME:latest"
    -f Dockerfile
    ..
)

# Add no-cache if requested
if [ "$NO_CACHE" = true ]; then
    BUILD_ARGS+=(--no-cache)
fi

# Build based on platform requirements
if [ "$MULTI_PLATFORM" = true ]; then
    log_info "Building multi-platform image for: $PLATFORMS"
    
    if [ "$PUSH" = true ]; then
        docker buildx build \
            --platform "$PLATFORMS" \
            --push \
            "${BUILD_ARGS[@]}"
    else
        log_warn "Multi-platform build requires --push flag to work properly"
        docker buildx build \
            --platform "$PLATFORMS" \
            "${BUILD_ARGS[@]}"
    fi
else
    log_info "Building single-platform image"
    docker build "${BUILD_ARGS[@]}"
    
    if [ "$PUSH" = true ]; then
        log_info "Pushing image to registry..."
        docker push "$IMAGE_NAME:$IMAGE_TAG"
        docker push "$IMAGE_NAME:latest"
    fi
fi

log_info "Build complete!"
log_info "Image: $IMAGE_NAME:$IMAGE_TAG"

# Show image size
docker images "$IMAGE_NAME:$IMAGE_TAG" --format "Size: {{.Size}}"
