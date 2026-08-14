# Diomika — Relatório técnico completo

Documento de arquitectura, protocolos, decisões e estado operacional.
Escopo: o que está **implementado e em produção** (não roadmap aspiracional).
Segredos reais **não** constam deste ficheiro nem do repositório público.

---

## 1. Visão do produto

A Diomika é um **catálogo B2B** (almofadas / produtos) com três superfícies:

| Superfície | Tecnologia | Público |
|------------|------------|---------|
| Loja | Vue 3 + Vite em Cloudflare Pages | Visitantes / clientes |
| API | FastAPI (Python) em VM GCP + Cloudflare Tunnel | Loja + backoffice |
| Backoffice | Electron (Windows / macOS / Linux) | Admin Diomika / cliente |

Dados e imagens: **Supabase** (PostgreSQL + Storage). Autenticação admin: ficheiro local na API (`admin_users.json`), **não** Supabase Auth.

Objectivo de custo: stack **€0/mês** de infra recorrente (domínio anual à parte), com monitorização freemium (Sentry / Axiom / PostHog / UptimeRobot / ntfy).

---

## 2. Topologia de runtime (como o tráfego flui)

```
[Browser]
    │ HTTPS
    ▼
www.diomika.com  ── Cloudflare Pages ── dist/ Vue
    │
    ├─ GET catálogo/imagens ──► Supabase (anon key + RLS)
    └─ POST contacto / API ──► https://api.diomika.com

[Electron Backoffice]
    │ HTTP local
    ▼
127.0.0.1:<port>/api/*  ── proxy Electron ──► https://api.diomika.com
    │                         header X-Diomika-Desktop = gate
    ▼
Cloudflare Edge (TLS + WAF)
    │
    ▼
Cloudflare Tunnel (cloudflared na VM)
    │ HTTP (sem porta pública 8000)
    ▼
127.0.0.1:8000 ── Docker: API FastAPI + Redis
    │
    ▼
Supabase (service role só no servidor)
```

### Decisões de topologia

1. **Não expor a API na internet aberta** — a VM só escuta `127.0.0.1:8000`; o Tunnel é o único caminho público.
2. **Pages separado da API** — CDN estático gratuito; API com estado (Redis, workers embutidos, ficheiros admin).
3. **Backoffice cloud** — o cliente **não** corre Python/Node local; o instalador fala com `api.diomika.com`.
4. **GCP e2-micro Always Free** — alternativa documentada a Oracle; deploy via `deploy/deploy_vm.py` (tarball SCP, sem clone de repo privado na VM).

Ficheiros: `deploy/docker-compose.free.yml`, `deploy/deploy_vm.py`, `deploy/FREE_STACK.md`, `backoffice-desktop/electron/main.cjs`.

---

## 3. Componentes e responsabilidades

### 3.1 Loja (`frontend-web/`)

- Rotas: home, categorias, produto, carrinho, contacto, about, privacy.
- Catálogo público via Supabase anon (`src/lib/catalogSupabase.js`).
- Formulários sensíveis: Cloudflare Turnstile (`useTurnstile.js`).
- Analytics: PostHog EU **só após consentimento** cookies (`CookieBanner.vue`).
- Edge: `functions/_middleware.js` bloqueia probes (`.env`, `.git`, `/src`, …).
- Headers: `public/_headers` (CSP / segurança em Pages).

### 3.2 API (`backend-api/`)

Entrada: `main.py` — routers de catálogo, contacto, orçamentos, encomendas, admin CRUD, auth admin, privacy, health.

Middleware (ordem relevante):

- Path guard / lockdown
- Trusted hosts / CORS / security headers
- Rate limit global
- Body size (**só Content-Length** — ver §5.4)
- Latency alert

Workers: email + outbox podem correr embutidos (`RUN_EMBEDDED_WORKERS`) no compose free, ou como serviços no `docker-compose.yml` raiz (VPS all-in-one).

### 3.3 Backoffice (`backoffice-desktop/`)

