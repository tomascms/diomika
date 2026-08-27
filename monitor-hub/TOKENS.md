# Tokens do hub — checklist rápida

O hub já está preparado. Falta só permissões correctas nos tokens.

## 1. Cloudflare (pedidos edge / WAF)

1. Abre https://dash.cloudflare.com/profile/api-tokens
2. **Create Token** → *Read analytics and logs* (ou Custom)
3. Permissões mínimas:
   - Zone — Zone — Read (zona `diomika.com`)
   - Zone — Analytics — Read
   - Zone — Firewall Services — Read (opcional: feed WAF por path/evento)
4. Zone Resources: Include → Specific zone → `diomika.com` (ou All zones)
5. Copia o token para `.env` como `CLOUDFLARE_API_TOKEN=...`
6. No hub: **Ligações → Importar do .env**

> Sem Firewall Services Read o hub ainda mostra pedidos/ameaças agregados; só o feed detalhado de paths fica limitado.

## 2. Axiom (gráficos de erros)

1. Abre https://app.axiom.co/ → Settings → API tokens
2. Cria token com:
   - Datasets: **Read** (ou Query) no dataset `diomika`
3. Substitui `AXIOM_TOKEN=` no `.env`
4. Hub: **Importar do .env**

> O token actual parece ser sobretudo de **ingest** (a API escreve logs). O hub precisa de **leitura**.

## 3. PostHog

Já deve estar OK com `POSTHOG_PERSONAL_API_KEY` (`phx_`) + Query:Read.

## 3b. Sentry (opcional — resolver issues)

O token actual do hub basta para **ler** issues. Para o hub (ou script) **resolver** em lote:

1. https://sentry.io/settings/account/api/auth-tokens/
2. Token com scopes: `project:read`, `event:read`, **`event:admin`** (ou `project:write`)
3. Guarda como `SENTRY_AUTH_TOKEN` no `.env` e Importar do .env

Ou no UI do Sentry: Issues → seleccionar todas → Resolve.

## 4. Confirmar

```powershell
cd monitor-hub
npm start
```

Visão geral → Edge 24h deve deixar de ser "—" e Axiom deixa de pedir atenção por permissões.
