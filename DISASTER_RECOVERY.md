# Disaster Recovery Documentation

## Objetivos

- RTO (Recovery Time Objective): 30 minutos
- RPO (Recovery Point Objective): 5 minutos
- Disponibilidade: 99.9% SLA

## 1. Estratégia de Backup

### 1.1 Database Backups

**Frequency**: Contínuo com snapshots a cada 5 minutos

```bash
# Manual backup
supabase db push --linked

# Scheduled backups (via Supabase)
- Daily full backups
- Hourly incremental backups
- 30-day retention
```

**Teste de Restauração**: Semanal

### 1.2 Application State

- Redis snapshots: a cada 10 minutos
- Outbox events: persistidas em database
- Audit trail: completo em database

### 1.3 Storage Backups

- S3/R2 backups: Replicação cross-region
- Versioning ativado
- 90-day retention

## 2. Recovery Procedures

### 2.1 Application Failure

**Cenário**: Pod falha

**Ação**:
```bash
# Kubernetes auto-recovery
kubectl rollout restart deployment/diomika-api

# Manual check
kubectl get pods -l app=diomika-api
kubectl logs <pod-name>
```

**RTO**: < 2 minutos

### 2.2 Database Failure

**Cenário**: Supabase database indisponível

**Ação**:
```bash
# 1. Verificar status
curl https://api.diomika.com/health/detail

# 2. Restaurar do backup
supabase db restore --backup-ref <backup-id>

# 3. Verificar integridade
pytest tests/test_database_integrity.py
```

**RTO**: 10-15 minutos

### 2.3 Cache Failure

**Cenário**: Redis indisponível

**Ação**:
```bash
# 1. Cache é opcional - aplicação continua funcionando
# 2. Warm up cache manualmente
curl -X POST https://api.diomika.com/admin/cache/warmup

# 3. Monitor performance
grep "cache_misses_total" /metrics
```

**RTO**: < 5 minutos

### 2.4 Cluster Failure

**Cenário**: Múltiplos nós Kubernetes falham

**Ação**:
```bash
# 1. Blue-green deployment
kubectl patch service diomika-api -p '{"spec":{"selector":{"version":"green"}}}'

# 2. Validar tráfego
curl -v https://api.diomika.com/health

# 3. Rollback se necessário
kubectl patch service diomika-api -p '{"spec":{"selector":{"version":"blue"}}}'
```

**RTO**: < 30 minutos

## 3. Data Consistency

### 3.1 Transaction Log

```sql
-- Verificar status das transações
SELECT * FROM schema_migrations;
SELECT * FROM outbox;

-- Compensar transações não confirmadas
UPDATE outbox SET processed_at = NOW() 
WHERE processed_at IS NULL AND created_at < NOW() - INTERVAL '1 hour';
```

### 3.2 Event Sourcing

```python
# Reconstruir estado a partir de eventos
from core.saga_coordinator import get_saga_orchestrator

orchestrator = get_saga_orchestrator()
saga = orchestrator.get_saga_status(saga_id)
# Replay events if needed
```

## 4. Network Failover

### 4.1 DNS Failover

```yaml
# Cloudflare DNS configuration
api.diomika.com:
  Primary:    api-primary.diomika.com (GCP)
  Secondary:  api-secondary.diomika.com (Backup)
  Fallback:   api-emergency.diomika.com (Minimal)
```

### 4.2 Geographic Failover

```bash
# Switch to secondary region
terraform apply -var="primary_region=us-central1" -var="active_region=secondary"

# Update DNS
gcloud compute backend-services update api-service --global \
  --enable-cdn --cache-mode CACHE_ALL_STATIC
```

**RTO**: 5-10 minutos

## 5. Validation & Testing

### 5.1 Restore Test

```bash
#!/bin/bash
# Monthly restore test

# 1. Create test database
psql -c "CREATE DATABASE diomika_restore_test"

# 2. Restore from backup
pg_restore -d diomika_restore_test backup.sql

# 3. Run integrity tests
pytest tests/test_restore_integrity.py

# 4. Clean up
psql -c "DROP DATABASE diomika_restore_test"

# 5. Report results
echo "Restore test: PASSED" | mail -s "DR Test Results" team@diomika.com
```

