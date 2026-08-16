# Diomika

Catálogo B2B: loja Vue + API FastAPI + backoffice Electron + Supabase.

## Backoffice (PC do cliente — um clique)

A API já está online em `https://api.diomika.com`. O cliente **não** instala Python nem Node.

| SO | Ficheiro (só isto) |
|----|---------------------|
| Windows | `Diomika-Backoffice-*-win-portable.exe` |
| macOS | `Diomika-Backoffice-*-mac.dmg` |
| Linux | `Diomika-Backoffice-*-linux.AppImage` |

Duplo-clique → login. Build: Actions → *Backoffice release*, ou neste PC:

```powershell
cd backoffice-desktop
npm ci
npm run dist:win
```

Artefactos em `backoffice-desktop/release/`.

## Produção (€0 excepto domínio)

| Peça | Onde |
|------|------|
| Loja | Cloudflare Pages → `www.diomika.com` |
| API | GCP + Tunnel → `api.diomika.com` (24/7) |
| Dados | Supabase Free |
| Admin | EXE/DMG/AppImage acima |
| Monitorização | Sentry + Axiom + PostHog + UptimeRobot |

```powershell
python deploy/deploy_vm.py
python deploy/deploy_pages.py --pages-deploy --api-url https://api.diomika.com
python deploy/verify_production.py
```

Docs: [`docs/INSTRUCOES.md`](docs/INSTRUCOES.md) (operar) · [`docs/RELATORIO_TECNICO.md`](docs/RELATORIO_TECNICO.md) (manual completo) · Scripts: [`deploy/README.md`](deploy/README.md)

## Config (servidor / developers)

Copia `deploy/env.free.example` → `.env`. **Nunca commits `.env`.**
