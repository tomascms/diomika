# Optional Features Implementation

Complete reference for optional features implemented to enhance production operations.

## 1. Health Check Endpoints

### Overview
Three health check endpoints for Kubernetes liveness and readiness probes.

### Implementation
**File**: `backend-api/routes/health.py`

### Endpoints

#### `/health/live` (Liveness Probe)
```bash
curl http://localhost:8000/health/live
```

Returns 200 if service is running. Used by Kubernetes to determine if container should be restarted.

```json
{
  "status": "alive",
  "timestamp": "2024-01-15T10:30:00.000000",
  "service": "diomika-backend"
}
```

#### `/health/ready` (Readiness Probe)
```bash
curl http://localhost:8000/health/ready
```

Returns 200 if ready for traffic, 503 if not. Checks:
- Database connectivity ✓ (required)
- Cache/Redis connectivity (optional, doesn't fail if unavailable)

```json
{
  "status": "ready",
  "timestamp": "2024-01-15T10:30:00.000000",
  "checks": {
    "database": true,
    "cache": true
  },
  "service": "diomika-backend"
}
```

#### `/health` (General Health)
```bash
curl http://localhost:8000/health
```

Combines liveness + readiness into single endpoint.

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000000",
  "service": "diomika-backend"
}
```

### Kubernetes Configuration

In Helm values or Pod spec:

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 3
```

### Usage in Helm Charts
Already configured in `helm/templates/deployment.yaml`:
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: http
  initialDelaySeconds: {{ .Values.livenessProbe.initialDelaySeconds }}
  periodSeconds: {{ .Values.livenessProbe.periodSeconds }}

readinessProbe:
  httpGet:
    path: /health/ready
    port: http
  initialDelaySeconds: {{ .Values.readinessProbe.initialDelaySeconds }}
  periodSeconds: {{ .Values.readinessProbe.periodSeconds }}
```

## 2. Prometheus Metrics

### Overview
Comprehensive Prometheus metrics for monitoring API performance, database, business logic, and infrastructure.

### Implementation
**Files**: 
- `backend-api/core/metrics.py` - Metrics definitions
- `backend-api/routes/metrics.py` - Prometheus endpoint

### Metrics Endpoint
```bash
# Get all metrics in Prometheus format
curl http://localhost:8000/metrics
```

### Available Metrics

#### Request Metrics
- `http_requests_total` (counter): Total HTTP requests by method, endpoint, status
- `http_request_duration_seconds` (histogram): Request duration with 0.01-5s buckets
- `http_request_size_bytes` (histogram): Request size distribution
- `http_response_size_bytes` (histogram): Response size distribution

#### Database Metrics
- `db_connection_pool_size` (gauge): Current connection pool size
- `db_query_duration_seconds` (histogram): Query execution time by operation
- `db_query_errors_total` (counter): Total database errors by operation

#### Business Metrics
- `orders_created_total` (counter): Orders created by status
- `orders_completed_total` (counter): Successfully completed orders
- `invoices_generated_total` (counter): Generated invoices
- `emails_sent_total` (counter): Sent emails by type
- `saga_execution_duration_seconds` (histogram): Order saga duration
- `saga_failures_total` (counter): Failed sagas by type and reason

#### Cache Metrics
- `cache_hits_total` (counter): Cache hits by cache name
- `cache_misses_total` (counter): Cache misses by cache name
- `cache_size_bytes` (gauge): Cache size in bytes

#### System Metrics
- `active_sessions_total` (gauge): Active user sessions
- `auth_attempts_total` (counter): Authentication attempts by result
- `processing_queue_length` (gauge): Background job queue length
- `active_workers_total` (gauge): Active background workers

### Prometheus Configuration

In `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'diomika-backend'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
    scrape_timeout: 10s
```

### Grafana Dashboard Setup

1. Add Prometheus data source
2. Import dashboard or create panels:

```
Panel 1: Request Rate
  Query: rate(http_requests_total[5m])
  
Panel 2: Response Time (p95)
  Query: histogram_quantile(0.95, http_request_duration_seconds)
  
Panel 3: Database Queries/sec
  Query: rate(db_query_duration_seconds_count[5m])
  
Panel 4: Orders Completed
  Query: rate(orders_completed_total[5m])
```

### Alerts Setup

Example AlertManager rule:

```yaml
groups:
  - name: diomika
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        
      - alert: SlowResponses
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
        for: 10m
        
      - alert: SagaFailures
        expr: rate(saga_failures_total[5m]) > 0.01
        for: 5m
```

## 3. Database Seeding Script

### Overview
Populate development database with test data.

### Implementation
**File**: `scripts/seed_database.py`

### Data Created
- **3 Categories**: Almofadas, Mantas, Tapetes
- **3 Products**: Different types with attributes
- **3 Colors**: With prices and availability
- **2 Test Users**: Admin and regular user

### Usage

```bash
# Via Make command
make db-seed

# Direct Python execution
python scripts/seed_database.py

# With docker-compose
docker-compose exec backend python scripts/seed_database.py
```

### Output Example
```
🌱 Starting database seeding...

📦 Seeding categories...
✓ Category created: Almofadas
✓ Category created: Mantas
✓ Category created: Tapetes

📦 Seeding products...
✓ Product created: Almofada Confort Básica
✓ Product created: Almofada Premium Decorativa
✓ Product created: Manta Quentinha Inverno

