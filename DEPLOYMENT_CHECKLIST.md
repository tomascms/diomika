# Deployment Checklist — Production Release

**Release Version**: [VERSION]
**Date**: [DATE]
**Deployer**: [NAME]
**Reviewer**: [NAME]

---

## Pre-Deployment (24h before)

### Code Quality
- [ ] All tests passing locally (`pytest tests/ -v`)
- [ ] Code coverage > 80% (`pytest --cov`)
- [ ] Linting passes (`black`, `isort`, `pylint`)
- [ ] Security scan clean (`bandit`, `safety`)
- [ ] No TODO/FIXME in production code

### Branch & CI/CD
- [ ] Feature branch code reviewed and approved (2+ reviewers)
- [ ] All CI checks passing on GitHub Actions
- [ ] Docker image built and tagged (`v[VERSION]`)
- [ ] Docker image security scan clean (Trivy)
- [ ] Helm chart validated (`helm lint k8s/helm`)

### Database
- [ ] Migration script tested locally
- [ ] Migration backwards-compatible (can rollback)
- [ ] Database backups scheduled
- [ ] Backup tested (restore validation)
- [ ] no breaking schema changes in peak hours

### Documentation
- [ ] CHANGELOG.md updated
- [ ] API documentation updated (if endpoints changed)
- [ ] Runbook updated (if operational procedures changed)
- [ ] Team notified of deployment window

---

## 6 Hours Before Deployment

### Communication
- [ ] Slack notification sent to #deployments
- [ ] Alert team of deployment window (XX:XX - XX:XX UTC)
- [ ] Customers notified if downtime expected
- [ ] On-call team ready for rollback

### Infrastructure
- [ ] Staging deployment successful
- [ ] Smoke tests passed on staging
- [ ] Resource quotas checked (CPU, memory, disk)
- [ ] Load balancer health checks configured
- [ ] Backup database snapshot taken

### Monitoring
- [ ] Grafana dashboards loaded
- [ ] AlertManager rules active
- [ ] Prometheus scrape config validated
- [ ] PagerDuty integration verified
- [ ] Slack alerts channel monitored

---

## Deployment Day (During Window)

### Pre-Flight (15min before)
- [ ] Production database backup started
- [ ] Current metrics baseline captured (Prometheus snapshot)
- [ ] All team on call bridge ready
- [ ] Incident response procedure reviewed
- [ ] Rollback plan confirmed

### Deployment (Staging → Canary → Prod)

**Stage 1: Canary Deployment (10% traffic)**
```bash
kubectl patch deployment diomika-api -p \
  '{"spec":{"replicas":2}}' -n diomika-prod
```

- [ ] Canary pods healthy (`kubectl get pods -n diomika-prod`)
- [ ] Logs show no errors
- [ ] Metrics normal (error rate < 1%)
- [ ] Customer complaints received? (Monitor Slack)

**Stage 2: Progressive Rollout (50% traffic)**
```bash
kubectl patch deployment diomika-api -p \
  '{"spec":{"replicas":5}}' -n diomika-prod
```

- [ ] Wait 5 minutes for stabilization
- [ ] Error rate remains < 1%
- [ ] Latency within SLA (P95 < 2s)
- [ ] No database connection errors
- [ ] Cache hit rate > 60%

**Stage 3: Full Deployment (100% traffic)**
```bash
kubectl patch deployment diomika-api -p \
  '{"spec":{"replicas":10}}' -n diomika-prod
```

- [ ] All replicas healthy
- [ ] Traffic fully switched
- [ ] Error rate < 0.5%
- [ ] Latency normal
- [ ] All integration tests passing

### Post-Deployment (30min after)

- [ ] API responding to requests
- [ ] Database queries performing normally
- [ ] No alerts firing
- [ ] Log aggregation shows clean operation
- [ ] Business metrics tracking (orders/hour, revenue)
- [ ] Third-party integrations working (email, payment, etc.)
- [ ] Customer feedback positive

### Validation Tests

