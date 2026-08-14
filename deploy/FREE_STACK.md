# Stack €0 (excepto domínio)

**Único gasto:** domínio `diomika.com`.

```
www.diomika.com  → Cloudflare Pages + PostHog
api.diomika.com  → Tunnel → GCP e2-micro (API + Redis) + Sentry/Axiom
dados            → Supabase Free (+ R2 para imagens quando activares)
PC admin         → Diomika-Backoffice EXE/DMG (liga à API cloud)
```

Apresentação cliente: `APRESENTACAO_CLIENTE.md`  
Verificação: `python deploy/verify_production.py`

```powershell
python deploy/create_gcp_vm.py
python deploy/deploy_vm.py
python deploy/deploy_beta.py --pages-deploy --api-url https://api.diomika.com
python deploy/verify_production.py
```
