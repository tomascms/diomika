# Apresentação ao cliente — stack Diomika

Uma ferramenta por função. Tudo free-tier (excepto domínio).

## O que está vivo hoje

| Peça | Tecnologia | URL |
|------|------------|-----|
| Loja B2B | Vue + Cloudflare Pages | https://www.diomika.com |
| API | FastAPI + Redis na GCP e2-micro + Tunnel | https://api.diomika.com |
| Dados / auth BD | Supabase Free (Postgres + RLS) | — |
| Admin | Electron **só no PC** (não na internet) | local |
| Segurança edge | Cloudflare WAF + Turnstile + CSP | — |

## Monitorização (escolhas finais — sem duplicados)

| Função | Ferramenta | Porque esta |
|--------|------------|-------------|
| Erros da API | **Sentry** Free | Completo: stack traces, alertas, release tracking |
| Logs / pesquisa | **Axiom** Free | Logs JSON pesquisáveis; substitui “SIEM caseiro” |
| Analytics loja | **PostHog** Free (EU) | Funnels, paths, gravação opcional — melhor que Plausible simples |
| Uptime 24/7 | **UptimeRobot** Free | Alerta se API/loja caírem (email) |
| Alertas abuso/login | Webhook Slack/Discord + ficheiro local | Já no código |
| Imagens (próximo passo) | **Cloudflare R2** Free | CDN barato; BD fica no Supabase |

Removido de propósito (era pior/duplicado): Plausible, pageviews first-party `/metrics/hit`, Grafana na VM.

## Segurança já no produto (podes dizer isto)

- Admin inacessível na internet (só localhost + WAF)
- Rate limit + Turnstile + honeypot nos formulários
- Sessões curtas, passwords scrypt, sem enumeração de login
- RLS no Supabase (anon não lê dados sensíveis)
- Privacy erase + retenção automática (RGPD operacional)
- Testes: `python deploy/verify_production.py`

## Contas a criar (ordem sugerida — free)

1. **Sentry** → projecto Python → `SENTRY_DSN` no `.env` da VM  
2. **PostHog** (região EU) → projecto → `VITE_POSTHOG_KEY` + redeploy Pages  
3. **Axiom** → dataset `diomika` → `AXIOM_TOKEN` + `AXIOM_DATASET`  
4. **UptimeRobot** → monitor `https://api.diomika.com/health` e `https://www.diomika.com` (5 min)  
5. **Slack/Discord webhook** → `ALERT_WEBHOOK_URL`  
6. **R2** (quando quiseres CDN imagens) → `R2_*` (activa sozinho)

Depois: `python deploy/deploy_vm.py` e `python deploy/deploy_beta.py --pages-deploy --api-url https://api.diomika.com`

## Manutenção mensal (proposta comercial)

Inclui: uptime, revisão alertas Sentry/PostHog, backup/drill, call 30–45 min, pequenas alterações de catálogo.  
Ver valores discutidos à parte (€300–450/mês recomendado).

## Demo ao vivo (2 min)

1. Abrir loja → categorias → produto → orçamento  
2. `https://api.diomika.com/health` → online  
3. Tentar `/admin` na API pública → bloqueado  
4. Backoffice: instalar EXE/DMG (liga a `api.diomika.com`) — **sem** Python no PC do cliente  
