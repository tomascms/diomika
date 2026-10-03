# Development Setup Guide

Complete guide for setting up the Diomika backend development environment with Docker, testing, and CI/CD infrastructure.

## Quick Start (5 minutes)

```bash
# Clone the repository
git clone https://github.com/tomascms/diomika.git
cd diomika

# Copy environment configuration
cp .env.example .env

# Start development environment
make dev

# Run all tests
make test
```

The backend is now available at `http://localhost:8000` and the database UI at `http://localhost:8080`.

## Prerequisites

- **Docker**: 20.10+ ([Install](https://docs.docker.com/get-docker/))
- **Docker Compose**: 2.0+ (included with Docker Desktop)
- **Python**: 3.11+ (for local development without Docker)
- **Make**: GNU Make (for command shortcuts)
- **Git**: 2.30+ (for version control)

## Directory Structure

```
diomika/
├── backend-api/              # FastAPI application
│   ├── core/                 # Business logic (saga, invoice, email, audit)
│   ├── routes/               # API endpoints (admin, catalog, orders, webhooks)
│   ├── models/               # Database models and schema
│   ├── migrations/           # SQL migrations (versioned manual)
│   └── tests/                # Unit tests
├── e2e/                      # End-to-end tests
│   ├── conftest.py           # E2E test fixtures
│   ├── test_order_flow.py    # Full order flow E2E tests
│   └── test_payment_saga.py  # Payment saga E2E tests
├── load-tests/               # k6 load testing
│   ├── order-api.js          # Order API baseline
│   └── payment-saga.js       # Payment saga baseline
├── helm/                     # Kubernetes Helm charts
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-staging.yaml
│   ├── values-production.yaml
│   └── templates/
├── .github/workflows/        # GitHub Actions CI/CD
│   └── ci-full-pipeline.yml  # 8-job comprehensive pipeline
├── docker-compose.yml        # Local development services
├── Dockerfile                # Container image
├── Makefile                  # Development commands
├── requirements.txt          # Python dependencies
├── pytest.ini                # Pytest configuration
├── .pre-commit-config.yaml   # Git hooks configuration
└── .env.example              # Environment variables template
```

## Service Architecture

### Docker Services (via docker-compose.yml)

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| **postgres** | PostgreSQL 15 | 5432 | Primary database |
| **redis** | Redis 7 | 6379 | Session cache, rate limiting |
| **backend** | FastAPI | 8000 | API application |
| **localstack** | LocalStack | 4566 | AWS service emulation (S3, SQS) |
| **adminer** | Adminer | 8080 | Database web UI |
| **webhook-test** | Nginx | 9000 | Mock webhook receiver |

### Local Development Services

```bash
# Start all services
make docker-up

# View service status
make ps

# View logs
make docker-logs

# Stop services
make docker-down

# Full clean (removes volumes)
make docker-clean
```

## Setup Steps

### 1. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit for your setup (optional - defaults work for local development)
nano .env
```

Key variables for local development:
- `DATABASE_URL`: Already configured for docker-compose
- `AWS_ACCESS_KEY_ID/SECRET`: Set to "testing" for LocalStack
- `SLACK_WEBHOOK_URL`: Points to mock webhook server
- `DEBUG=true`: Enables debug mode and auto-reload

### 2. Install Dependencies

```bash
# Using Make
make install

# OR manually
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
pre-commit install
```

### 3. Start Development Environment

```bash
# Option A: Using Docker Compose (recommended)
make dev
```

Services will start automatically:
- PostgreSQL with migrations applied
- Redis for caching
- FastAPI backend with hot-reload
- LocalStack for AWS emulation
- Adminer database UI

**Initial Setup Wait**: First-time startup takes ~10-15 seconds while containers initialize.

```bash
# Option B: Without Docker (requires local PostgreSQL/Redis)
make run-local
```

### 4. Database Setup

```bash
# Apply all migrations
make db-migrate

# Seed with test data (optional)
make db-seed

# Access database via web UI
# Open http://localhost:8080
# User: diomika_dev, Password: diomika_dev_password

# Access via CLI
make db-shell
```

## Development Workflow

### Running Tests

```bash
# Run all tests
make test

# Unit tests only (fast)
make test-unit

# E2E tests (full workflow)
make test-e2e

# With coverage report
make test-cov

# Watch mode (auto-run on file changes)
make test-watch
```

**Test Markers** (filter with `-m "marker_name"`):
- `unit`: Fast, isolated tests
- `integration`: Database-dependent tests
- `e2e`: Full workflow tests
- `slow`: Long-running tests (skip with `-m "not slow"`)
- `security`: Security-focused tests

### Code Quality

```bash
# Check code formatting
make format-check

# Auto-format code
make format

# Run all linters
make lint

# Simulate CI/CD locally
make ci-local
```

**Integrated Tools**:
- **Black**: Code formatting
- **isort**: Import sorting
- **Flake8**: Linting
- **MyPy**: Type checking
- **Pylint**: Code analysis
- **Bandit**: Security scanning
- **Pre-commit**: Git hooks

### API Development

```bash
# Backend auto-reloads on code changes
# Access API at http://localhost:8000

# View interactive documentation
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc

# Example: Create order
curl -X POST http://localhost:8000/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer": {"name": "Test", "email": "test@diomika.pt"},
    "lines": [{"ean": "5901234123457", "quantity": 1, "price": 99.99}]
  }'
```

### Database Access

```bash
# PostgreSQL CLI
make db-shell

# Redis CLI
make redis-cli

# Web UI (Adminer)
# Open http://localhost:8080
# Leave all defaults, click "Login"
```

## Performance & Load Testing

### Load Testing Baseline

```bash
# Run baseline load test
make load-test

# Results available in load-test-summary.json
cat load-test-summary.json | jq .

# Manual k6 test with custom settings
k6 run load-tests/order-api.js \
  --vus 200 \
  --duration 5m \
  --out json=results/custom-$(date +%s).json
```

**Target Metrics**:
- Order API: 100+ req/s, p95 < 500ms
- Payment Saga: 50+ req/s, p95 < 2000ms
- Success Rate: 99.9%

### Performance Profiling

```bash
# With Python profiler
python -m cProfile -o profile.stats main.py

# Analyze with snakeviz
pip install snakeviz
snakeviz profile.stats
```

## CI/CD Integration

### GitHub Actions Pipeline

The `.github/workflows/ci-full-pipeline.yml` runs automatically on push/PR:

1. **Security Scan** (9 tools): Trivy, TruffleHog, Bandit, Safety
2. **Code Quality**: Black, isort, Flake8, MyPy, Pylint
3. **Unit Tests**: With coverage reporting
4. **E2E Tests**: Full workflow validation
5. **Load Testing**: Performance regression detection
6. **Docker Build**: Image push to registry
7. **Deployment Check**: Readiness verification

### Setting Up Secrets

Follow `.github/GITHUB_ACTIONS_SECRETS.md` to configure:
- `DATABASE_URL`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `SLACK_WEBHOOK_URL`
- `PAGERDUTY_SERVICE_KEY`
- `GITGUARDIAN_API_KEY`

```bash
# Via GitHub CLI
gh secret set DATABASE_URL --body "postgresql://..."
gh secret set AWS_ACCESS_KEY_ID --body "AKIA..."
```

### Local CI Simulation

```bash
# Run all CI checks locally (before pushing)
make ci-local
```

## Troubleshooting

### Services Won't Start

```bash
# Check Docker daemon
docker version

# View detailed logs
docker-compose logs -f

# Restart specific service
docker-compose restart postgres

# Full reset
make docker-clean
make docker-up
```

### Database Connection Errors

```bash
# Verify PostgreSQL is running
make ps

# Check connection string
grep DATABASE_URL .env

# Test connection
psql "postgresql://diomika_dev:diomika_dev_password@localhost:5432/diomika_dev"
```

### Test Failures

```bash
# Run with verbose output
pytest tests/ -vv --tb=long

# Run specific test
pytest tests/test_order_saga.py::TestOrderSaga::test_basic -vv

# Check dependencies
pip list | grep -E "pytest|sqlalchemy|fastapi"
```

### Performance Issues

```bash
# Check resource usage
docker stats

# View slow queries
docker-compose logs postgres | grep "duration"

# Restart database (clears connections)
docker-compose restart postgres
```

### Pre-commit Hook Failures

```bash
# Run hooks manually
pre-commit run --all-files

# Install dependencies
pre-commit install

# Bypass for emergency (not recommended)
git commit --no-verify
```

## Useful Commands

```bash
# System Information
make ps                  # Service status
docker-compose logs -f   # Stream logs

# Database
make db-shell           # PostgreSQL shell
make redis-cli          # Redis CLI
make db-migrate         # Run migrations
make db-reset           # Reset database

# Testing
make test               # All tests
make test-unit          # Unit only
make test-cov           # With coverage
make test-watch         # Watch mode

# Code Quality
make lint               # Run linters
make format             # Auto-format
make security-scan      # Security tools

# Utilities
make help               # Show all commands
make clean              # Remove artifacts
make git-hooks          # Setup/update git hooks
```

## Development Tips

1. **Hot Reload**: Backend auto-reloads on code changes in development mode
2. **Database UI**: Use Adminer (http://localhost:8080) for quick database inspection
3. **API Docs**: Swagger UI at http://localhost:8000/docs has integrated API testing
4. **Logging**: Check logs via `docker-compose logs -f` for real-time debugging
5. **Test First**: Write tests before implementing features
6. **Pre-commit**: Let git hooks catch issues before commit
7. **Migrations**: Create migrations for all schema changes (never modify old ones)

## Deployment Preparation

Before deploying to production:

```bash
# 1. Run all local checks
make ci-local

# 2. Check load test baseline
make load-test

# 3. Security scan
make security-scan

# 4. Verify all migrations
make db-migrate

# 5. Review environment configuration
# - Set all production secrets in GitHub Actions
# - Configure Slack/PagerDuty webhooks
# - Set up AWS IAM credentials

# 6. Deploy via Helm
helm upgrade --install diomika ./helm \
  -f ./helm/values-production.yaml \
  --namespace production
```

## Additional Resources

- **Requirements**: `requirements.txt` - All Python dependencies
- **Configuration**: `pytest.ini` - Test settings, markers, coverage
- **Migrations**: `backend-api/migrations/` - SQL schema versions
- **Load Testing**: `LOAD_TEST_BASELINE.md` - Performance baselines
- **Secrets**: `.github/GITHUB_ACTIONS_SECRETS.md` - CI/CD setup
- **Infrastructure**: `INFRASTRUCTURE.md` - Kubernetes, monitoring
- **Deployment**: `DEPLOYMENT_CHECKLIST.md` - Pre-release checks

## Getting Help

- **GitHub Issues**: Report bugs or feature requests
- **Documentation**: Check INFRASTRUCTURE.md and related docs
- **Logs**: `docker-compose logs -f` for service debugging
- **Tests**: Run tests in verbose mode to see assertions

## Next Steps

1. Start development environment: `make dev`
2. Run tests: `make test`
3. Make your changes
4. Run CI checks locally: `make ci-local`
5. Create pull request with results

Happy coding! 🚀
