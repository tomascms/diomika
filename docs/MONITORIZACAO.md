# Monitorização — hub único Diomika

**App local (recomendado):** `monitor-hub/` — Electron com sidebar + abas.

```bash
cd monitor-hub && npm install && npm start
```

### Configurar alertas ntfy no hub

```bash
cp monitor-hub/config.local.example.json monitor-hub/config.local.json
# Edita ntfyTopicJsonUrl com o teu tópico (mesmo do ALERT_WEBHOOK_URL)
```

A aba **Estado & Alertas** mostra:
- API `/health` e `/health/ready`
- Loja `www.diomika.com`
- Últimos alertas de `deploy/alerts.log`
- Stream ntfy (se configurado)

Página pública de estado: https://www.diomika.com/status.html

---

## 1. Minuto a minuto (está no ar?)

| Serviço | O que faz | Abrir |
|---------|-----------|--------|
| **Monitor Hub — Estado & Alertas** | Painel local integrado | `npm start` em `monitor-hub/` |
| **Estado público** | Página auto-refresh 60s | https://www.diomika.com/status.html |
| **UptimeRobot** | HTTP checks api + www (5 min) | https://dashboard.uptimerobot.com/monitors |
| **GitHub Actions — uptime** | Check 5 min + alerta ntfy | https://github.com/tomascms/diomika/actions/workflows/uptime.yml |

Alertas no telemóvel: `ALERT_WEBHOOK_URL` no `.env` (ntfy) — **não partilhar o URL**.

---

## 2. Erros e logs (API)

| Serviço | O que faz | Abrir |
|---------|-----------|--------|
| **Sentry** (EU) | Excepções / stack traces da API | https://diomika.sentry.io/ |
| **Axiom** (EU Central) | Logs estruturados dataset `diomika` | https://app.axiom.co/diomika-5pui/datasets/diomika |

---

## 3. Produto / loja (comportamento)

| Serviço | O que faz | Abrir |
|---------|-----------|--------|
| **PostHog** (EU) | Analytics após consentimento cookies | https://eu.posthog.com/project/248877 |

---

## 4. Infraestrutura e edge

| Serviço | O que faz | Abrir |
|---------|-----------|--------|
| **Cloudflare** | Loja + TLS + túnel API + WAF + Turnstile | https://dash.cloudflare.com/ |
| **Google Cloud** | VM e2-micro da API | https://console.cloud.google.com/ |
| **Supabase** | Postgres + Storage + RLS | https://supabase.com/dashboard |

---

## 5. Código e entregas

| Serviço | O que faz | Abrir |
|---------|-----------|--------|
| **GitHub** | Repo + CI + releases backoffice | https://github.com/tomascms/diomika/actions |
| **CI** | Testes + security gate + e2e | workflows/ci.yml |
| **Backoffice release** | Win/Mac/Linux → GitHub Release | workflows/backoffice-release.yml |

---

## Checklist matinal (2 minutos)

1. Monitor Hub → aba **Estado & Alertas** → tudo OK
2. UptimeRobot → monitores Up
3. Sentry → sem erro crítico novo
4. Axiom → ingest recente
5. Se houve deploy: `python deploy/verify_production.py`

---

*Actualiza `projects.json` se mudares org/project IDs. Hub ops: `docs/MONITORIZACAO.md`.*
