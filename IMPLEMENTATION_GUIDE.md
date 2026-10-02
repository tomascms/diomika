# Diomika Professional Implementation Guide

Guia completo para integração e uso dos módulos profissionais implementados.

## Índice

1. [Database Migrations](#1-database-migrations)
2. [CQRS Integration](#2-cqrs-integration)
3. [Event-Driven Architecture](#3-event-driven-architecture)
4. [Sagas Pattern](#4-sagas-pattern)
5. [WebSocket Real-time Updates](#5-websocket-real-time-updates)
6. [Background Jobs](#6-background-jobs)
7. [Monitoring & Tracing](#7-monitoring--tracing)
8. [API Versioning](#8-api-versioning)
9. [Rate Limiting](#9-rate-limiting)
10. [Security & Testing](#10-security--testing)
11. [Kubernetes Deployment](#11-kubernetes-deployment)
12. [Disaster Recovery](#12-disaster-recovery)

---

## 1. Database Migrations

### Setup

```python
from core.migration_manager import get_migration_manager

# Initialize
manager = get_migration_manager()

# Check pending migrations
status = manager.get_migration_status()
print(f"Pending: {status['pending']}, Executed: {status['executed']}")
```

### Creating Migrations

```sql
-- backend-api/sql/0005_new_feature.sql
CREATE TABLE IF NOT EXISTS new_feature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_new_feature_name ON new_feature(name);
```

### Running Migrations

```python
# In main.py startup
import asyncio
from core.migration_manager import get_migration_manager

async def run_migrations():
    manager = get_migration_manager()
    result = await manager.execute_pending_migrations()
    logger.info(f"Migration result: {result}")

# In lifespan context
await asyncio.to_thread(lambda: asyncio.run(run_migrations()))
```

---

## 2. CQRS Integration

### Creating Commands

```python
from core.cqrs import Command
from core.cqrs_handlers import EndpointCommandHandler

class CreateProductCommand(Command):
    def __init__(self, name: str, price: float):
        super().__init__()
        self.name = name
        self.price = price
```

### Creating Handlers

```python
class CreateProductHandler(EndpointCommandHandler):
    async def _execute(self, command: CreateProductCommand):
        # Business logic
        product = {
            "id": uuid.uuid4(),
            "name": command.name,
            "price": command.price,
        }
        # Save to database
        return product

    def _get_generated_events(self, command, result):
        return [
            {
                "aggregate_id": str(result["id"]),
                "event_type": "product.created",
                "data": result,
            }
        ]
```

### Using in Endpoints

```python
@router.post("/products")
async def create_product(payload: CreateProductModel):
    handler = CreateProductHandler()
    command = CreateProductCommand(payload.name, payload.price)
    result = await handler.handle(command)
    return result
```

---

## 3. Event-Driven Architecture

### Event Subscribers

```python
from core.event_subscribers import EventSubscriber, get_subscription_manager

class OrderNotificationSubscriber(EventSubscriber):
    @property
    def event_types(self):
        return ["order.created", "order.confirmed"]

    async def handle_event(self, event):
        # Send email, push notification, etc.
        logger.info(f"Handling event: {event.event_type}")
        return True

# Register subscriber
manager = get_subscription_manager()
manager.register_subscriber(OrderNotificationSubscriber())
```

### Publishing Events via Outbox

```python
from core.outbox_pattern import get_outbox_publisher

publisher = get_outbox_publisher()

# Events are automatically published via outbox pattern
# When command handler executes and returns
```

---

## 4. Sagas Pattern

### Creating Sagas

```python
from core.saga_coordinator import Saga, SagaStep

class PaymentSaga(Saga):
    async def build_steps(self, context):
        return [
            SagaStep(
                name="Validate Payment",
                action=lambda: self._validate_payment(context),
                compensation=lambda: self._log_validation_failure(context),
            ),
            SagaStep(
                name="Process Payment",
                action=lambda: self._process_payment(context),
                compensation=lambda: self._refund_payment(context),
                retry_count=3,
            ),
            SagaStep(
                name="Confirm Payment",
                action=lambda: self._confirm_payment(context),
            ),
        ]

    async def _validate_payment(self, context):
        # Validation logic
        return {"valid": True}

    async def _process_payment(self, context):
        # Payment processing
        return {"transaction_id": str(uuid.uuid4())}

    # ... other steps
```

### Executing Sagas

```python
from core.saga_coordinator import get_saga_orchestrator

saga = PaymentSaga()
orchestrator = get_saga_orchestrator()

saga_instance = await orchestrator.execute_saga(
    saga,
    context={"order_id": "123", "amount": 100.00},
    user_id="user_456",
)

# Check status
print(saga_instance.status)  # "completed" or "failed"
```

---

## 5. WebSocket Real-time Updates

### Setup in Main

```python
from core.websocket_manager import get_websocket_manager

# Initialize
ws_manager = get_websocket_manager()

# Include WebSocket router
from routes.websocket_example import router as ws_router
app.include_router(ws_router)
```

### Client Example (JavaScript)

```javascript
// Connect to order updates
const ws = new WebSocket('wss://api.diomika.com/ws/orders/order_123');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'order_status_changed') {
        console.log(`Order status: ${data.new_status}`);
        updateUI(data);
    }
};

// Send ping
setInterval(() => {
    ws.send(JSON.stringify({type: 'ping'}));
}, 30000);
```

### Broadcasting Updates

```python
from core.websocket_manager import get_order_update_publisher

publisher = get_order_update_publisher()

await publisher.publish_order_status_changed(
    order_id="order_123",
    old_status="pending",
    new_status="confirmed",
)
```

---

## 6. Background Jobs

### Setup

```python
from core.job_queue import get_job_queue, Job, JobPriority

# Initialize
job_queue = get_job_queue()

# Register handlers
async def send_email_handler(data):
    email = data['email']
    subject = data['subject']
    # Send email
    return {'sent': True}

job_queue.register_handler('send_email', send_email_handler)
```

### Enqueuing Jobs

```python
# In command handler
job = Job(
    job_type='send_email',
    data={
        'email': 'customer@example.com',
        'subject': 'Order Confirmation',
    },
    priority=JobPriority.HIGH,
    max_retries=3,
)

await job_queue.enqueue(job)
```

### Processing Jobs

```python
# In background worker
async def process_jobs():
    while True:
        job = await job_queue.dequeue(JobPriority.HIGH)
        if job:
            success = await job_queue.execute_job(job)
            logger.info(f"Job {job.job_id}: {'success' if success else 'failed'}")
```

---

## 7. Monitoring & Tracing

### Setup Tracing

```python
from core.distributed_tracing import get_tracer, TracingMiddleware

tracer = get_tracer()
app.add_middleware(TracingMiddleware, tracer=tracer)
```

### Custom Spans

```python
tracer = get_tracer()

# Start span
span = tracer.start_span(
    trace_id=request.state.request_id,
    span_name="database_query",
)

try:
    # Do work
    result = await db.query()
    span.set_attribute("rows", len(result))
    span.set_status("OK")
finally:
    tracer.end_span(span.span_id)
```

### Prometheus Metrics

```python
from core.prometheus_metrics import get_application_metrics

metrics = get_application_metrics()

# Record HTTP request
metrics.record_http_request("GET", "/catalog", 0.150, 200)

# Record database query
metrics.record_database_query("SELECT", 0.050)

# Record cache hit
metrics.record_cache_hit()
```

### Metrics Endpoint

```python
@app.get("/metrics")
async def metrics():
    registry = get_metrics_registry()
    return Response(
        content=registry.export_prometheus_format(),
        media_type="text/plain",
    )
```

---

## 8. API Versioning

### Setup

```python
from core.api_versioning import get_api_version_config, APIVersion

config = get_api_version_config()

# Get version from header
version = get_api_version(x_api_version="v2")
```

### Version-Specific Endpoints

```python
@router.get("/products", dependencies=[Depends(get_api_version)])
async def list_products_v1(api_version: APIVersion):
    if api_version == APIVersion.V1:
        # Return v1 format
        return {"products": [...], "format": "v1"}
    else:
        # Return v2 format
        return {"items": [...], "meta": {...}}
```

### Deprecation Warnings

```python
from core.api_versioning import DeprecationWarning

warning = DeprecationWarning(
    deprecated_version=APIVersion.V1,
    sunset_date="2025-01-01",
    replacement="/api/v2/products",
)

response.headers["Deprecation"] = warning.to_header()
```

---

## 9. Rate Limiting

### Setup

```python
from core.endpoint_rate_limiting import (
    get_rate_limiter,
    RateLimitConfig,
    RATE_LIMITS,
)

rate_limiter = await get_rate_limiter()

# Register endpoint
rate_limiter.register_endpoint(
    "list_products",
    RATE_LIMITS["authenticated"],  # 60 req/min, 2000 req/h
)
```

### Checking Rate Limits

```python
# In endpoint
allowed, remaining = await rate_limiter.check_rate_limit(
    endpoint_key="list_products",
    identifier=user_id,
)

if not allowed:
    raise HTTPException(status_code=429)
```

### Adaptive Rate Limiting

```python
adaptive_limiter = await get_adaptive_rate_limiter()

# Reduce limits if under high load
await adaptive_limiter.update_load_factor("list_products", 0.5)
```

---

## 10. Security & Testing

### Load Testing

```bash
# Run k6 load tests
k6 run backend-api/load_tests/k6_scenarios.js \
    --vus 50 \
    --duration 2m \
    --env BASE_URL=http://localhost:8001

# Run specific scenario
k6 run -f load_tests/k6_scenarios.js::testStress
```

### Security Testing

```bash
# Run OWASP ZAP scan
python backend-api/security_tests/zap_scanner.py

# Run security tests
python -m pytest security_tests/ -v
```

### Integration Tests

```bash
# Run CQRS integration tests
pytest tests/test_cqrs_integration.py -v

# Run with coverage
pytest tests/ --cov=core --cov-report=html
```

---

## 11. Kubernetes Deployment

### Deploy with Helm

```bash
# Install
helm install diomika k8s/helm/diomika-api \
    --namespace production \
    --values k8s/helm/diomika-api/values-prod.yaml

# Upgrade
helm upgrade diomika k8s/helm/diomika-api \
    --namespace production \
    --values k8s/helm/diomika-api/values-prod.yaml

# Check status
kubectl rollout status deployment/diomika-api -n production
```

### Blue-Green Deployment

```bash
# Deploy green version
kubectl apply -f k8s/blue_green_deployment.yaml

# Test green version
curl https://green-api.diomika.com/health

# Switch traffic
kubectl patch service diomika-api -p '{"spec":{"selector":{"version":"green"}}}'

# Rollback if needed
kubectl patch service diomika-api -p '{"spec":{"selector":{"version":"blue"}}}'
```

### Health Checks

```bash
# Check liveness
curl http://localhost:8000/health/live

# Check readiness
curl http://localhost:8000/health/ready

# Check startup
curl http://localhost:8000/health/startup

# Check detailed health
curl http://localhost:8000/health/detail
```

---

## 12. Disaster Recovery

### Backup Procedures

```bash
# Manual database backup
supabase db push --linked

# Verify backups
aws s3 ls s3://diomika-backups/

# Restore from backup
supabase db restore --backup-ref <backup-id>
```

### Failover

```bash
# Activate secondary region
terraform apply -var="active_region=secondary"

# Update DNS
gcloud dns record-sets update api.diomika.com \
    --rrdatas=secondary-ip \
    --zone=diomika

# Verify
curl https://api.diomika.com/health
```

### Recovery Validation

```bash
# Run restore tests
pytest tests/test_restore_integrity.py -v

# Run database checks
psql -c "SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 10"

# Verify application
curl -H "Authorization: Bearer $TOKEN" https://api.diomika.com/health/detail
```

---

## Configuration Files

### Environment Variables

```bash
# .env.production
DIOMIKA_ENV=production
DATABASE_URL=postgresql://user:pass@host:5432/diomika
REDIS_URL=redis://host:6379
SUPABASE_URL=https://project.supabase.co
SUPABASE_KEY=eyJhbGc...

# API & Security
API_SECRET_KEY=your-secret-key
ALLOWED_HOSTS=api.diomika.com,api-secondary.diomika.com

# Monitoring
SENTRY_DSN=https://...
PROMETHEUS_ENABLED=true

# WebSocket
WEBSOCKET_HEARTBEAT_INTERVAL=30
```

### Helm Values

```yaml
# k8s/helm/diomika-api/values-prod.yaml
replicaCount: 5
image:
  tag: v1.0.0
resources:
  limits:
    cpu: 2000m
    memory: 1Gi
autoscaling:
  enabled: true
  minReplicas: 5
  maxReplicas: 20
```

---

## Performance Targets

- **API Latency**: p99 < 500ms
- **Database Queries**: p95 < 100ms
- **Cache Hit Rate**: > 80%
- **Error Rate**: < 0.1%
- **Availability**: 99.9% SLA
- **Startup Time**: < 30s

## Monitoring & Alerts

```yaml
# Prometheus rules
groups:
  - name: diomika
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(errors_total[5m]) > 0.001
        for: 5m
        action: page
      
      - alert: SlowQueries
        expr: histogram_quantile(0.99, db_query_duration_seconds) > 0.5
        for: 10m
        action: notify
```

---

## Support & Documentation

- **API Documentation**: https://api.diomika.com/docs
- **Status Page**: https://status.diomika.com
- **GitHub Issues**: https://github.com/diomika/diomika-api/issues
- **Slack Channel**: #api-support

---

**Last Updated**: 2024-10-02  
**Maintained By**: Infrastructure Team
