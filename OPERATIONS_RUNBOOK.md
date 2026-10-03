# Diomika API — Operations Runbook

**Last Updated**: 2026-10-02
**Environment**: Production (GCP e2-micro + Cloudflare Tunnel)

---

## 1. Alert Response Procedures

### 1.1 Critical Alert: High Error Rate

**Alert**: `HighErrorRate` (>5% errors in 5m window)

**Response**:
1. Check real-time logs in Grafana → Loki
   ```bash
   curl -G http://localhost:3100/loki/api/v1/query_range \
     -d 'query=logs for "ERROR"' \
     -d 'start=now-30m'
   ```
2. Identify error pattern (500, 503, 504, timeout)
3. **If Database errors**: Check Postgres connection pool
   ```sql
   SELECT count(*) FROM pg_stat_activity WHERE state = 'active';
   SELECT max_conn FROM pg_settings WHERE name = 'max_connections';
   ```
4. **If Timeout errors**: Check external service dependencies (Supabase, Redis)
5. Run incident protocol (see section 3.0)

**Escalation**:
- If unresolved > 5min: Page SRE on-call
- If > 10% errors: Declare P1 incident

---

### 1.2 Alert: High Latency

**Alert**: `HighLatency` (P95 > 2s)

**Response**:
1. Check Prometheus metrics for slow endpoints
   ```bash
   curl 'http://localhost:9090/api/v1/query?query=topk(5, rate(http_request_duration_seconds_bucket[5m]))'
   ```
2. Check database query performance
   ```bash
   # In Supabase dashboard:
   # → Performance → Slow Queries
   ```
3. Check cache hit rate in Grafana
4. **If low cache hits**: Trigger cache warmup
   ```bash
   curl -X POST http://localhost:8001/admin/system/cache-warmup
   ```
5. **If specific endpoint slow**: Check for N+1 queries or missing indexes

**Resolution**:
- Scale horizontally (add more API instances)
- Optimize slow database queries
- Increase cache TTL

---

### 1.3 Alert: Database Connection Pool Exhausted

**Alert**: `DatabaseConnectionPoolExhausted` (connections < 2)

**Response** (IMMEDIATE):
1. Stop accepting new connections
   ```bash
   # Mark service as degraded
   kubectl scale deployment diomika-api --replicas=0 -n diomika-prod
   ```
2. Check connection leaks
   ```sql
   SELECT pid, usename, state, state_change, query 
   FROM pg_stat_activity 
   ORDER BY state_change DESC 
   LIMIT 10;
   ```
3. Kill idle connections (if safe)
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle' AND query_start < now() - interval '10 min';
   ```
4. Restart API service
   ```bash
   kubectl rollout restart deployment/diomika-api -n diomika-prod
   ```

---

### 1.4 Alert: Saga Compensation Failure

**Alert**: `SagaCompensationFailure` (failures detected)

**Response**:
1. Check saga logs in Loki
   ```bash
   # Look for "compensation" events
   curl -G http://localhost:3100/loki/api/v1/query_range \
     -d 'query={job="diomika-saga"} | "compensation" | "failed"'
   ```
2. Identify affected saga type (order, orcamento, contact)
3. Check Dead Letter Queue (DLQ) for failed events
4. **For Order Sagas**:
   ```sql
   SELECT order_id, saga_id, error_message, created_at
   FROM saga_dlq 
   WHERE saga_type = 'order_saga' 
   ORDER BY created_at DESC 
   LIMIT 10;
   ```
5. Manual remediation:
   - Check if order was partially created
   - Restore inventory if reserved
   - Send compensation email to customer

**Prevention**:
- Increase saga timeout thresholds
- Improve idempotency keys

---

## 2. Common Operations

### 2.1 Reboot Production API

```bash
# Graceful restart (wait for in-flight requests)
kubectl rollout restart deployment/diomika-api -n diomika-prod --timeout=5m

# Verify health
kubectl get pods -n diomika-prod -l app=diomika-api
curl -f https://api.diomika.com/health
```

### 2.2 View Recent Logs

```bash
# Last 100 logs
kubectl logs -n diomika-prod deployment/diomika-api -f --tail=100

# Logs from specific time range
stern -n diomika-prod diomika-api --since=10m

# Filter by level
kubectl logs -n diomika-prod deployment/diomika-api | grep "ERROR"
```

### 2.3 Check Resource Usage

```bash
# CPU, Memory, Network
kubectl top nodes
kubectl top pods -n diomika-prod

# Detailed metrics
curl http://localhost:9090/api/v1/query?query='up{job="diomika-api"}'
```

### 2.4 Manual Cache Clear

```bash
# Warm specific catalog
curl -X POST http://localhost:8001/admin/system/cache-warmup \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"

# Clear all cache
redis-cli -h redis.default.svc.cluster.local FLUSHALL
```

### 2.5 Database Backups

```bash
# Manual backup to S3
cd /home/user/diomika
python deploy/backup_database.py --env=production --target=s3://diomika-backups

