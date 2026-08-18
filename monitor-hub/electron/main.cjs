const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron')
const path = require('path')
const fs = require('fs')
const {
  getUiPath,
  ensureLocalConfig,
  getLocalConfigPath,
  getUserRoot,
} = require('./paths.cjs')
const {
  loadHubConfig,
  saveHubConfig,
  integrationStatus,
  persistMergedSecrets,
} = require('./config.cjs')
const { buildSnapshot } = require('./aggregator.cjs')
const {
  loadDismissed,
  saveDismissed,
  alertKey,
  recKey,
  sentryKey,
  ciKey,
} = require('./dismissed.cjs')
const {
  startDeviceFlow,
  pollDeviceToken,
  tryGhCliToken,
} = require('./services/github.cjs')

/** @type {BrowserWindow | null} */
let mainWindow = null
let pollTimer = null
let ntfyTimer = null
let devicePollTimer = null

async function pushSnapshot() {
  if (!mainWindow) return
  try {
    const snapshot = await buildSnapshot(app)
    mainWindow.webContents.send('snapshot', snapshot)
  } catch (e) {
    mainWindow.webContents.send('snapshot-error', e.message)
  }
}

function startPolling() {
  stopPolling()
  const cfg = loadHubConfig(app)
  const sec = Math.max(15, Number(cfg.pollIntervalSeconds) || 30)
  pollTimer = setInterval(pushSnapshot, sec * 1000)
  ntfyTimer = setInterval(pushSnapshot, 10000)
  pushSnapshot()
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer)
  if (ntfyTimer) clearInterval(ntfyTimer)
  pollTimer = null
  ntfyTimer = null
}

async function showFirstRunDialog(setup) {
  if (!setup.firstRun) return
  const flag = path.join(getUserRoot(app), 'hub-welcome-seen')
  if (!fs.existsSync(flag)) fs.writeFileSync(flag, new Date().toISOString(), 'utf8')
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 920,
    minWidth: 1100,
    minHeight: 700,
    title: 'Diomika Command Center',
    backgroundColor: '#0a0e14',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  mainWindow.loadFile(getUiPath(app, 'index.html'))
  mainWindow.webContents.on('did-finish-load', () => {
    startPolling()
  })
  mainWindow.on('closed', () => {
    mainWindow = null
    stopPolling()
  })
}

ipcMain.handle('get-config', () => {
  const cfg = loadHubConfig(app)
  return {
    ...cfg,
    github: { ...cfg.github, token: cfg.github?.token ? '***' : '' },
    sentry: { ...cfg.sentry, token: cfg.sentry?.token ? '***' : '' },
    axiom: { ...cfg.axiom, token: cfg.axiom?.token ? '***' : '' },
    uptimerobot: { ...cfg.uptimerobot, apiKey: cfg.uptimerobot?.apiKey ? '***' : '' },
    cloudflare: { ...cfg.cloudflare, apiToken: cfg.cloudflare?.apiToken ? '***' : '' },
    posthog: { ...cfg.posthog, apiKey: cfg.posthog?.apiKey ? '***' : '' },
    integrations: integrationStatus(cfg),
    configPath: getLocalConfigPath(app),
  }
})

ipcMain.handle('save-config', (_e, partial) => {
  const saved = saveHubConfig(app, partial)
  startPolling()
  return { ok: true, integrations: integrationStatus(saved) }
})

ipcMain.handle('import-env', () => {
  const { execFileSync } = require('child_process')
  const script = path.join(__dirname, '..', 'scripts', 'setup-from-env.cjs')
  try {
    execFileSync('node', [script], {
      cwd: path.join(__dirname, '..'),
      stdio: 'pipe',
      env: process.env,
    })
  } catch {
    /* fallback: fundir .env no config ao lado do exe */
  }
  persistMergedSecrets(app)
  startPolling()
  return { ok: true, integrations: integrationStatus(loadHubConfig(app)) }
})

ipcMain.handle('refresh-now', () => buildSnapshot(app))

ipcMain.handle('github-start-device', async () => {
  const cfg = loadHubConfig(app)
  const clientId = (cfg.github?.clientId || '').trim()
  if (!clientId) {
    return {
      error: 'Coloca github.clientId no config.local.json (OAuth App com Device Flow activo).',
    }
  }
  const flow = await startDeviceFlow(clientId)
  return {
    userCode: flow.user_code,
    verificationUri: flow.verification_uri,
    deviceCode: flow.device_code,
    interval: flow.interval || 5,
    expiresIn: flow.expires_in || 900,
    clientId,
  }
})

ipcMain.handle('github-poll-device', async (_e, { clientId, deviceCode, interval }) => {
  const wait = Math.max(3, Number(interval) || 5) * 1000
  return new Promise((resolve) => {
    const deadline = Date.now() + 15 * 60 * 1000
    devicePollTimer = setInterval(async () => {
      if (Date.now() > deadline) {
        clearInterval(devicePollTimer)
        resolve({ error: 'Tempo esgotado — tenta outra vez.' })
        return
      }
      try {
        const tok = await pollDeviceToken(clientId, deviceCode)
        if (tok.access_token) {
          clearInterval(devicePollTimer)
          saveHubConfig(app, { github: { token: tok.access_token, clientId } })
          startPolling()
          resolve({ ok: true })
          return
        }
        if (tok.error && tok.error !== 'authorization_pending') {
          clearInterval(devicePollTimer)
          resolve({ error: tok.error_description || tok.error })
        }
      } catch (e) {
        clearInterval(devicePollTimer)
        resolve({ error: e.message })
      }
    }, wait)
  })
})

ipcMain.handle('github-try-gh-cli', async () => {
  const token = await tryGhCliToken()
  if (!token) return { ok: false }
  saveHubConfig(app, { github: { token } })
  startPolling()
  return { ok: true }
})

ipcMain.handle('open-config-file', () => {
  const p = getLocalConfigPath(app)
  shell.showItemInFolder(p)
  return p
})

ipcMain.handle('dismiss-tab', async (_e, { tab, items }) => {
  const store = loadDismissed(app)
  const map = { alerts: 'alerts', overview: 'recommendations', metrics: 'sentry', cicd: 'ci' }
  const key = map[tab]
  if (!key || !Array.isArray(items)) return { ok: false }
  const set = new Set(store[key])
  for (const id of items) set.add(id)
  store[key] = [...set]
  saveDismissed(app, store)
  return { ok: true, snapshot: await buildSnapshot(app) }
})

ipcMain.handle('dismiss-all-tabs', async () => {
  saveDismissed(app, { alerts: [], recommendations: [], sentry: [], ci: [] })
  return { ok: true, snapshot: await buildSnapshot(app) }
})

app.whenReady().then(async () => {
  const setup = ensureLocalConfig(app)
  persistMergedSecrets(app)
  const cfg = loadHubConfig(app)
  if (!cfg.github?.token) {
    const t = await tryGhCliToken()
    if (t) saveHubConfig(app, { github: { token: t } })
  }
  await showFirstRunDialog(setup)
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  stopPolling()
  if (devicePollTimer) clearInterval(devicePollTimer)
  if (process.platform !== 'darwin') app.quit()
})
