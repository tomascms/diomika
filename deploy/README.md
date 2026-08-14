# Deploy Diomika

Caminho canónico (produção €0):

```powershell
python deploy/deploy_vm.py
python deploy/deploy_pages.py --pages-deploy --api-url https://api.diomika.com
python deploy/verify_production.py
```

| Ficheiro | Função |
|----------|--------|
| `deploy_vm.py` | API na VM + Tunnel |
| `deploy_pages.py` | Build + Cloudflare Pages |
| `docker-compose.free.yml` | Compose na VM |
| `docker-compose.vps.yml` | Alternativa VPS com workers separados |
| `env.free.example` | Template `.env` produção |
| `create_gcp_vm.py` | Criar VM GCP |
| `security_gate.py` | Portão CI |
| `verify_production.py` | Smoke pós-deploy |
| `supabase_pre_deploy.sql` | SQL / RLS |
| `cloudflare/` | DNS + WAF |

Documentação longa: [`docs/`](../docs/).
