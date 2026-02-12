#!/bin/bash
# Production Deployment Script for Into the Repo
# This script helps deploy the application to production

set -e

echo "Into the Repo - Production Deployment"
echo "======================================"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please copy .env.sample to .env and fill in the values."
    exit 1
fi

# Validate required environment variables
required_vars=("DATABASE_URL" "REDIS_URL" "SECRET_KEY" "GITHUB_TOKEN" "GEMINI_API_KEY")
for var in "${required_vars[@]}"; do
    if ! grep -q "^$var=" .env; then
        echo "Error: $var not set in .env file"
        exit 1
    fi
done

echo "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed"
    exit 1
fi

echo "✓ Docker and docker-compose are installed"
echo ""

# Build images
echo "Building Docker images..."
docker-compose build --no-cache

echo "✓ Images built successfully"
echo ""

# Stop existing services
echo "Stopping existing services (if any)..."
docker-compose down --remove-orphans 2>/dev/null || true

echo "✓ Old services stopped"
echo ""

# Start services
echo "Starting services..."
docker-compose up -d

echo "✓ Services started"
echo ""

# Wait for services to be ready
echo "Waiting for services to become healthy..."
sleep 15

# Health check
echo "Running health checks..."
echo ""

checks_passed=0
checks_total=4

if curl -s -f http://localhost:8000/docs > /dev/null 2>&1; then
    echo "✓ Backend API: OK"
    ((checks_passed++))
else
    echo "✗ Backend API: FAILED"
fi

if curl -s -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✓ Frontend: OK"
    ((checks_passed++))
else
    echo "✗ Frontend: FAILED"
fi

if redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis: OK"
    ((checks_passed++))
else
    echo "✗ Redis: FAILED"
fi

if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "✓ PostgreSQL: OK"
    ((checks_passed++))
else
    echo "✗ PostgreSQL: FAILED"
fi

echo ""
echo "Health checks: $checks_passed/$checks_total passed"
echo ""

if [ $checks_passed -eq $checks_total ]; then
    echo "======================================"
    echo "Deployment Successful!"
    echo "======================================"
    echo ""
    echo "Services running:"
    echo "  Backend API: http://localhost:8000"
    echo "  API Docs: http://localhost:8000/docs"
    echo "  Frontend: http://localhost:3000"
    echo ""
    echo "View logs:"
    echo "  make logs (all services)"
    echo "  make logs-backend (backend only)"
    echo "  make logs-worker (celery worker)"
    echo "  make logs-frontend (frontend)"
    echo ""
    exit 0
else
    echo "======================================"
    echo "Deployment Failed!"
    echo "======================================"
    echo ""
    echo "Some services failed health checks."
    echo "View logs with: docker-compose logs"
    echo ""
    exit 1
fi
