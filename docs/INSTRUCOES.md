# Diomika — Instruções (ligar e usar tudo)

Guia prático único. Manual técnico completo: [`RELATORIO_TECNICO.md`](RELATORIO_TECNICO.md).

---

## 1. O que está online

| Peça | URL / local |
|------|-------------|
| Loja B2B | https://www.diomika.com |
| API | https://api.diomika.com |
| Estado público | https://www.diomika.com/status.html |
| Dados | Supabase (projecto `ptvzctrutihcfknowbam`) |
| Backoffice cliente | `cliente-backoffice/` ou GitHub Release `backoffice-cliente-latest` |
| Monitor Hub (tu) | `monitor-hub/` — app Electron local |

**Custo recorrente:** €0 infra (excepto domínio `diomika.com`).

---

## 2. Primeira configuração (ordem)

1. Copiar `deploy/env.free.example` → `.env` na raiz (nunca commitar).
2. Preencher Supabase, Turnstile, Cloudflare, `API_SECRET_KEY`, observabilidade.
3. **Alertas telemóvel:** `ALERT_WEBHOOK_URL=https://ntfy.sh/<teu-topico>` (mesmo URL no hub e no GitHub secret).
4. Contas free (se ainda não tens): Sentry, Axiom, PostHog EU, UptimeRobot.
5. GCP VM + Tunnel (se ainda não existe): `python deploy/create_gcp_vm.py` depois `python deploy/deploy_vm.py`.

---

## 3. Deploy produção

```powershell
cd C:\Users\tcmso\Desktop\diomika
python deploy/deploy_vm.py
$env:PAGES_PRODUCTION="1"
python deploy/deploy_pages.py --build --pages-deploy --api-url https://api.diomika.com
python deploy/verify_production.py
```

Preferir `CLOUDFLARE_PAGES_API_TOKEN` (Account → **Cloudflare Pages → Edit/Write**, ex. token «Diomika deploy»). O `CLOUDFLARE_API_TOKEN` do hub (Analytics) fica separado — sem Pages Write falha com `Authentication error [code: 10000]`. Alternativa: Dashboard → Pages → `diomika-loja` → Upload de `frontend-web/dist/`.

| Script | Faz |
|--------|-----|
| `deploy_vm.py` | API na VM + Docker + Tunnel |
| `deploy_pages.py` | Build + Cloudflare Pages (`PAGES_PRODUCTION=1` = loja produção) |
| `verify_production.py` | Uptime + smoke + segurança (+ e2e se Playwright instalado) |
| `apply_production.py` | Schema Supabase + SQL infra (opcional `--seed-demo`) |
| `monitor_check.py --alert` | Teste manual API+loja com alerta ntfy |
| `security_audit_deep.py` | Auditoria de segurança expandida |

**GitHub secrets (Actions):** `API_HEALTH_URL`, `ALERT_WEBHOOK_URL`, `SITE_URL` (opcional).

---

## 4. Backoffice cliente

### Entregar ao cliente

Instaladores em `cliente-backoffice/` (ou `Desktop/cliente-backoffice/`):

- `Diomika-Backoffice-1.0.0-windows.exe`
- `Diomika-Backoffice-1.0.0-mac.dmg`
- `Diomika-Backoffice-1.0.0-linux.AppImage`

Actualizar a partir do CI:

```powershell
python deploy/fetch_backoffice_release.py
```

### Rebuild local (Windows)

```powershell
cd backoffice-desktop
npm ci
npm run dist:cliente
```

Mac/Linux `.dmg`/`.AppImage` — GitHub Actions (`backoffice-release.yml`) ou num Mac/Linux.

**Uso:** duplo-clique → login admin → gere catálogo/pedidos. Liga a `https://api.diomika.com` (não precisa Python no PC do cliente).

---

## 5. Monitor Hub — Command Center (como ler em 30s)

```powershell
cd monitor-hub
npm install
# Preferível: Importar do .env dentro da app (Ligações)
# Ou: copy config.local.example.json config.local.json
npm start
```

**Atalho:** `Abrir Command Center.vbs` / atalho no Ambiente de trabalho.

### O que vês na Visão geral (control tower)

1. **Estado do cliente** — OK / Atenção / Crítico (linguagem clara, sem códigos)
2. **Faixa de ligações** — verde = hub a ver dados; vermelho = cego nalguma API
3. **4 números** — pedidos edge (Cloudflare), visitas PostHog, inbox por ler, uptime/SLO
4. **O que precisa de ti** — só problemas accionáveis + «Ver o que fazer» / Prompt Cursor
5. **O que mudou** — deltas desde o último poll + banner de regressão pós-deploy

