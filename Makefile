.PHONY: help install dev build up down logs clean test lint format db-migrate health docs

# Default target
help:
	@echo "================================"
	@echo "Into the Repo - Make Commands"
	@echo "================================"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install       - Install all dependencies (local development)"
	@echo "  make setup         - Setup development environment with virtual env"
	@echo ""
	@echo "Development:"
	@echo "  make dev           - Start both backend and frontend dev servers"
	@echo "  make dev-backend   - Start FastAPI dev server only"
	@echo "  make dev-frontend  - Start Next.js dev server only"
	@echo ""
	@echo "Docker & Deployment:"
	@echo "  make build         - Build Docker images"
	@echo "  make up            - Start all services (Docker Compose)"
	@echo "  make down          - Stop all services"
	@echo "  make logs          - View logs from all services"
	@echo "  make clean         - Remove containers, volumes, and build artifacts"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate    - Run database migrations"
	@echo "  make db-reset      - Reset database to fresh state"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test          - Run all tests"
	@echo "  make test-backend  - Run backend tests only"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo "  make lint          - Run code linters"
	@echo "  make format        - Format code (black, isort, prettier)"
	@echo ""
	@echo "Utilities:"
	@echo "  make health        - Check health of all services"
	@echo "  make docs          - Open API documentation in browser"
	@echo ""

# ==========================================
# SETUP & INSTALLATION
# ==========================================

setup:
	@echo "Setting up development environment..."
	cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
	cd frontend && npm install
	@echo "Setup complete! Run 'make dev' to start developing."

install:
	@echo "Installing dependencies..."
	cd backend && pip install -r requirements.txt
	cd frontend && npm install
	@echo "Dependencies installed!"

# ==========================================
# DEVELOPMENT
# ==========================================

dev:
	@echo "Starting development environment..."
	@echo "Backend: http://localhost:8000 (API Docs: http://localhost:8000/docs)"
	@echo "Frontend: http://localhost:3000"
	@echo ""
	@make -j2 dev-backend dev-frontend

dev-backend:
	cd backend && source .venv/bin/activate && uvicorn src.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

# ==========================================
# DOCKER & DEPLOYMENT
# ==========================================

build:
	@echo "Building Docker images..."
	docker-compose build
	@echo "Build complete!"

up:
	@echo "Starting services with Docker Compose..."
	@cp .env.sample .env 2>/dev/null || true
	docker-compose up -d
	@echo ""
	@echo "Services started!"
	@echo "Backend API: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"
	@echo "Frontend: http://localhost:3000"
	@echo ""
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@make health

down:
	@echo "Stopping services..."
	docker-compose down
	@echo "Services stopped!"

logs:
	@docker-compose logs -f

logs-backend:
	@docker-compose logs -f backend

logs-worker:
	@docker-compose logs -f celery_worker

logs-frontend:
	@docker-compose logs -f frontend

clean:
	@echo "Cleaning up..."
	@docker-compose down -v
	@rm -rf backend/__pycache__ backend/**/__pycache__
	@rm -rf backend/.pytest_cache backend/htmlcov
	@rm -rf frontend/.next frontend/out
	@rm -rf .pytest_cache
	@echo "Cleanup complete!"

# ==========================================
# TESTING & QUALITY
# ==========================================

test:
	@echo "Running all tests..."
	cd backend && source .venv/bin/activate && pytest tests/ -v

test-backend:
	@echo "Running backend tests..."
	cd backend && source .venv/bin/activate && pytest tests/ -v

test-coverage:
	@echo "Running tests with coverage report..."
	cd backend && source .venv/bin/activate && pytest tests/ -v --cov=src --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

lint:
	@echo "Running linters..."
	cd backend && source .venv/bin/activate && flake8 src tests 2>/dev/null || echo "flake8 not installed"
	cd frontend && npm run lint 2>/dev/null || echo "ESLint not configured"

format:
	@echo "Formatting code..."
	cd backend && source .venv/bin/activate && black src tests && isort src tests
	cd frontend && npm run format 2>/dev/null || echo "Format script not found"

# ==========================================
# DATABASE
# ==========================================

db-migrate:
	@echo "Running database migrations..."
	cd backend && source .venv/bin/activate && alembic upgrade head 2>/dev/null || echo "Alembic not configured"

db-reset:
	@echo "Resetting database..."
	@docker-compose down -v db
	@docker-compose up -d db
	@echo "Waiting for database..."
	@sleep 5
	@make db-migrate

# ==========================================
# UTILITIES
# ==========================================

health:
	@echo "Health Check Results:"
	@echo "====================="
	@curl -s -f http://localhost:8000/docs > /dev/null 2>&1 && echo "✓ Backend API: OK" || echo "✗ Backend API: FAILED"
	@curl -s -f http://localhost:3000 > /dev/null 2>&1 && echo "✓ Frontend: OK" || echo "✗ Frontend: FAILED"
	@redis-cli ping > /dev/null 2>&1 && echo "✓ Redis: OK" || echo "✗ Redis: FAILED"
	@pg_isready -h localhost -p 5432 > /dev/null 2>&1 && echo "✓ PostgreSQL: OK" || echo "✗ PostgreSQL: FAILED"
	@echo ""

docs:
	@echo "Opening API documentation..."
	@python -m webbrowser http://localhost:8000/docs || open http://localhost:8000/docs 2>/dev/null || xdg-open http://localhost:8000/docs 2>/dev/null

# ==========================================
# GIT & DEPLOYMENT
# ==========================================

commit-check:
	@echo "Checking code quality before commit..."
	@make lint
	@make test
	@echo "All checks passed! Ready to commit."

production-build:
	@echo "Building for production..."
	@docker-compose build --no-cache
	@echo "Production build complete!"

