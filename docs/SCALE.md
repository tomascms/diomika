# Escala (€0 → quando doer)

Stack escolhido: Sentry + Axiom + PostHog + UptimeRobot + R2 (imagens) + Supabase (BD).

## Já no código

- Sentry / Axiom / PostHog / alerta latência / anomaly login  
- Storage auto-R2 se `R2_*` existirem  
- `verify_production.py` (smoke + security + load + e2e)

## Quando crescer de verdade

1. Budget alerta GCP $1–5  
2. Mais workers / upgrade Supabase se CPU BD alta  
3. Self-host Postgres só com runbook — não é o próximo passo  
