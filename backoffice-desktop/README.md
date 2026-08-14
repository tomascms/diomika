# Diomika Backoffice

App de secretária **para o cliente**: um ficheiro, um clique, sem instalar Python/Node.

Liga à API de produção (`https://api.diomika.com`) — já online 24/7.

## Entregar ao cliente

| SO | Artefacto em `release/` |
|----|-------------------------|
| Windows | `Diomika-Backoffice-*-win-portable.exe` |
| macOS | `Diomika-Backoffice-*-mac.dmg` (CI macOS) |
| Linux | `Diomika-Backoffice-*-linux.AppImage` (CI Linux) |

```bash
npm ci
npm run dist:win
# Mac/Linux: GitHub Actions → "Backoffice release"
```

## Developers (só)

```bash
# API local opcional
DIOMIKA_API_ORIGIN=http://127.0.0.1:8001 npm run dev
```
