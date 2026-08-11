# Stack €0 (excepto domínio)

**Único gasto:** domínio `diomika.com`.

```
www.diomika.com  → Cloudflare Pages
api.diomika.com  → Cloudflare Tunnel → GCP e2-micro (API + Redis)
                 → Supabase Free
PC admin         → backoffice-desktop (local)
```

## VM Always Free

- Shape: **e2-micro**, disco 30 GB standard
- Região: `us-central1`, `us-west1` ou `us-east1`
- Não activar billing pago / “Activate” se só queres free

```powershell
python deploy/create_gcp_vm.py
# grava REMOTE_VM_SSH no .env
python deploy/deploy_vm.py
```

`deploy_vm.py`: swap 2G, Docker, envia código + `.env`, sobe `docker-compose.free.yml` (API + Redis + cloudflared), aponta o tunnel para `http://127.0.0.1:8000`.

## Ficheiros úteis

| Ficheiro | Uso |
|----------|-----|
| `docker-compose.free.yml` | API + Redis + tunnel |
| `env.free.example` | Template `.env` |
| `create_gcp_vm.py` | Criar e2-micro |
| `deploy_vm.py` | Deploy na VM |
| `deploy_beta.py` | Build / deploy Pages |
| `smoke_test.py` | Health público |
| `security_gate.py` | Gate CI |
| `verify_csp.py` | CSP sem unsafe-inline |
| `OPS.md` | IR, backup, alertas, RGPD |
