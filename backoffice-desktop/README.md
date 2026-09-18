# Diomika Backoffice

App Electron (Win/Mac/Linux) para gestão do catálogo — liga a `https://api.diomika.com`.

Documentação completa: [`docs/INSTRUCOES.md`](../docs/INSTRUCOES.md) (secção Backoffice).

## Build

```bash
npm ci
npm run dist:cliente   # Windows + copia para cliente-backoffice/
```

## Dev

```bash
npm run dev:ui         # browser http://127.0.0.1:5174
npm run dev            # Electron + Vite
```

Abrir instalador local: `Abrir-Windows.cmd` ou `packaging/Abrir-Windows.cmd`.
