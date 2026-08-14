# Monitor Hub (local)

App Electron **só na tua máquina**: sidebar de projectos + abas por serviço (Cloudflare, Sentry, Axiom, …).

Cada aba é um browser embutido real (`WebContentsView`), não iframe — os dashboards SaaS bloqueiam iframe; aqui o login fica na sessão persistente do projecto.

## Arranque

```bash
cd monitor-hub
npm install
npm start
```

## Adicionar outro projecto

Edita `projects.json`:

```json
{
  "projects": [
    {
      "id": "diomika",
      "name": "Diomika",
      "tabs": [ ... ]
    },
    {
      "id": "outro",
      "name": "Outro Cliente",
      "tabs": [
        { "id": "sentry", "label": "Sentry", "url": "https://...." },
        { "id": "cloudflare", "label": "Cloudflare", "url": "https://dash.cloudflare.com/" }
      ]
    }
  ]
}
```

Reinicia a app. Sessões de login ficam separadas por `id` do projecto (`persist:monitor-<id>`).

Não mete tokens nem passwords neste ficheiro — só URLs públicas dos painéis.
