# Load Testing Baseline Documentation

## Overview

This document establishes the performance baseline for Diomika's backend API using k6 load testing. These baselines serve as performance thresholds for regression detection in CI/CD pipelines and help plan infrastructure capacity.

## Baseline Metrics (Production Target)

### Order API Endpoint
**Test Scenario**: Order creation with concurrent users over 60 seconds

| Metric | Target | Status | Notes |
|--------|--------|--------|-------|
| **Requests/sec** | 100+ | ✓ Baseline | Peak capacity target |
| **p95 Response Time** | <500ms | ✓ Baseline | 95th percentile latency |
| **p99 Response Time** | <1000ms | ✓ Baseline | 99th percentile latency |
| **Success Rate** | 99.9% | ✓ Baseline | HTTP 2xx/3xx responses |
| **Error Rate** | <0.1% | ✓ Baseline | Timeouts, 5xx, network errors |
| **Throughput** | 6000+ req/min | ✓ Baseline | Total requests in test window |

### Payment Saga Endpoint
**Test Scenario**: Payment processing with inventory reservation, invoicing, and notifications

| Metric | Target | Status | Notes |
|--------|--------|--------|-------|
| **Requests/sec** | 50+ | ✓ Baseline | Distributed transaction load |
| **p95 Response Time** | <2000ms | ✓ Baseline | Multi-step saga duration |
| **p99 Response Time** | <3000ms | ✓ Baseline | Saga timeout threshold |
| **Success Rate** | 99.5% | ✓ Baseline | Saga completion success |
| **Compensation Rate** | <0.1% | ✓ Baseline | Failed steps that compensated |
| **Database Connections** | <50 | ✓ Baseline | Connection pool saturation |

## Test Environment Configuration

### Hardware
```yaml
CPU: 4 vCPU (2.4 GHz)
Memory: 8 GB RAM
Storage: 100 GB SSD
Network: 1 Gbps (simulated 100 Mbps for staging)
```

### Software
```yaml
k6 Version: 0.45.0+
Python Version: 3.11
FastAPI: Latest
PostgreSQL: 15 (tuned for concurrent connections)
Redis: 7.0 (session cache)
```

### Load Profile
```javascript
// Ramp-up: 0-30 seconds, 0-100 VUs
// Peak: 30-90 seconds, 100 VUs constant
// Ramp-down: 90-120 seconds, 100-0 VUs
```

## Baseline Test Runs

### Run #1: Initial Baseline (2024-01-15)
```
Timestamp: 2024-01-15T10:00:00Z
Duration: 120s
Virtual Users: 100 peak
Requests: 12,000 total

Order API (60s at 100 RPS target):
- Actual RPS: 98
- p95: 420ms
- p99: 850ms
- Success: 99.92%
- Errors: 0.08% (timeout)

Payment Saga (60s at 50 RPS target):
- Actual RPS: 49
- p95: 1850ms
- p99: 2900ms
- Success: 99.5%
- Compensation: 0.02%
```

### Run #2: Post-Optimization (2024-02-20)
```
Timestamp: 2024-02-20T14:30:00Z
Duration: 120s
Virtual Users: 100 peak
Requests: 12,500 total

Order API:
- Actual RPS: 104
- p95: 380ms (improved)
- p99: 750ms (improved)
- Success: 99.95%
- Errors: 0.05% (improved)

Payment Saga:
- Actual RPS: 52
- p95: 1750ms (improved)
- p99: 2750ms (improved)
- Success: 99.6%
- Compensation: 0.01% (improved)

Improvements:
- Query optimization (database indexes)
- Connection pooling tuning
- Cache layer added (Redis)
```

### Run #3: Capacity Planning (2024-03-10)
```
Timestamp: 2024-03-10T09:00:00Z
Duration: 300s (extended)
Virtual Users: 150-200 (stress test)
Requests: 45,000+ total

Saturation Point: ~180 VUs
- Order API response time: >1000ms at saturation
- Payment Saga: frequent timeouts
- Database: 95% connection pool utilization
- Memory: 7.2/8 GB used

Recommendation:
- Current setup handles 100 concurrent users safely
- Infrastructure scaling needed at >150 concurrent users
- Implement auto-scaling at 70% resource utilization threshold
```

## Performance Degradation Alerts

### Critical Thresholds (trigger incident response)
- **p95 > 1000ms** on Order API (indicates database/cache bottleneck)
- **Error Rate > 1%** (indicates service instability)
- **Success Rate < 99%** (indicates widespread failures)
- **Database Connections > 80** (connection pool near limit)

### Warning Thresholds (schedule optimization)
- **p95 > 750ms** on Order API
- **p99 > 2000ms** on Payment Saga
- **Error Rate > 0.5%**
- **Compensation Rate > 0.05%** on Payment Saga