# List recent backups
aws s3 ls s3://diomika-backups/ --recursive --human-readable --summarize

# Restore from backup
python deploy/restore_database.py --env=production --backup=backup-2026-10-02.sql.gz
```

---

## 3. Incident Protocol

### 3.1 Incident Declaration

**When to declare**:
- Error rate > 10% for > 2 minutes
- API down (>50% requests failing)
- Data corruption detected

**Steps**:
1. Create incident in incident tracking system
   ```bash
   # Slack: /incident create "API high error rate" #incident-response
   ```
2. Add to bridge call (Zoom link in Slack)
3. Assign commander and scribe

### 3.2 Investigation Checklist

- [ ] Confirm problem scope (all endpoints or specific?)
- [ ] Check recent deployments (rollback if needed)
- [ ] Review error logs and metrics
- [ ] Check external dependencies status
- [ ] Review on-call schedule (did someone make changes?)
- [ ] Check database connection/lock status
- [ ] Review recent firewall/network changes

### 3.3 Remediation Steps

**If recent deployment caused issue**:
```bash
# Rollback to previous version
kubectl rollout undo deployment/diomika-api -n diomika-prod
kubectl rollout status deployment/diomika-api -n diomika-prod
```

**If database is slow**:
```bash
# Restart DB (if in control)
# Or: Scale down API to reduce query load
kubectl scale deployment diomika-api --replicas=2 -n diomika-prod
```

**If memory leak detected**:
```bash
# Force pod restart
kubectl delete pod -n diomika-prod -l app=diomika-api
```

### 3.4 Post-Incident

- [ ] Write incident report (5-Whys root cause analysis)
- [ ] Schedule follow-up meeting within 24h
- [ ] Create tickets for preventive improvements
- [ ] Update runbook if procedures changed

---

## 4. Performance Tuning

### 4.1 Database Query Optimization

```sql
-- Find slow queries
SELECT 
  query,
  calls,
  mean_time,
  max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Add missing indexes
CREATE INDEX CONCURRENTLY idx_orders_customer_email 
ON orders(customer_email);

-- Analyze table
ANALYZE orders;
```

### 4.2 Cache Strategy

```python
# Warm cache at startup
python -c "from core.cache_warmup import warm_catalog_cache; warm_catalog_cache()"

# Monitor cache effectiveness
curl http://localhost:9090/api/v1/query?query=cache_hit_rate
```

### 4.3 Load Balancing

```bash
# Adjust replica count based on traffic
kubectl scale deployment diomika-api --replicas=5 -n diomika-prod

# Check pod distribution
kubectl get pods -n diomika-prod -o wide
```

---

## 5. Security Checks

### 5.1 Monthly Security Review

```bash
# Check for vulnerabilities
safety check
bandit -r backend-api/

# Rotate secrets
kubectl create secret generic api-secrets --from-file=.env -n diomika-prod --dry-run=client -o yaml | kubectl apply -f -
```

### 5.2 Access Audit

```sql
-- Who accessed sensitive tables?
SELECT user_id, action, entity_id, created_at
FROM audit_log
WHERE action IN ('DELETE', 'HARD_DELETE', 'EXPORT')
ORDER BY created_at DESC
LIMIT 50;
```

### 5.3 Network Policy

```bash
# Verify ingress rules
kubectl get networkpolicies -n diomika-prod

# Test connectivity
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl http://diomika-api.diomika-prod.svc.cluster.local:8001/health
```

---

## 6. Disaster Recovery

### 6.1 Complete Restore Procedure

See `DISASTER_RECOVERY.md` for full procedures including:
- Database restore
- Cached data reconstruction
- Event sourcing replay
- API redeployment

### 6.2 Critical Contact List

- **On-Call Engineer**: [Slack @on-call]
- **SRE Lead**: [Email: sre@diomika.com]
- **Database Admin**: [Email: dba@diomika.com]
- **Security Officer**: [Email: security@diomika.com]

---

## 7. Monitoring Dashboard

**Primary**: https://grafana.diomika.com (login via SSO)

**Key Dashboards**:
- API Overview (throughput, latency, errors)
- Database (queries, connections, locks)
- Infrastructure (CPU, memory, disk)
- Business Metrics (orders/hour, revenue)
- Security (failed logins, suspicious activity)

**Alert Channel**: #monitoring in Slack

---

## Appendix A: Common Commands

```bash
# SSH into pod for debugging
kubectl exec -it deployment/diomika-api -n diomika-prod -- /bin/bash

# Port forward to local machine
kubectl port-forward svc/diomika-api 8001:8001 -n diomika-prod

# View environment variables
kubectl set env deployment/diomika-api --list -n diomika-prod

# Check recent events
kubectl describe deployment diomika-api -n diomika-prod

# Update configuration
kubectl edit configmap diomika-config -n diomika-prod
```

---

**Document Version**: 1.0
**Last Reviewed**: 2026-10-02
**Next Review**: 2026-11-02