### 5.2 Failover Drill

```bash
#!/bin/bash
# Quarterly failover drill

# 1. Notify stakeholders
curl -X POST https://slack.com/api/chat.postMessage \
  -d "channel=ops&text=Starting DR failover drill"

# 2. Switch to secondary
kubectl apply -f k8s/secondary-cluster-config.yaml

# 3. Validate
for endpoint in /health /catalog /health/ready; do
  curl -f https://api.diomika.com$endpoint || exit 1
done

# 4. Switch back
kubectl apply -f k8s/primary-cluster-config.yaml

# 5. Report
echo "Failover drill: PASSED (${DURATION}s)" | mail -s "DR Drill Results" team@diomika.com
```

## 6. Communication Plan

### 6.1 Incident Escalation

```
Level 1 (< 5 min outage):
  - Automated recovery attempted
  - No notification required

Level 2 (5-30 min outage):
  - Notify #ops Slack channel
  - Trigger on-call engineer

Level 3 (> 30 min outage):
  - Page VP Engineering
  - Notify customers
  - Activate war room
```

### 6.2 Status Page

```bash
# Update public status
curl -X POST https://status.diomika.com/api/incidents \
  -d '{
    "name": "Database Maintenance",
    "status": "investigating",
    "impact": "major",
    "components": ["api", "database"]
  }'
```

## 7. Post-Incident Review

### 7.1 Runbook Update

```markdown
## Incident Postmortem
- **Date**: 2024-10-01
- **Duration**: 15 minutes
- **Root Cause**: Database connection pool exhausted
- **Action Items**:
  - Increase connection pool size (DONE)
  - Add alerting for connection count (DONE)
  - Load test with new limits (SCHEDULED)
```

### 7.2 Metrics & Monitoring

```python
# Track DR metrics
dr_metrics = {
    "rto_actual": 12,  # minutes
    "rpo_actual": 2,   # minutes
    "detection_time": 2,  # minutes
    "resolution_time": 10,  # minutes
    "success": True,
}
```

## 8. Checklists

### 8.1 Pre-Incident Checklist

- [ ] Backup systems operational
- [ ] Failover DNS configured
- [ ] Secondary infrastructure ready
- [ ] Team trained on procedures
- [ ] Communication templates prepared
- [ ] Monitoring alerts configured

### 8.2 During-Incident Checklist

- [ ] Acknowledge incident
- [ ] Assess severity
- [ ] Activate response team
- [ ] Begin recovery procedure
- [ ] Update status page
- [ ] Monitor progress
- [ ] Validate recovery

### 8.3 Post-Incident Checklist

- [ ] Verify all systems operational
- [ ] Restore backups to secondary
- [ ] Document incident details
- [ ] Conduct postmortem
- [ ] Update runbooks
- [ ] Schedule follow-up training

## 9. Tools & Contacts

### 9.1 Emergency Contacts

```
On-Call Engineer:    +1-555-0100 / oncall@diomika.com
VP Engineering:      +1-555-0101 / vp@diomika.com
Database Admin:      +1-555-0102 / dba@diomika.com
Infrastructure:      #ops-emergency (Slack)
```

### 9.2 Recovery Tools

- **Supabase CLI**: `npm install -g supabase`
- **kubectl**: `kubectl version`
- **Terraform**: `terraform version`
- **Prometheus**: `http://prometheus:9090`
- **Logs**: `journalctl -u diomika-api -n 1000`

## 10. Compliance

- **Regulatory Requirements**: GDPR, CCPA
- **Data Retention**: 90 days
- **Backup Testing**: Monthly
- **Disaster Drills**: Quarterly
- **Documentation**: Updated weekly

---

**Last Updated**: 2024-10-02  
**Next Review**: 2024-11-02  
**Owner**: Infrastructure Team
