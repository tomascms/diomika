# Performance Tuning Guide

This document provides comprehensive performance optimization strategies for Diomika based on Prometheus metrics and observability data.

## Database Optimization

### Connection Pooling

**Monitor:** `pg_stat_activity_count`, `pg_connections_used`, `pg_connections_limit`

```python
# Optimal pool sizes in core/config.py
PRODUCTION_POOL_SIZE = 25      # 25 connections per worker
PRODUCTION_MAX_OVERFLOW = 15   # Up to 40 total during peaks
STAGING_POOL_SIZE = 15
DEVELOPMENT_POOL_SIZE = 10

# Calculation: pool_size + max_overflow = concurrent_connections
# = num_workers * (pool_size + max_overflow)
# Example: 4 workers * (25 + 15) = 160 max connections
```

### Query Optimization

**Hot queries to analyze:**

1. **Catalog search** - Indexed on: `typ_catalog`, `id_modelo`, `id_categoria`
   ```sql
   CREATE INDEX idx_catalog_search ON catalogo(tipo_catalogo, id_modelo, id_categoria);
   ANALYZE catalogo;
   ```

2. **Order lookups** - Indexed on: `customer_id`, `order_date`
   ```sql
   CREATE INDEX idx_orders_customer_date ON orders(customer_id, order_date DESC);
   ```

3. **Audit trail** - Indexed on: `created_at`, `user_id`, `action`
   ```sql
   CREATE INDEX idx_audit_time ON audit_trail(created_at DESC);
   CREATE INDEX idx_audit_user ON audit_trail(user_id, created_at DESC);
   ```

### Missing Index Detection

Monitor in CloudWatch/DataDog:
- **slow_queries**: Queries taking >1 second
- **seq_scans**: Sequential table scans indicate missing indexes

```sql
-- Find missing indexes
SELECT 
  schemaname, tablename, indexname
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY tablename;

-- Check index usage
SELECT 
  relname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(relid) DESC;
```

## Cache Strategy

### Redis Configuration

**Monitor:** `cache_hit_rate`, `cache_eviction_rate`, `redis_memory_used`

```python
# Optimal TTL by entity type
CACHE_TTL = {
    "catalog": 3600,           # 1 hour - catalog changes infrequent
    "orders": 300,             # 5 min - orders change constantly
    "customer": 1800,          # 30 min - customer data semi-static
    "search_results": 600,     # 10 min - search results vary by query
    "inventory": 60,           # 1 min - inventory critical freshness
}

# Target hit rate: >85%
# If <85%: increase TTL or cache more data
# If >95%: consider longer TTL
```

### Cache Invalidation

**Smart invalidation to avoid cascade invalidation:**

```python
# In core/cache_invalidation_strategy.py
# Surgical invalidation: only affected keys
# Avoid: invalidate entire cache

# Good ✓
cache.delete(f"catalog:modelo:{model_id}")
cache.delete(f"orders:customer:{customer_id}")

# Bad ✗
cache.delete("catalog:*")      # Too broad
cache.flushdb()                 # Catastrophic
```

## API Response Time Optimization

**Target latencies (p95/p99):**
- Simple GET (cached): <50ms / 100ms
- GET (database): <200ms / 500ms
- POST/PUT/DELETE: <500ms / 1000ms
- Search queries: <1s / 2s

### Bottleneck Detection

```python
# Enable request tracing in core/main.py
@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Alert if slow
    if process_time > 1.0:
        logger.warning(f"Slow request: {request.url.path} took {process_time}s")
    
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

**Profile endpoints:**

```bash
# Using py-spy (in-production safe)
py-spy record -o profile.svg -- python -m uvicorn core.main:app

# View: profile.svg in browser
```

## Worker Performance

### Background Workers Tuning

**Monitor:** `email_worker_duration`, `outbox_worker_duration`, `saga_executor_duration`

```python
# Optimal poll intervals in helm/values.yaml
email_poll_seconds: 30         # Check for emails every 30s
outbox_poll_seconds: 30        # Process events every 30s  
saga_sweep_seconds: 300        # Sweep zombie sagas every 5m
saga_process_seconds: 10       # Process pending sagas every 10s
retention_sweep_cycles: 12     # Retention cleanup every 1 hour

