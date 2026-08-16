# Operações — Diomika

Stack canónico (sem duplicados): ver `APRESENTACAO_CLIENTE.md`.

## Comando único

```powershell
python deploy/verify_production.py
```

## Env essenciais

```
SENTRY_DSN=                 # erros
AXIOM_TOKEN=                # logs
AXIOM_DATASET=diomika
AXIOM_API_URL=https://eu-central-1.aws.edge.axiom.co  # EU edge ingest
VITE_POSTHOG_KEY=           # analytics loja (Pages)
VITE_POSTHOG_HOST=https://eu.i.posthog.com
ALERT_WEBHOOK_URL=          # Slack/Discord
ALERT_LATENCY_MS=2000       # default
R2_ACCOUNT_ID=              # opcional; se preenchido + keys → imagens em R2
```

## Incidentes

1. Cloudflare Under Attack se preciso  
2. Rodar secrets afectados  
3. `python deploy/deploy_vm.py`  
4. Privacy erase se PII  
5. Sentry + Axiom + webhook para evidência  

## Backup Supabase

**Política:** backups automáticos diários (plano Free Supabase) + restore manual documentado.

**Frequência recomendada:**
- Verificar backups no dashboard Supabase — mensal
- **Restore drill** — trimestral (calendário: Jan, Abr, Jul, Out)

**Procedimento restore drill (resumo):**
1. Supabase Dashboard → Project → Database → Backups
2. Criar branch de teste ou project staging (nunca restore directo em prod sem janela)
3. Restaurar snapshot num branch
4. Validar: `categories` visíveis, RLS activo, login admin funciona
5. Apagar branch de teste

**Último check documentado:** 2026-08-10 · **Próximo drill:** 2026-11-01

**Dados críticos:** catálogo, pedidos orçamento, mensagens contacto — retenção automática em `core/retention.py`.