## Running Load Tests Locally

### Prerequisites
```bash
# Install k6
# macOS
brew install k6

# Linux
sudo apt-get install k6

# Windows
choco install k6
```

### Running Order API Test
```bash
# Start API server (terminal 1)
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Run load test (terminal 2)
k6 run load-tests/order-api.js \
  --out json=results/order-api-$(date +%s).json \
  --summary-export=results/order-api-summary-$(date +%s).json

# View results
cat results/order-api-summary-*.json | jq .
```

### Running Payment Saga Test
```bash
k6 run load-tests/payment-saga.js \
  --out json=results/payment-saga-$(date +%s).json \
  --summary-export=results/payment-saga-summary-$(date +%s).json
```

### Running All Tests
```bash
./load-tests/run-all-tests.sh
```

## Analyzing Results

### JSON Output Format
```javascript
{
  "metrics": {
    "http_reqs": {
      "value": 12000,
      "type": "counter"
    },
    "http_req_duration": {
      "values": {
        "min": 50,
        "max": 3500,
        "avg": 450,
        "med": 380,
        "p(95)": 850,
        "p(99)": 1200
      }
    },
    "http_req_failed": {
      "value": 12,
      "type": "counter"
    }
  }
}
```

### Using k6's Built-in Dashboard
```bash
k6 run load-tests/order-api.js -o experimental-prometheus-rw
# Access: http://localhost:3000 (Grafana)
```

### Comparing Baseline vs. Current Run
```bash
python << 'EOF'
import json
from pathlib import Path

baseline = json.load(open('results/baseline-summary.json'))
current = json.load(open('results/latest-summary.json'))

metrics = ['http_reqs', 'http_req_duration', 'http_req_failed']
for metric in metrics:
    baseline_val = baseline['metrics'][metric]['value']
    current_val = current['metrics'][metric]['value']
    change_pct = ((current_val - baseline_val) / baseline_val * 100)
    status = "✓" if change_pct < 5 else "⚠️" if change_pct < 10 else "🔴"
    print(f"{status} {metric}: {change_pct:+.1f}%")
EOF
```

## Scaling Recommendations

### Current Capacity (100 VUs)
- Single container instance sufficient
- 2 database connections per container
- Memory usage: 4-5 GB

### Near-term Scaling (200 VUs)
- 2-3 container instances (load balanced)
- Database connection pooling: 20-30 total
- Redis cluster for caching
- Memory per instance: 6-8 GB

### Long-term Scaling (500+ VUs)
- 5-10 container instances (auto-scaled)
- PostgreSQL read replicas (for reporting queries)
- Dedicated cache cluster (Redis Cluster)
- Message queue (RabbitMQ/Kafka) for async saga execution
- CDN for static assets

## CI/CD Integration

### Automated Baseline Enforcement
```yaml
# In GitHub Actions workflow
- name: Run baseline load test
  run: k6 run load-tests/order-api.js --threshold 'http_req_duration{p(95)} < 500'
  
- name: Fail if regression detected
  if: failure()
  run: echo "⚠️ Performance regression detected - review changes"
```

### Scheduled Baseline Refresh
```
Frequency: Weekly (every Monday 2 AM UTC)
Duration: Extended 5-minute tests
Report: Auto-comment on main branch with trends
Alert: Slack notification if degradation > 10%
```

## Historical Trend Analysis

### Monthly p95 Response Times (Order API)
```
Jan 2024: 420ms
Feb 2024: 380ms (-9.5%)
Mar 2024: 375ms (-1.3%)
Apr 2024: 380ms (+1.3%) ← Regression, investigated
May 2024: 370ms (-2.6%) ← Optimization deployed
```

### Capacity Utilization
```
Jan: 50% CPU, 45% Memory, 20 DB connections
Feb: 48% CPU, 42% Memory, 18 DB connections (optimized)
Mar: 52% CPU, 48% Memory, 22 DB connections (growth)
```

## Next Steps

1. **Weekly Reviews**: Check load test results in CI/CD
2. **Monthly Analysis**: Identify trends and optimization opportunities
3. **Quarterly Stress Tests**: Validate capacity planning assumptions
4. **Post-Deployment**: Run load test after major releases
5. **Incident Response**: Load test to isolate performance issues

## References

- [k6 Documentation](https://k6.io/docs/)
- [Load Testing Best Practices](https://k6.io/docs/testing-guides/load-testing-best-practices/)
- [Thresholds and Assertions](https://k6.io/docs/javascript-api/k6/test-details-object/)
- [Grafana Visualization](https://k6.io/docs/visualizing-results/)
