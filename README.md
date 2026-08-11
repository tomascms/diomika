# Diomika

Catálogo B2B: loja Vue + API FastAPI + backoffice Electron (só local) + Supabase.

## Produção (€0 excepto domínio)

| Peça | Onde |
|------|------|
| Loja | Cloudflare Pages → `www.diomika.com` |
| API | GCP e2-micro + Tunnel → `api.diomika.com` |
| Dados | Supabase Free |
| Admin | `backoffice-desktop` neste PC |

```powershell
python deploy/create_gcp_vm.py
python deploy/deploy_vm.py
python deploy/deploy_beta.py --pages-deploy --api-url https://api.diomika.com
python deploy/smoke_test.py --api https://api.diomika.com --site https://www.diomika.com
python deploy/security_test.py --url https://api.diomika.com
```

Ops / IR / RGPD: `deploy/OPS.md`  
Stack €0: `deploy/FREE_STACK.md`

## Backoffice (PC)

```powershell
.\ABRIR_BACKOFFICE.bat
# API local opcional: python deploy/start_local_api.py
```

## Pastas

| Pasta | Função |
|-------|--------|
| `frontend-web/` | Loja (Pages) |
| `backend-api/` | API FastAPI |
| `backoffice-desktop/` | Admin Electron |
| `deploy/` | VM, Docker, gates CI, smoke/security |

## Config

Copia `deploy/env.free.example` → `.env` na raiz (local/VM). **Nunca commits `.env`** — o repo está preparado para ser público.

Antes de tornar o GitHub público: roda no dashboard as chaves que já estiveram no histórico antigo (`SUPABASE_KEY`, Turnstile, Cloudflare token, mail app password). As chaves de API/admin locais já foram regeneradas.

## Testes

```powershell
python -m pytest backend-api/tests -q
python deploy/security_gate.py
```
