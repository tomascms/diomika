# Diomika — Estado de produção

**Última verificação:** 16 de Agosto de 2026  
**Comando:** `python deploy/verify_production.py` → **VERIFY OK**

| Componente | URL | Estado |
|---|---|---|
| API | `https://api.diomika.com` | online v2.3.0 |
| Loja | `https://www.diomika.com` | Pages OK |
| Estado público | `https://www.diomika.com/status.html` | activo |
| Monitor Hub | `monitor-hub/` (local) | painel Estado & Alertas |
| Backoffice cliente | `cliente-backoffice/` | win + mac + linux (release CI) |
| Supabase | `ptvzctrutihcfknowbam` | migração `composicao` aplicada |

---

## Cabeçalhos HTTP da API — é suposto estar exposto?

**Sim.** Os cabeçalhos de **resposta** (`Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options`, etc.) são protecções públicas — não são segredos. Os cabeçalhos de **pedido** no DevTools são só os que o teu browser enviou naquele request.

Implementação: `backend-api/core/middleware.py`.

**Não exposto (correcto):** tokens, OpenAPI, stack traces, `/api/docs`.

---

## Melhorias implementadas (16/08/2026)

| Melhoria | Estado | Onde |
|---|---|---|
| Monitorização externa (5 min) | **Feito** | `.github/workflows/uptime.yml` + `deploy/monitor_check.py` |
| Alertas no hub (ntfy + log local) | **Feito** | `monitor-hub/ui/panel-status.html` + `config.local.json` |
| Página de estado | **Feito** | `www.diomika.com/status.html` |
| `security.txt` | **Feito** | API + loja (`/.well-known/security.txt`) |
| `robots.txt` API | **Feito** | `GET /robots.txt` → `Disallow: /` |
| `GET /` API | **Feito** | JSON mínimo com link para `/health` e status page |
| E2E Playwright no CI | **Já existia** | `.github/workflows/ci.yml` + testes meta novos |
| Alertas latência → ntfy | **Feito** | `LatencyAlertMiddleware` + `ALERT_WEBHOOK_URL` |
| Backup Supabase documentado | **Feito** | `docs/OPS.md` (runbook) |
| PostHog RGPD | **Já existia** | `CookieBanner.vue` — load só após aceitar |
| Assinatura código backoffice | **Pendente externo** | requer certificado EV (custo) |

---

## Monitor Hub — estado e alertas num só sítio

1. Copia `monitor-hub/config.local.example.json` → `config.local.json`
2. Coloca o URL JSON do teu tópico ntfy (`https://ntfy.sh/<topico>/json?poll=1`)
3. `cd monitor-hub && npm start`
4. Abre a aba **Estado & Alertas** — mostra API, loja, BD, alertas locais (`deploy/alerts.log`) e push ntfy

Documentação completa: [`MONITORIZACAO.md`](MONITORIZACAO.md)

---

## Testes automáticos

```powershell
python deploy/verify_production.py
python deploy/security_test.py
python deploy/monitor_check.py --alert
```

- Segurança: rotas admin bloqueadas, OpenAPI off, `/`, `robots.txt`, `security.txt`
- Uptime: GitHub Actions cada **5 min**; falha envia webhook (`ALERT_WEBHOOK_URL` secret)

---

## Pendente (requer acção manual)

1. **GitHub secret** `ALERT_WEBHOOK_URL` — mesmo URL ntfy do `.env` de produção
2. **GitHub secret** `SITE_URL` = `https://www.diomika.com` (opcional, tem default)
3. **Deploy** — `python deploy/deploy_vm.py` + `python deploy/deploy_pages.py --build --pages-deploy --api-url https://api.diomika.com`
4. **Assinatura EV** dos instaladores backoffice (SmartScreen / Gatekeeper)
5. **Restore drill Supabase** — calendário trimestral (ver `docs/OPS.md`)

---

Relatório técnico completo: [`RELATORIO_TECNICO.md`](RELATORIO_TECNICO.md)
