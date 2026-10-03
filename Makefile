.PHONY: help install dev test test-unit test-e2e test-cov test-watch lint format clean docker-up docker-down docker-logs db-migrate db-seed run-local load-test security-scan docs

help:
	@echo "Diomika Backend - Development Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install              - Install dependencies and setup environment"
	@echo "  make dev                  - Start development environment (docker-compose)"
	@echo ""
	@echo "Testing:"
	@echo "  make test                 - Run all tests"
	@echo "  make test-unit            - Run unit tests only"
	@echo "  make test-e2e             - Run end-to-end tests"
	@echo "  make test-cov             - Run tests with coverage report"
	@echo "  make test-watch           - Run tests in watch mode"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint                 - Run all linters (flake8, mypy, pylint)"
	@echo "  make format               - Format code (black, isort)"
	@echo "  make format-check         - Check code formatting without changes"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate           - Run pending migrations"
	@echo "  make db-seed              - Seed database with test data"
	@echo "  make db-reset             - Reset database (⚠️  data loss)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up            - Start all services (docker-compose)"
	@echo "  make docker-down          - Stop all services"
	@echo "  make docker-logs          - View service logs"
	@echo ""
	@echo "Local Development:"
	@echo "  make run-local            - Run backend without docker"
	@echo "  make load-test            - Run load test baseline"
	@echo "  make security-scan        - Run security scanning tools"
	@echo ""
	@echo "Documentation:"
	@echo "  make docs                 - Generate documentation"
	@echo "  make docs-serve           - Serve documentation locally"
	@echo ""

# Installation & Setup
install:
	pip install --upgrade pip
	pip install -r requirements-dev.txt
	pre-commit install
	mkdir -p .venv

dev: docker-up
	@echo "✅ Development environment ready at http://localhost:8000"
	@echo "   Database UI available at http://localhost:8080"
	@echo "   Adminer creds: System=PostgreSQL, Server=postgres, User=diomika_dev, Password=diomika_dev_password"

docker-up:
	docker-compose up -d
	@echo "⏳ Waiting for services to be healthy..."
	@sleep 5
	@docker-compose ps

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-clean:
	docker-compose down -v
	docker volume prune -f

# Database Management
db-migrate:
	@echo "Running database migrations..."
	docker-compose exec -T postgres psql -U diomika_dev -d diomika_dev -f /docker-entrypoint-initdb.d/001_audit_archive_table.sql
	docker-compose exec -T postgres psql -U diomika_dev -d diomika_dev -f /docker-entrypoint-initdb.d/002_orders_invoice_columns.sql
	@echo "✅ Migrations completed"

db-reset:
	@echo "⚠️  This will reset all data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose exec postgres dropdb -U diomika_dev diomika_dev || true; \
		docker-compose exec postgres createdb -U diomika_dev diomika_dev; \
		$(MAKE) db-migrate; \
		echo "✅ Database reset"; \
	fi

db-seed:
	python scripts/seed_database.py

# Testing
test: test-unit test-e2e

test-unit:
	pytest tests/ -v -m "not slow and not e2e" --tb=short

test-e2e:
	pytest e2e/ -v --tb=short

test-cov:
	pytest tests/ \
		--cov=backend-api \
		--cov-report=html \
		--cov-report=term-missing \
		-m "not slow and not e2e"
	@echo "📊 Coverage report generated: htmlcov/index.html"

test-watch:
	ptw tests/ -- -v --tb=short

# Code Quality
lint:
	@echo "Running Flake8..."
	flake8 backend-api/ --count --select=E9,F63,F7,F82 --show-source
	@echo "Running MyPy..."
	mypy backend-api/ --ignore-missing-imports || true
	@echo "Running Pylint..."
	pylint backend-api/ || true

format-check:
	@echo "Checking code formatting..."
	black --check backend-api/
	isort --check-only backend-api/

format:
	@echo "Formatting code..."
	black backend-api/
	isort backend-api/
	@echo "✅ Code formatted"

# Security & Performance
security-scan:
	@echo "Running Bandit security analysis..."
	bandit -r backend-api/ -f json -o bandit-results.json || true
	@echo "Running Safety dependency check..."
	safety check --json > safety-results.json || true
	@echo "✅ Security scan complete"

load-test:
	@echo "Starting backend..."
	docker-compose up -d backend
	@sleep 3
	@echo "Running load test (Order API)..."
	k6 run load-tests/order-api.js \
		--out json=load-test-results.json \
		--summary-export=load-test-summary.json
	@echo "✅ Load test results in load-test-summary.json"

# Local Development
run-local:
	@echo "Starting backend (without Docker)..."
	python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Documentation
docs:
	@echo "Building documentation..."
	python -m mkdocs build
	@echo "✅ Documentation built in site/"

docs-serve:
	@echo "Serving documentation..."
	python -m mkdocs serve

# Utilities
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache/ htmlcov/ site/ build/ dist/ *.egg-info
	@echo "✅ Cleaned up artifacts"

ps:
	docker-compose ps

shell:
	docker-compose exec backend bash

db-shell:
	docker-compose exec postgres psql -U diomika_dev -d diomika_dev

redis-cli:
	docker-compose exec redis redis-cli

# Git Hooks
git-hooks:
	pre-commit install
	pre-commit run --all-files

# CI/CD Simulation
ci-local: lint format-check test-unit test-e2e
	@echo "✅ All local CI checks passed"