Run automated validation:
```bash
# Health checks
curl -f https://api.diomika.com/health

# Smoke tests
pytest backend-api/tests/test_smoke.py

# Quick load test (5 min)
k6 run backend-api/tests/test_load_k6.js \
  --duration 5m \
  --vus 10

# API version check
curl -H "X-API-Version: 2.0" https://api.diomika.com/api/v2/catalog | jq .

# Database connectivity
curl https://api.diomika.com/admin/orders -H "Authorization: Bearer ${TOKEN}"
```

---

## Rollback Plan (If Needed)

### Automatic Rollback Triggers

**Immediately rollback if any of**:
- Error rate > 5% for > 2 minutes
- API down completely (0% traffic)
- Database connection failures
- Critical security vulnerability found
- Confirmed data corruption

### Manual Rollback Procedure

```bash
# Immediate: Revert deployment
kubectl rollout undo deployment/diomika-api -n diomika-prod

# Wait for rollback
kubectl rollout status deployment/diomika-api -n diomika-prod --timeout=5m

# Verify health
curl -f https://api.diomika.com/health

# Confirm previous version
curl https://api.diomika.com/version

# Alert team
# Post in #incident-response: "Rollback completed to v[PREVIOUS_VERSION]"
```

### Database Rollback (If Schema Changed)

```bash
# Backup current data
pg_dump diomika_prod > /backups/diomika_prod_$(date +%s).sql

# Restore previous migration
cd backend-api
alembic downgrade -1  # Go back 1 migration
alembic upgrade head  # Verify schema consistency
```

---

## Post-Deployment (24h after)

### Validation
- [ ] No errors in logs over 24h period
- [ ] Alert firing frequency normal
- [ ] Customer reported issues: NONE
- [ ] Database performance normal
- [ ] Cache hit rate stable (> 60%)
- [ ] Cost metrics normal (no unexpected scaling)

### Analysis
- [ ] Review deployment metrics (duration, resource usage)
- [ ] Collect performance data (before vs after)
- [ ] Analyze audit logs for anomalies
- [ ] Check for new errors/warnings in logs

### Sign-off
- [ ] Deployment successful sign-off by SRE
- [ ] Product team confirmation
- [ ] Customers notified (if communication sent)
- [ ] Slack update: Deployment complete ✅

### Documentation
- [ ] Deployment notes added to CHANGELOG
- [ ] Incident report (if any issues occurred)
- [ ] Lessons learned documented
- [ ] Performance improvements documented

---

## Emergency Contacts

| Role | Name | Slack | Email |
|------|------|-------|-------|
| SRE Lead | [NAME] | @[slack] | [email] |
| On-Call | [ROTATION] | @on-call | oncall@diomika.com |
| CTO | [NAME] | @[slack] | [email] |
| CEO | [NAME] | @[slack] | [email] |

---

## Deployment Approval Sign-Off

I certify that:
- All checks passed
- Code reviewed and tested
- Database migration tested
- Rollback plan confirmed
- Team ready for deployment

**Deployer Name**: _________________________ **Date**: _______

**Reviewer Name**: _________________________ **Date**: _______

**SRE Lead Name**: _________________________ **Date**: _______

---

## Deployment Timeline Log

```
[HH:MM] Pre-deployment verification: STARTED
[HH:MM] Database backup: COMPLETED
[HH:MM] Canary deployment: STARTED (v[VERSION])
[HH:MM] Canary health: OK
[HH:MM] Progressive rollout: STARTED
[HH:MM] Full deployment: STARTED
[HH:MM] Smoke tests: PASSED
[HH:MM] Validation: PASSED
[HH:MM] Deployment: COMPLETE ✅
```

---

## Related Documents

- [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md) — Daily operations procedures
- [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md) — Disaster recovery procedures
- [SECURITY_ARCHITECTURE_ROADMAP.md](./SECURITY_ARCHITECTURE_ROADMAP.md) — Security procedures
- [.github/workflows/ci.yml](./.github/workflows/ci.yml) — CI/CD pipeline configuration

---

**Version**: 1.0  
**Last Updated**: 2026-10-02  
**Maintained By**: SRE Team