- UI Vue dentro de Electron.
- Servidor HTTP local: estáticos + **proxy** `/api` → origem cloud.
- Injecção do gate desktop em todos os pedidos API.
- Builds: portable Win, DMG Mac, AppImage Linux (`package.json` + workflow `backoffice-release.yml`).
- Gate gerado em build: `scripts/write-gate.cjs` → `electron/desktop-gate.cjs` (**gitignored**).

### 3.4 Dados (Supabase)

- SQL de produção / RLS: `deploy/supabase_pre_deploy.sql`, `backend-api/sql/`.
- Storage privado + signed URLs quando `SUPABASE_STORAGE_PRIVATE=1`.
- R2 opcional: `backend-api/utils/storage_r2.py` (activo só com `R2_*`).

---

## 4. Protocolos e métodos (detalhe)

### 4.1 HTTPS / TLS

- Visitantes e API pública: TLS terminado na **Cloudflare**.
- Origem Tunnel → API: HTTP em loopback (não atravessa a internet em claro).
- HSTS e headers de segurança aplicados pela API em produção (`middleware.py`).

### 4.2 Cloudflare Tunnel

- Autenticação: `CLOUDFLARE_TUNNEL_TOKEN` (secret).
- Serviço `cloudflared` com `network_mode: host`, origin `http://127.0.0.1:8000`.
- Motivo: zero portas abertas no firewall da VM; IP da VM não precisa ser o endpoint público.

### 4.3 Gate desktop (`X-Diomika-Desktop`)

**Problema:** expor `/admin` na API cloud quebraria o modelo “admin só no PC”.

**Solução:**

1. Secret partilhado `DIOMIKA_DESKTOP_GATE` (≥24 chars).
2. Electron envia header `X-Diomika-Desktop` no proxy (`main.cjs`).
3. API compara com `hmac.compare_digest` (`local_only.py`).
4. Em produção final: `/admin`, `/system`, `/health/detail` só com **loopback** ou gate válido (`path_guard.py` + `privileged_access_ok`).
5. WAF Cloudflare: regra espelho — bloqueia `/admin`/`/system` sem o header correcto (defense in depth; template em `deploy/cloudflare/waf_rules.json`).

**Não é JWT.** É um shared secret de instalação, embutido no binário do cliente. Rotação = novo build + actualizar WAF + `.env` da VM + secret GitHub.

### 4.4 Autenticação admin

| Aspecto | Método |
|---------|--------|
| Password | `hashlib.scrypt` (n=2¹⁴, r=8, p=1, dklen=32), salt 16 bytes (`admin_users.py`) |
| Sessão | Token opaco HMAC `dms1.…` (`session_tokens.py`), TTL curto / idle |
| Transporte | `Authorization: Bearer` |
| MFA | TOTP opcional; `ADMIN_MFA_REQUIRED` (default off) |
| Lockout | Falhas consecutivas → bloqueio temporário |
| Bootstrap | `ADMIN_BOOTSTRAP_USER/PASSWORD` só se **ainda não houver users** |

**Decisão crítica:** alterar o password no `.env` **não** actualiza um `admin_users.json` já existente. Reset = `upsert_user` / apagar store / script ops. Isto já causou falha de login em produção e foi corrigido alinhando o hash ao ficheiro `CREDENCIAIS.secret.txt`.

### 4.5 API keys (máquina a máquina)

- `X-API-Key` com comparação segura; chaves com scopes (`auth.py`).
- Loja **não** leva service role; só anon + Turnstile onde aplicável.

### 4.6 SSRF

- Qualquer URL outbound (alertas, Axiom, etc.) passa `assert_safe_outbound_url`.
- Só HTTPS; host allowlist; bloqueio de IPs privados / metadata.
- Defaults incluem Cloudflare, Slack/Discord, Axiom edge EU/US, `ntfy.sh`.

### 4.7 Turnstile

- Anti-bot nos formulários públicos.
- Verificação server-side (`utils/turnstile.py`); site key só no frontend.

### 4.8 Rate limiting