# If queue buildup:
# - Decrease poll interval (trade off CPU)
# - Increase worker threads
# - Scale horizontally (multiple containers)
```

### Batch Processing

```python
# Process in batches, not individually
# Good ✓
outbox_events = get_pending_events(limit=100)
for event in outbox_events:
    send_event(event)
db.commit()  # One commit per batch

# Bad ✗
for event in get_all_pending_events():
    send_event(event)
    db.commit()  # One commit per event - slow!
```

## Memory Optimization

**Monitor:** `container_memory_usage_bytes`, `process_resident_memory_bytes`

### Memory Leaks

```python
# Check for circular references
import tracemalloc

tracemalloc.start()
# ... run code ...
current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024 / 1024}MB; Peak: {peak / 1024 / 1024}MB")
```

### Resource Limits

```yaml
# In helm/values-production.yaml
resources:
  requests:
    memory: 1024Mi    # Guaranteed
    cpu: 1000m
  limits:
    memory: 2048Mi    # Maximum (OOMKilled if exceeded)
    cpu: 2000m

# VPA recommendations
vpa:
  enabled: true
  updateMode: "Auto"   # Automatically adjust based on usage
```

## Database Connection Pooling Metrics

```python
# Monitor in Prometheus
- name: 'SQLAlchemy Pool'
  help: 'Database connection pool metrics'
  metrics:
    - sqlalchemy_pool_size{pool: "default"}
    - sqlalchemy_pool_checked_out{pool: "default"}
    - sqlalchemy_pool_checked_in{pool: "default"}
    - sqlalchemy_pool_overflow{pool: "default"}
```

## Load Test Baselines

Run load tests to establish baselines:

```bash
# Warmup
k6 run --vus 1 --duration 30s load-tests/order-api.js

# Baseline test
k6 run --vus 50 --duration 10m load-tests/order-api.js

# Store results for comparison
k6 run --out csv=results.csv load-tests/order-api.js
```

**Expected throughput:**
- Order creation: 100+ RPS at p95 <500ms
- Order listing: 500+ RPS at p95 <200ms
- Product search: 1000+ RPS at p95 <500ms

## CloudWatch Dashboards

Key metrics to monitor:

```
API Performance:
- http_requests_total (rate)
- http_request_duration (p50, p95, p99)
- http_requests_failed_total (rate)

Database:
- db_query_total (rate)
- db_query_duration (p95)
- pg_stat_activity_count
- pg_connections_used / pg_connections_limit

Cache:
- cache_hits_total (rate)
- cache_misses_total (rate)
- cache_hit_rate (%)

Workers:
- email_worker_processed
- outbox_worker_processed
- saga_executor_processed
- saga_executor_compensated
```

## Cost Optimization

### Right-sizing Resources

```python
# Use VPA to auto-right-size
# Monitor for 1-2 weeks to get recommendations

# Common oversizing:
- Memory: 2GB when only using 500MB
- CPU: 2 cores when only using 0.5 core

# Cost savings: 50-60% typical
```

### Scaling Strategy

```yaml
# Scale up gradually
autoscaling:
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70  # Scale at 70%
  targetMemoryUtilizationPercentage: 80

  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30   # Quick scale-up
      policies:
        - type: Percent
          value: 100                    # Double replicas
          periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300  # Gradual scale-down
      policies:
        - type: Percent
          value: 50                     # Half replicas
          periodSeconds: 60
```

## Recommended Monitoring Alerts

```yaml
# In k8s/alertmanager-config.yml
- alert: HighAPILatency
  expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
  for: 5m
  annotations:
    summary: "API latency > 1 second (p95)"

- alert: CacheHitRateLow
  expr: cache_hit_rate < 0.80
  for: 10m
  annotations:
    summary: "Cache hit rate < 80%"

- alert: DatabaseConnectionPoolExhausted
  expr: pg_connections_used / pg_connections_limit > 0.9
  for: 5m
  annotations:
    summary: "Database connections >90% utilized"
```

## References

- Prometheus best practices: https://prometheus.io/docs/practices/
- PostgreSQL optimization: https://www.postgresql.org/docs/current/performance.html
- Redis memory optimization: https://redis.io/topics/memory-optimization
- k6 load testing: https://k6.io/docs/
