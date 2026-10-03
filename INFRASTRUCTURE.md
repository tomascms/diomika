# Infrastructure & Deployment Guide

Complete infrastructure setup for Diomika e-commerce platform with Kubernetes, observability, security, and disaster recovery.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Kubernetes Cluster                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Ingress (nginx) - TLS, Rate Limiting, Load Balancing      │   │
│  └──────────────┬───────────────────────────────────────────┘   │
│                 │                                                │
│  ┌──────────────▼───────────────────────────────────────────┐   │
│  │ API Service (Diomika)                                    │   │
│  │ - FastAPI + Uvicorn (multiple workers)                  │   │
│  │ - CQRS pattern (Commands/Queries)                       │   │
│  │ - Saga pattern (distributed transactions)               │   │
│  │ - Background workers (email, outbox, sagas)             │   │
│  │ - Request context, audit logging, rate limiting         │   │
│  └──────────────┬──────────────────┬──────────────────┬────┘   │
│                 │                  │                  │         │
│  ┌──────────────▼──┐  ┌────────────▼──┐  ┌──────────▼─┐        │
│  │  PostgreSQL     │  │  Redis Cache  │  │ RabbitMQ  │        │
│  │  (Events, Data) │  │  (Sessions)   │  │  (Queue)  │        │
│  └─────────────────┘  └───────────────┘  └───────────┘        │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Observability Stack                                         │ │
│  │ ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐ │ │
│  │ │ Prometheus │ │ Grafana  │ │ Loki     │ │ AlertManager │ │ │
│  │ │ (Metrics)  │ │(Dashbrd) │ │ (Logs)   │ │ (Alerting)   │ │ │
│  │ └────────────┘ └──────────┘ └──────────┘ └──────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Deployment Environments

### Development
- Local Kubernetes (minikube, Docker Desktop)
- SQLite/PostgreSQL (local)
- Redis (optional)
- 1-3 replicas
- No ingress, port-forward instead

### Staging
- AWS EKS (2 node group, 3-6 nodes)
- RDS PostgreSQL (db.t3.medium)
- ElastiCache Redis (cache.t3.small)
- 2 replicas minimum, 5 maximum
- Self-signed TLS or staging Let's Encrypt

### Production
- AWS EKS (3+ node groups, 10-50 nodes)
- RDS PostgreSQL (db.r5.xlarge, Multi-AZ)
- ElastiCache Redis Cluster (cache.r5.xlarge, Multi-AZ)
- 3 replicas minimum, 20 maximum
- Let's Encrypt TLS, Wildcard certificate
- CloudFront CDN for static assets

## Helm Deployment

### Chart Structure
```
helm/
├── Chart.yaml                  # Chart metadata
├── values.yaml                 # Default values
├── values-staging.yaml         # Staging overrides
├── values-production.yaml       # Production overrides
└── templates/
    ├── deployment.yaml         # Pod spec
    ├── service.yaml            # Service definition
    ├── ingress.yaml            # Ingress rules
    ├── configmap.yaml          # Configuration
    ├── secret.yaml             # Secrets (injected)
    ├── hpa.yaml                # Autoscaling
    ├── pdb.yaml                # Pod disruption budget
    ├── serviceaccount.yaml      # RBAC
    └── _helpers.tpl            # Template helpers
```

### Deployment Commands

```bash
# Development
helm install diomika ./helm \
  --namespace diomika \
  --create-namespace \
  --values helm/values.yaml

# Staging
helm upgrade --install diomika ./helm \
  --namespace diomika-staging \
  --create-namespace \
  --values helm/values.yaml \
  --values helm/values-staging.yaml \
  --set secrets.databasePassword=$DB_PASSWORD

# Production
helm upgrade --install diomika ./helm \
  --namespace diomika-prod \
  --create-namespace \
  --values helm/values.yaml \
  --values helm/values-production.yaml \
  --values helm/secrets-prod.yaml \  # External secrets
  --wait \
  --timeout 10m
```

## Kubernetes Configuration

### Namespaces
```yaml
# development
kubectl create namespace diomika
kubectl label namespace diomika environment=development

# staging
kubectl create namespace diomika-staging
kubectl label namespace diomika-staging environment=staging

# production
kubectl create namespace diomika-prod
kubectl label namespace diomika-prod environment=production
```

### Network Policies
```yaml
# Restrict ingress/egress per namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: diomika-api-policy
  namespace: diomika-prod
spec:
  podSelector:
    matchLabels:
      app: diomika
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: ingress-nginx
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: default
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - protocol: TCP
          port: 5432
```

### Resource Quotas
```yaml
# Prevent resource starvation
apiVersion: v1
kind: ResourceQuota
metadata:
  name: diomika-prod-quota
  namespace: diomika-prod
spec:
  hard:
    requests.cpu: "100"
    requests.memory: "200Gi"
    limits.cpu: "200"
    limits.memory: "400Gi"
    pods: "100"
```

## Observability Stack

### Prometheus Configuration
```yaml
# k8s/prometheus-rules.yml
- name: API Performance
  rules:
    - alert: HighErrorRate
      expr: rate(http_requests_failed[5m]) > 0.05
      for: 5m
    - alert: SlowAPI
      expr: histogram_quantile(0.95, http_request_duration) > 1
      for: 5m

- name: Database
  rules:
    - alert: SlowQueries
      expr: rate(db_query_slow[5m]) > 0.1
    - alert: DatabaseDown
      expr: pg_stat_activity_count == 0

- name: Infrastructure
  rules:
    - alert: HighCPU
      expr: rate(node_cpu[5m]) > 0.8
    - alert: HighMemory
      expr: (1 - node_memory_available / node_memory_total) > 0.85
```