- Redis em produção (`REDIS_URL`); fallback memória.
- Limites globais + por rota; login admin: IP + username.

### 4.9 RLS (Postgres)

- Políticas em SQL de deploy: anon lê o necessário; escrita via service role na API.
- Verificação: `deploy/verify_rls.py` (CI opcional).

---

## 5. Decisões de engenharia (porquê)

### 5.1 Cloud backoffice em vez de Python local

- Cliente final não instala stack de desenvolvimento.
- Um binário por SO; API única; suporte remoto possível.
- Trade-off: gate no binário (quem tiver o instalador + password entra). Mitigado por WAF + password forte + rate limit + alertas de login falhado.

### 5.2 Não usar JWT de biblioteca para sessões admin

- Tokens curtos HMAC próprios, revogáveis (Redis em prod final).
- Menos superfície e dependências; formato controlado (`session_tokens.py`).

### 5.3 Storage privado

- Imagens não são URLs eternamente públicas sem controlo.
- Signed URLs com TTL; alinhado com B2B.

### 5.4 BodySizeLimitMiddleware sem consumir o body

**Bug:** ler `request.stream()` no middleware esgotava o body → POST login 422 “field required”.

**Fix:** validar apenas `Content-Length` (`middleware.py`). Decisão: preferir simplicidade e correcção ASGI a um parser buffering complexo.

### 5.5 Axiom na edge EU

- Org EU Central → ingest em `https://eu-central-1.aws.edge.axiom.co/v1/ingest/{dataset}`.
- Path legacy US `api.axiom.co/v1/datasets/.../ingest` rejeitado na edge.
- Código bifurca pelo hostname (`structured_logging.py`).

### 5.6 Observabilidade freemium

| Sistema | Papel |
|---------|--------|
| Sentry | Excepções API |
| Axiom | Logs estruturados |
| PostHog EU | Product analytics (consent) |
| ntfy | Alertas ops baratos |
| UptimeRobot | Uptime www + api |
| GH Actions uptime | Check secundário |

### 5.7 Schema-driven

- Modelos Pydantic como fonte de verdade → API + formulários backoffice + sync SQL (`schema_engine`).
- Reduz drift entre BD e UI admin.

---

## 6. Observabilidade — implementação

| Peça | Ficheiro | Activação |
|------|----------|-----------|
| Sentry | `core/sentry_init.py`, `error_tracking.py` | `SENTRY_DSN` |
| Axiom | `core/structured_logging.py` | `AXIOM_TOKEN` + `AXIOM_API_URL` |
| Flags | `core/feature_flags.py` | `FEATURE_*` |
| Health | `core/health.py` | `/health`, `/health/ready`, `/health/detail` (gated) |
| Alertas | `core/alerts.py` | `ALERT_WEBHOOK_URL` |
| PostHog | `CookieBanner.vue` | `VITE_POSTHOG_*` no **build** Pages |
| Bundle scan | `deploy/verify_bundle_secrets.py` | CI / pre-commit |

Health público devolve só status/versão; detalhe (sentry/axiom flags, DB, Redis) fica atrás do gate.

---

## 7. Segurança — mapa de controlos

1. Rede: Tunnel, loopback, sem 8000 público.
2. Edge: WAF + Pages middleware.
3. App: path_guard, local_only, rate limit, Turnstile, API keys, scrypt, sessões, SSRF allowlist.
4. Dados: RLS, storage privado, service role só no servidor.
5. Segredos: `.env` gitignored; gate gitignored; `cliente-backoffice/` gitignored; gitleaks no CI/pre-commit.
6. Lockdown: `SECURITY_LOCKDOWN` pode suspender mutações.

---

## 8. Deploy e operações

| Acção | Comando / artefacto |
|-------|---------------------|
| Deploy API VM | `python deploy/deploy_vm.py` |
| Deploy loja | `python deploy/deploy_beta.py --build --pages-deploy --api-url https://api.diomika.com` |
| Compose free | `deploy/docker-compose.free.yml --profile tunnel` |
| Release backoffice | workflow `backoffice-release.yml` + secret `DIOMIKA_DESKTOP_GATE` |
| Entrega cliente | pasta local `cliente-backoffice/` (não no git): EXE/DMG/AppImage + LEIA-ME + credenciais por canal privado |

