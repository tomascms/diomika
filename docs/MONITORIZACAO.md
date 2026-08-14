# Monitorização — hub único Diomika

**App local (recomendado):** `monitor-hub/` — Electron com sidebar de projectos + abas (Cloudflare, Sentry, Axiom, …). Sessão de login por projecto; podes acrescentar outros clientes em `projects.json`.

```bash
cd monitor-hub && npm install && npm start
```

Abaixo fica a lista de referência dos mesmos painéis (links). Não guarda passwords nem tokens.

---

## 1. Minuto a minuto (está no ar?)

| Serviço | O que faz | Abrir |
|---------|-----------|--------|
| **UptimeRobot** | HTTP checks `api.diomika.com` + `www.diomika.com` (5 min) | https://dashboard.uptimerobot.com/monitors |
| **GitHub Actions — uptime** | Check periódico via workflow | https://github.com/tomascms/diomika/actions/workflows/uptime.yml |

Alerta rápido no telemóvel (sem login SaaS extra): tópico **ntfy** configurado em `ALERT_WEBHOOK_URL` no `.env` (não partilhar o URL).

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
| **Cloudflare** (Pages, DNS, Tunnel, WAF, Turnstile) | Loja + TLS + túnel API + anti-bot | https://dash.cloudflare.com/ |
| **Google Cloud** (VM e2-micro) | Máquina da API | https://console.cloud.google.com/ |
| **Supabase** | Postgres + Storage + RLS | https://supabase.com/dashboard |

---

## 5. Código e entregas

| Serviço | O que faz | Abrir |
|---------|-----------|--------|
| **GitHub** (repo + CI + releases backoffice) | Código, Actions, instaladores | https://github.com/tomascms/diomika |
| **GitHub Actions — CI** | Testes / security gate | https://github.com/tomascms/diomika/actions/workflows/ci.yml |
| **GitHub Actions — backoffice** | Builds Win/Mac/Linux | https://github.com/tomascms/diomika/actions/workflows/backoffice-release.yml |

---

## 6. Email (contacto / respostas)

| Serviço | O que faz | Onde |
|---------|-----------|------|
| **Caixa IMAP/SMTP** (Gmail ou o que estiver no `.env`) | Notificações de contacto + worker email | Conta definida em `MAIL_*` / `IMAP_*` |

---

## Checklist matinal (2 minutos)

1. UptimeRobot → os 2 monitores **Up**
2. Sentry → sem erro novo crítico
3. Axiom → há ingest recente (API viva)
4. Cloudflare / GCP → sem alerta óbvio
5. Se houve deploy: `python deploy/verify_production.py`

---

## O que **não** é monitorização (mas tens login)

| Item | Nota |
|------|------|
| Backoffice Electron | App local; login `admin` contra a API |
| Pasta `cliente-backoffice/` | Entrega ao cliente — não é dashboard |
| ntfy (app/web) | Só se quiseres ler o tópico de alertas |

---

*Actualiza este ficheiro se mudares de org/project IDs. Mantém-o em `docs/MONITORIZACAO.md` — é o teu hub.*
