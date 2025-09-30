#!/bin/bash

# JobHire.AI Backend Deployment Script
# Production deployment with zero-downtime

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="jobhire-ai-backend"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-}"
VERSION="${VERSION:-latest}"
ENVIRONMENT="${ENVIRONMENT:-production}"

# Functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    command -v docker >/dev/null 2>&1 || error "Docker is not installed"
    command -v docker-compose >/dev/null 2>&1 || error "Docker Compose is not installed"
    
    if [ ! -f ".env" ]; then
        error ".env file not found. Please create one from .env.example"
    fi
    
    success "Prerequisites check passed"
}

# Build and tag Docker images
build_images() {
    log "Building Docker images..."
    
    # Build main application image
    docker build -t ${APP_NAME}:${VERSION} .
    
    if [ -n "$DOCKER_REGISTRY" ]; then
        docker tag ${APP_NAME}:${VERSION} ${DOCKER_REGISTRY}/${APP_NAME}:${VERSION}
        log "Tagged image for registry: ${DOCKER_REGISTRY}/${APP_NAME}:${VERSION}"
    fi
    
    success "Docker images built successfully"
}

# Push images to registry
push_images() {
    if [ -n "$DOCKER_REGISTRY" ]; then
        log "Pushing images to registry..."
        docker push ${DOCKER_REGISTRY}/${APP_NAME}:${VERSION}
        success "Images pushed to registry"
    else
        warn "No Docker registry configured, skipping push"
    fi
}

# Run database migrations
run_migrations() {
    log "Running database migrations..."
    
    # Ensure database is running
    docker-compose up -d postgres
    
    # Wait for database to be ready
    log "Waiting for database to be ready..."
    sleep 10
    
    # Run migrations
    docker-compose run --rm api alembic upgrade head
    
    success "Database migrations completed"
}

# Health check
health_check() {
    local max_attempts=30
    local attempt=1
    
    log "Performing health check..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/health >/dev/null 2>&1; then
            success "Health check passed"
            return 0
        fi
        
        log "Health check attempt $attempt/$max_attempts failed, retrying in 10s..."
        sleep 10
        attempt=$((attempt + 1))
    done
    
    error "Health check failed after $max_attempts attempts"
}

# Backup database
backup_database() {
    if [ "$ENVIRONMENT" = "production" ]; then
        log "Creating database backup..."
        
        local backup_file="backup_$(date +%Y%m%d_%H%M%S).sql"
        
        docker-compose exec -T postgres pg_dump -U jobhire jobhire_ai > "backups/$backup_file"
        
        # Keep only last 10 backups
        ls -t backups/backup_*.sql | tail -n +11 | xargs -r rm
        
        success "Database backup created: $backup_file"
    fi
}

# Deploy with zero downtime
deploy() {
    log "Starting deployment..."
    
    # Create backup directory
    mkdir -p backups
    mkdir -p logs
    
    # Backup database in production
    backup_database
    
    # Build new images
    build_images
    
    # Push to registry if configured
    push_images
    
    # Run migrations
    run_migrations
    
    # Start new services
    log "Starting services..."
    docker-compose up -d
    
    # Wait for services to be ready
    sleep 20
    
    # Health check
    health_check
    
    success "Deployment completed successfully!"
}

# Rollback to previous version
rollback() {
    warn "Starting rollback..."
    
    # Stop current services
    docker-compose down
    
    # Restore from backup (if available)
    local latest_backup=$(ls -t backups/backup_*.sql 2>/dev/null | head -n1)
    if [ -n "$latest_backup" ]; then
        log "Restoring database from backup: $latest_backup"
        docker-compose up -d postgres
        sleep 10
        docker-compose exec -T postgres psql -U jobhire -d jobhire_ai < "$latest_backup"
    fi
    
    # Start services with previous version
    docker-compose up -d
    
    success "Rollback completed"
}

# Clean up old images and containers
cleanup() {
    log "Cleaning up old Docker resources..."
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused volumes
    docker volume prune -f
    
    # Remove unused networks
    docker network prune -f
    
    success "Cleanup completed"
}

# Show logs
show_logs() {
    docker-compose logs -f --tail=100
}

# Show status
show_status() {
    echo ""
    log "Service Status:"
    docker-compose ps
    
    echo ""
    log "Resource Usage:"
    docker stats --no-stream
}

# Main script
case "${1:-deploy}" in
    "deploy")
        check_prerequisites
        deploy
        ;;
    "rollback")
        rollback
        ;;
    "build")
        build_images
        ;;
    "push")
        push_images
        ;;
    "migrate")
        run_migrations
        ;;
    "health")
        health_check
        ;;
    "logs")
        show_logs
        ;;
    "status")
        show_status
        ;;
    "cleanup")
        cleanup
        ;;
    "stop")
        log "Stopping services..."
        docker-compose down
        success "Services stopped"
        ;;
    "restart")
        log "Restarting services..."
        docker-compose restart
        success "Services restarted"
        ;;
    *)
        echo "Usage: $0 {deploy|rollback|build|push|migrate|health|logs|status|cleanup|stop|restart}"
        echo ""
        echo "Commands:"
        echo "  deploy   - Full deployment (default)"
        echo "  rollback - Rollback to previous version"
        echo "  build    - Build Docker images only"
        echo "  push     - Push images to registry"
        echo "  migrate  - Run database migrations only"
        echo "  health   - Run health check"
        echo "  logs     - Show service logs"
        echo "  status   - Show service status"
        echo "  cleanup  - Clean up old Docker resources"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo ""
        echo "Environment variables:"
        echo "  VERSION         - Docker image version (default: latest)"
        echo "  DOCKER_REGISTRY - Docker registry URL"
        echo "  ENVIRONMENT     - Deployment environment (default: production)"
        exit 1
        ;;
esac