### O que **não** vai para o cliente

- `CHAVES_MONITORIZACAO.env.txt`, tokens Sentry/Axiom/PostHog
- Topic ntfy
- Gate raw (já vai embutido no instalador)
- Acesso SSH / `.env` da VM

### O que **vai** para o cliente

- Instalador do SO
- `LEIA-ME.txt`
- Username/password admin (canal privado)

---

## 9. Testes e qualidade

- **pytest** (`pytest.ini` → `backend-api/tests/`): path guard, SSRF, sessões, storage, IDOR, observabilidade, etc.
- **Playwright** (`frontend-web/e2e/critical.spec.js`): smoke produção (health, home, privacy, admin bloqueado).
- **CI** (`.github/workflows/ci.yml`): pip-audit, security_gate, gitleaks, pytest, build frontend + bundle secrets, Playwright.
- **pre-commit**: gitleaks + verify_bundle_secrets.
- Scripts: `verify_production.py`, `uptime_check.py`, `critical_flow_check.py`, `load_test.py`, `check_dead_code.py`, …

---

## 10. Variáveis de ambiente (nomes — sem valores)

Ver `.env.example` e `deploy/env.free.example`.

Grupos: Supabase, API keys, CORS/hosts, Turnstile, mail/IMAP, Redis, storage privado, alertas, Sentry/Axiom/PostHog, desktop gate, bootstrap admin, Tunnel/Cloudflare, R2 opcional, rate limits, feature flags.

---

## 11. Estado actual (checklist operacional)

| Item | Estado |
|------|--------|
| Loja Pages + www | Produção |
| API Tunnel + VM | Produção |
| Gate + WAF admin | Activo |
| Login admin alinhado com CREDENCIAIS | Corrigido (hash sync) |
| Sentry / Axiom EU / PostHog | Ligados |
| UptimeRobot api + www | Criados |
| ntfy alertas | Ligado |
| MFA admin | Implementado, **desligado** (`ADMIN_MFA_REQUIRED=0`) |
| R2 | Código pronto, **não** activado na conta |
| Assinatura código (Authenticode / notarize) | Não (unsigned; SmartScreen/Gatekeeper) |

---

## 12. Limitações honestas

1. Gate no binário: quem tem instalador oficial + password = acesso admin API (mitigações acima).
2. Password bootstrap ≠ rotação automática do store de users.
3. Free tiers de SaaS: quotas e UI instáveis (ex.: create monitor UptimeRobot `/create` vs `/new/http`).
4. Binários não assinados: avisos OS na primeira abertura.
5. e2-micro: capacidade limitada; ver `deploy/SCALE.md` se crescer.

---

## 13. Mapa rápido de ficheiros-chave

```
backend-api/main.py
backend-api/core/{local_only,path_guard,middleware,admin_users,session_tokens,
                  ssrf_guard,alerts,structured_logging,sentry_init,health,auth}.py
backoffice-desktop/electron/{main,api-origin}.cjs
backoffice-desktop/scripts/write-gate.cjs
frontend-web/src/components/CookieBanner.vue
frontend-web/functions/_middleware.js
deploy/{deploy_vm,deploy_beta,docker-compose.free,FREE_STACK,OPS,SCALE}.py|.yml|.md
.github/workflows/{ci,backoffice-release,uptime}.yml
```

---

## 14. Conclusão

A Diomika em produção é um sistema **deliberadamente defensivo**: CDN + Tunnel + gate desktop + WAF + RLS + scrypt + SSRF allowlist + observabilidade freemium, com custo recorrente ≈ €0. O backoffice cloud permite entregar um instalador por SO sem expor a API admin ao browser público. Os segredos ficam fora do Git; o que este relatório descreve são **protocolos e decisões**, não credenciais.