### Grafana Dashboards
- **API Performance**: Requests, latency, errors by endpoint
- **Database**: Query rate, latency, connections, cache hit rate
- **Business Metrics**: Orders, revenue, conversion rate
- **Infrastructure**: CPU, memory, disk, network I/O

### Log Aggregation (Loki)
```yaml
# backend-api/core/logging.py
logging.config:
  version: 1
  formatters:
    json:
      class: pythonjsonlogger.jsonlogger.JsonFormatter
      format: "%(asctime)s %(name)s %(levelname)s %(message)s"
  handlers:
    loki:
      class: logging_loki.LokiHandler
      url: http://loki:3100/loki/api/v1/push
      tags:
        app: diomika
        environment: production
```

## Security

### TLS/SSL
```bash
# Let's Encrypt with cert-manager
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: security@diomika.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

### Secrets Management
```bash
# Use sealed-secrets for encrypted GitOps
brew install sealed-secrets

# Create secret
kubectl create secret generic diomika-secrets \
  --from-literal=db-password=$DB_PASSWORD \
  --from-literal=jwt-secret=$JWT_SECRET \
  -o yaml | kubeseal -f - > sealed-secret.yaml

# Apply sealed secret
kubectl apply -f sealed-secret.yaml
```

### RBAC
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: diomika-api
spec:
  rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: diomika-api-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: diomika-api
subjects:
- kind: ServiceAccount
  name: diomika
```

## Disaster Recovery

### Backup Strategy

**Database Backups:**
```bash
# Daily automated snapshots (AWS RDS)
- Retention: 30 days (production), 7 days (staging)
- Multi-region replication for production
- Point-in-time recovery enabled

# Restore procedure
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier diomika-restored \
  --db-snapshot-identifier diomika-snapshot-2024-01-15

# Verify restore
psql -h restored-instance.rds.amazonaws.com -U postgres -d diomika < /dev/null
```

**Kubernetes Backups:**
```bash
# Velero for cluster-level backups
velero backup create diomika-backup-$(date +%Y%m%d)

# List backups
velero backup get

# Restore from backup
velero restore create --from-backup diomika-backup-20240115
```

### RTO/RPO Targets
- **RTO** (Recovery Time Objective): 1 hour
- **RPO** (Recovery Point Objective): 15 minutes
- Achieved through: continuous RDS snapshots, Velero backups

### Failover Procedure
```bash
# 1. Promote read replica to primary
aws rds promote-read-replica --db-instance-identifier diomika-read-replica

# 2. Update connection strings
kubectl patch secret diomika-secrets \
  -p '{"data":{"database-host":"'$(echo -n "new-primary.rds.amazonaws.com" | base64)'}}'

# 3. Verify connectivity
kubectl run debug --image=postgres:16 -- psql -h new-primary.rds.amazonaws.com -U postgres -c "SELECT 1"

# 4. Update DNS
aws route53 change-resource-record-sets --hosted-zone-id Z123 \
  --change-batch '{"Changes":[{"Action":"UPSERT","ResourceRecordSet":{"Name":"db.diomika.com","Type":"CNAME","TTL":60,"ResourceRecords":[{"Value":"new-primary.rds.amazonaws.com"}]}}]}'
```

## Monitoring & Alerting

### Alert Routing (AlertManager)
```yaml
# k8s/alertmanager-config.yml
receivers:
  - name: 'critical'
    slack_configs:
      - channel: '#critical-alerts'
    pagerduty_configs:
      - service_key: $PAGERDUTY_SERVICE_KEY

  - name: 'database-team'
    email_configs:
      - to: 'dba@diomika.com'

  - name: 'security-team'
    email_configs:
      - to: 'security@diomika.com'

routes:
  - match:
      severity: critical
    receiver: 'critical'
    continue: true
  
  - match:
      team: database
    receiver: 'database-team'
```

### Incident Response

**On-Call Rotation:**
- 24/7 coverage via PagerDuty
- Primary on-call: 1 week
- Secondary on-call: 1 week

**Escalation Policy:**
1. Alert triggered
2. PagerDuty notifies primary (5 min timeout)
3. Escalate to secondary if not acknowledged
4. Escalate to team lead if not resolved (30 min)

## Cost Optimization

### Resource Right-Sizing
```bash
# Get current resource usage recommendations
kubectl get vpa diomika-api -o yaml

# Example output:
# - containerName: diomika
#   lowerBound:
#     cpu: 100m
#     memory: 256Mi
#   target:
#     cpu: 250m
#     memory: 512Mi
#   uncappedTarget:
#     cpu: 200m
#     memory: 480Mi
```

### Savings Opportunities
- Reserved instances: 40% savings vs on-demand
- Spot instances: 70% savings (non-critical workloads)
- RDS savings plans: 30-40% savings
- CloudFront for static assets: 80% CDN bandwidth savings

### Cost Monitoring
```bash
# AWS Cost Explorer
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

## References

- Kubernetes: https://kubernetes.io/docs/
- Helm: https://helm.sh/docs/
- Prometheus: https://prometheus.io/docs/
- Grafana: https://grafana.com/docs/
- AlertManager: https://prometheus.io/docs/alerting/alertmanager/
- EKS Best Practices: https://aws.github.io/aws-eks-best-practices/
