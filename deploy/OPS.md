# Operações de segurança — Diomika (€0)

Playbook curto. Admin só no PC local; API pública via Tunnel; loja em Pages.

## 1. Incident response

| Severidade | Exemplos | Acção |
|------------|----------|--------|
| P1 | API down, vazamento de secrets, WAF bypass em `/admin` | Isolar + rodar secrets + status |
| P2 | Spike 5xx, brute-force login, rate-limit saturado | Verificar logs/alertas + mitigar |
| P3 | CSP/observability, bug UI | Corrigir em horário normal |

### Passos P1 (secrets ou acesso indevido)

1. Cloudflare: modo “Under Attack” / bloquear path se necessário.
2. Rodar: `SUPABASE_KEY`, `API_SECRET_KEY`, `API_*_KEY`, Turnstile, mail app password, tunnel token (ver `SECRETS_ROTATION` mental: gerar novos no painel + actualizar `.env` na VM).
3. Redeploy VM: `python deploy/deploy_vm.py`
4. `POST /admin/privacy/erase` (só role admin, localhost) se PII afectada.
5. Registar no `deploy/alerts.log` / webhook o que aconteceu.

Contacto: dono do projecto (single-operator). Sem SOC externo — alertas via `ALERT_WEBHOOK_URL`.

## 2. Monitorização e alertas

- Público: `python deploy/smoke_test.py` e `python deploy/security_test.py`
- Saúde: `GET https://api.diomika.com/health` e `/health/ready`
- Runtime: `core/anomaly.py` (falhas login) → `core/alerts.py` → ficheiro + webhook SSRF-safe
- Opcional: uptime externo grátis (UptimeRobot / Better Stack) a bater `/health` a cada 5 min
- Sem SIEM enterprise de propósito (€0). Request-ID em todas as respostas (`X-Request-Id`).

Env úteis:

```
ALERT_WEBHOOK_URL=https://hooks.slack.com/...
ANOMALY_LOGIN_FAIL_THRESHOLD=8
```

## 3. Backup e restore (drill)

**Backup:** Supabase Free faz backup automático do projeto. Na VM, `.env` fica só no disco (não no git).

**Drill de restore (fazer 1× após go-live e após mudanças de schema):**

1. Supabase Dashboard → Project Settings → Database → Backups → escolher ponto.
2. Ou export lógico: Table Editor / `pg_dump` com `DATABASE_URL` (só no PC admin).
3. Validar: `python deploy/verify_rls.py` + smoke loja/API.
4. Anotar data do drill neste ficheiro (última linha).

Último drill: 2026-08-10 — validação pós-deploy (RLS verify + `/health/ready` + smoke loja/API). Restore completo via Dashboard Supabase a marcar na próxima janela de manutenção.

## 4. Privacidade / retenção (RGPD operacional)

| Dado | Retenção | Mecanismo |
|------|----------|-----------|
| contact_messages | 24 meses | `core/retention.py` (`RETENTION_CONTACT_DAYS`) |
| pedidos_orcamento (terminais) | 24 meses | idem |
| admin_audit_log | 12 meses | idem |
| Apagamento sob pedido | imediato | `POST /admin/privacy/erase` (admin local) |

Política pública: `/privacy` na loja. Minimização: só nome/email/contacto/mensagem. Sem pagamentos no site.

## 5. Secrets (sem Vault)

- `.env` **não** vai para o git (`.gitignore` + gitleaks)
- Na VM: ficheiro root-owned, compose `--env-file .env`
- Rotação: gerar no painel do fornecedor → actualizar `.env` → `deploy_vm.py`
- Sem GCP Secret Manager de propósito (Always Free / ops single-user). Se crescer: migrar chaves para GSM.