📦 Seeding colors...
✓ Color created: Branco
✓ Color created: Cinzento
✓ Color created: Ouro

👤 Seeding test users...
✓ User created: Test Admin
✓ User created: Test User

✅ Database seeding completed successfully!

Test credentials:
  Admin: admin@diomika-test.pt
  User: user@diomika-test.pt
```

### Customization

Edit `scripts/seed_database.py` to:
- Change category names/slugs
- Add more products with different attributes
- Modify test user credentials
- Add more colors/variants

## 4. Distributed Tracing (OpenTelemetry)

### Overview
End-to-end request tracing for debugging and performance analysis.

### Implementation
**File**: `backend-api/core/tracing.py`

### Features
- Jaeger integration for trace collection
- Automatic FastAPI instrumentation
- Database query tracing
- Redis operation tracking
- HTTP request tracing
- Exception recording

### Configuration

#### Enable Tracing
```bash
# In .env or environment variables
ENABLE_TRACING=true
JAEGER_HOST=localhost
JAEGER_PORT=6831
```

#### Initialize in Application
```python
from core.tracing import initialize_tracing

# In main.py or app startup
initialize_tracing(service_name="diomika-backend")
```

### Usage

#### Automatic Instrumentation
```python
# FastAPI routes automatically traced
@app.post("/orders")
async def create_order(order: OrderSchema):
    # Automatically creates spans for:
    # - Request processing
    # - Database queries
    # - External API calls
    pass
```

#### Manual Span Creation
```python
from core.tracing import create_span, TracingContext

# Option 1: Context manager (recommended)
with TracingContext("order_processing", {"order_id": "123"}) as span:
    # Do work
    span.set_attribute("status", "processing")

# Option 2: Direct span creation
span = create_span("invoice_generation", {"invoice_id": "456"})
try:
    # Generate invoice
    span.set_attribute("success", True)
except Exception as e:
    record_exception(span, e)
finally:
    span.end()
```

### Jaeger Setup

#### Docker Compose
Add to `docker-compose.yml`:
```yaml
jaeger:
  image: jaegertracing/all-in-one:latest
  ports:
    - "6831:6831/udp"  # Collector
    - "16686:16686"    # UI
  environment:
    COLLECTOR_ZIPKIN_HOST_PORT: ":9411"
```

#### Access Jaeger UI
```
http://localhost:16686
```

#### Viewing Traces
1. Go to Jaeger UI
2. Select service: `diomika-backend`
3. Find trace by operation or tags
4. Click to view full trace timeline

### Trace Analysis Example

For order creation request:
```
REQUEST: POST /api/orders (250ms total)
├── validation (10ms)
├── database_insert (50ms)
│   ├── query_execute (40ms)
│   └── commit (10ms)
├── invoice_generation (120ms)
│   ├── pdf_creation (80ms)
│   └── s3_upload (40ms)
├── email_notification (60ms)
│   ├── template_render (20ms)
│   └── smtp_send (40ms)
└── event_publish (10ms)
```

### Performance Optimization
Use traces to identify bottlenecks:
- Find slow database queries
- Identify N+1 query problems
- Monitor external API latency
- Detect memory leaks via heap analysis

## Integration with Helm

All optional features are configured in Helm charts:

```yaml
# helm/values-production.yaml

health:
  liveness:
    enabled: true
    initialDelaySeconds: 10
    periodSeconds: 10
  readiness:
    enabled: true
    initialDelaySeconds: 5
    periodSeconds: 5

metrics:
  enabled: true
  port: 8000
  path: /metrics
  prometheus:
    scrapeInterval: 15s

tracing:
  enabled: true
  jaeger:
    host: jaeger-collector
    port: 6831
  sampling:
    type: probabilistic
    param: 0.1  # 10% sampling
```

## Deployment Checklist

- [ ] Enable health checks in Kubernetes
- [ ] Configure Prometheus scraping
- [ ] Set up Grafana dashboards
- [ ] Import AlertManager rules
- [ ] Deploy Jaeger (optional but recommended)
- [ ] Seed database with test data
- [ ] Test all endpoints locally: `make dev`
- [ ] Run load test with metrics: `make load-test`
- [ ] Verify metrics in Prometheus
- [ ] Verify traces in Jaeger

## Environment Variables

```bash
# Health Checks
HEALTH_CHECK_ENABLED=true

# Metrics
METRICS_ENABLED=true
PROMETHEUS_PORT=8000

# Tracing
ENABLE_TRACING=true
JAEGER_HOST=jaeger-collector
JAEGER_PORT=6831
JAEGER_SAMPLER_TYPE=probabilistic
JAEGER_SAMPLER_PARAM=0.1

# Database Seeding
SEED_DATABASE=false  # Set to true for first deployment
```

## Monitoring Dashboard Commands

```bash
# View metrics
curl http://localhost:8000/metrics | head -20

# Check health
curl http://localhost:8000/health

# View traces
# Open http://localhost:16686

# Test with load
make load-test

# Check database
make db-shell
```

## Conclusion

These optional features provide:
1. ✅ **Kubernetes Integration**: Liveness/readiness probes for orchestration
2. ✅ **Observable Systems**: Prometheus metrics for monitoring
3. ✅ **Developer Experience**: Test data seeding for local development
4. ✅ **Debugging**: Distributed tracing for request analysis

All are production-ready and integrate seamlessly with the existing infrastructure.
