# Diomika Command Center

Painel de operações nativo — gráficos, alertas e CI/CD via APIs.

## Arranque (um clique)

```
monitor-hub/Diomika-Command-Center-1.1.0-windows.exe
```

Configuração: `config.local.json` (mesma pasta).

## Configurar / actualizar credenciais

```powershell
cd monitor-hub
node scripts/setup-from-env.cjs      # importa do .env do repo
node scripts/sync-github-token.cjs   # depois de gh auth login
```

## Rebuild

```powershell
npm install
npm run dist:win
```

Gera o `.exe` na raiz de `monitor-hub/` (e artefactos em `release/`).

Guia: [`docs/INSTRUCOES.md`](../docs/INSTRUCOES.md) §5.