**Ctrl+K** — command palette (ir a abas, health, relatório).

### Abas

| Aba | Serve para |
|-----|------------|
| Visão geral | Decisão em 30s |
| Analytics | Edge + PostHog + negócio (hoje/7d/total) + insights |
| Segurança | Postura 0–100, sintéticos, WAF/ataques |
| Incidentes | Histórico, Ack/Resolver, playbooks, feed |
| Infra | Latência, monitores, Sentry (detalhe) |
| CI / CD | Releases e Actions |
| Ligações | Importar `.env`, tokens |

### Tokens / scopes necessários

| Serviço | O que o hub precisa |
|---------|---------------------|
| PostHog | **Personal API Key `phx_`** com Query:Read + Project:Read (EU). Não uses `phc_`. Env: `POSTHOG_PERSONAL_API_KEY` |
| Axiom | Token com **query/read** no dataset (não só ingest). Env: `AXIOM_TOKEN` |
| Cloudflare | Token com Zone Read + **Analytics Read** (GraphQL). Env: `CLOUDFLARE_API_TOKEN` |
| Supabase | URL + service/anon key para contagens de negócio. Env: `SUPABASE_URL`, `SUPABASE_KEY` |
| Sentry | Auth token org/project. Env: `SENTRY_AUTH_TOKEN` |
| GitHub | `gh auth login` ou Device Flow |

### Checklist matinal (2 min)

1. Visão geral → estado OK ou lista curta «precisa de ti»
2. Segurança → postura alta; admin bloqueado; sintéticos OK
3. Analytics → edge/visitas e inbox
4. Se houve deploy → banner de regressão ou `python deploy/verify_production.py`
5. Relatório mensal → botão «Relatório mensal» (Markdown sem PII)

### Notas

- Visitas PostHog = só tráfego **com consentimento** de cookies; edge Cloudflare = pedidos reais.
- Erros técnicos de integração ficam em Ligações / detalhe — a home mostra frases humanas.
- Notificação do Windows quando o score passa a Crítico.

---

## 6. Variáveis `.env` essenciais

```
SUPABASE_URL=
SUPABASE_KEY=
API_SECRET_KEY=
TURNSTILE_SECRET_KEY=
SENTRY_DSN=
AXIOM_TOKEN=
AXIOM_DATASET=diomika
AXIOM_API_URL=https://eu-central-1.aws.edge.axiom.co
POSTHOG_PERSONAL_API_KEY=   # hub Query API (phx_) — obrigatório para Analytics
VITE_POSTHOG_KEY=          # build Pages (phc_) — não usar no hub
VITE_POSTHOG_HOST=https://eu.i.posthog.com
ALERT_WEBHOOK_URL=         # ntfy
ALERT_LATENCY_MS=2000
ADMIN_SESSION_TTL_MINUTES=43200   # 30 dias; idle off por omissão
```

---

## 7. Incidentes

1. Cloudflare → Under Attack se ataque
2. Rodar secrets afectados
3. `python deploy/deploy_vm.py`
4. `SECURITY_LOCKDOWN=1` no `.env` se contenção urgente
5. Sentry + Axiom + ntfy para evidência

---

## 8. Backup Supabase

- Backups automáticos diários (plano Free)
- Verificar dashboard — **mensal**
- **Restore drill** — Jan, Abr, Jul, Out (branch de teste, nunca directo em prod)
- Último check: 2026-08-10 · Próximo: 2026-11-01

---

## 9. Quando o free doer (escala)

1. Alerta orçamento GCP $1–5
2. Upgrade Supabase ou mais workers se BD/CPU alta
3. R2 para imagens se tráfego crescer (`R2_*` no `.env`)
4. Certificado EV backoffice (~€/ano) — remove aviso SmartScreen/Gatekeeper

---

## 10. Demo ao cliente (2 min)

1. Loja → categorias → produto → orçamento
2. https://api.diomika.com/health → online
3. Backoffice → login → listagem
4. Browser em `/admin` na API → bloqueado (só app passa)

---

## 11. Comandos úteis

```powershell
python deploy/security_test.py
python deploy/uptime_check.py --url https://api.diomika.com --ready
python -m pytest backend-api/tests -q
cd frontend-web && npm run test:e2e
```

Scripts detalhados: [`deploy/README.md`](../deploy/README.md).
