const { app, BrowserWindow, WebContentsView, ipcMain, session } = require('electron')
const path = require('path')
const fs = require('fs')

const CONFIG_PATH = path.join(__dirname, '..', 'projects.json')
const LOCAL_CONFIG_PATH = path.join(__dirname, '..', 'config.local.json')

function loadConfig() {
  const raw = fs.readFileSync(CONFIG_PATH, 'utf8')
  const base = JSON.parse(raw)
  if (fs.existsSync(LOCAL_CONFIG_PATH)) {
    try {
      const local = JSON.parse(fs.readFileSync(LOCAL_CONFIG_PATH, 'utf8'))
      base.hub = { ...(base.hub || {}), ...local }
    } catch {
      /* ignore invalid local config */
    }
  }
  return base
}

function readRecentAlerts(limit = 30) {
  const logPath = path.join(__dirname, '..', '..', 'deploy', 'alerts.log')
  if (!fs.existsSync(logPath)) return []
  try {
    const lines = fs.readFileSync(logPath, 'utf8').trim().split('\n').filter(Boolean)
    return lines.slice(-limit).map((line) => {
      try {
        return JSON.parse(line)
      } catch {
        return { text: line }
      }
    })
  } catch {
    return []
  }
}

/** @type {BrowserWindow | null} */
let mainWindow = null
/** @type {Map<string, WebContentsView>} */
const views = new Map()
let activeKey = null
let chromeHeight = 52
let sidebarWidth = 200

function viewKey(projectId, tabId) {
  return `${projectId}::${tabId}`
}

function layoutActiveView() {
  if (!mainWindow || !activeKey) return
  const view = views.get(activeKey)
  if (!view) return
  const [w, h] = mainWindow.getContentSize()
  view.setBounds({
    x: sidebarWidth,
    y: chromeHeight,
    width: Math.max(100, w - sidebarWidth),
    height: Math.max(100, h - chromeHeight),
  })
}

function hideAllViews() {
  if (!mainWindow) return
  for (const view of views.values()) {
    try {
      mainWindow.contentView.removeChildView(view)
    } catch {
      /* already detached */
    }
  }
}

function showView(projectId, tabId, url, localFile) {
  if (!mainWindow) return
  const key = viewKey(projectId, tabId)
  hideAllViews()

  let view = views.get(key)
  if (!view) {
    const partition = localFile ? 'persist:monitor-local' : `persist:monitor-${projectId}`
    view = new WebContentsView({
      webPreferences: {
        partition,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        preload: path.join(__dirname, 'preload.cjs'),
      },
    })
    views.set(key, view)
    view.webContents.setWindowOpenHandler(({ url: openUrl }) => {
      view.webContents.loadURL(openUrl)
      return { action: 'deny' }
    })
    if (localFile) {
      view.webContents.loadFile(path.join(__dirname, '..', 'ui', localFile))
    } else {
      view.webContents.loadURL(url)
    }
  }

  mainWindow.contentView.addChildView(view)
  activeKey = key
  layoutActiveView()
}

function createWindow() {
  const config = loadConfig()
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'Monitor Hub',
    backgroundColor: '#0f1419',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  mainWindow.loadFile(path.join(__dirname, '..', 'ui', 'index.html'))

  mainWindow.on('resize', layoutActiveView)
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents.send('config', config)
  })
}

ipcMain.handle('get-config', () => loadConfig())

ipcMain.handle('get-hub-config', () => {
  const cfg = loadConfig()
  return cfg.hub || {}
})

ipcMain.handle('get-recent-alerts', (_e, limit) => readRecentAlerts(limit || 30))

ipcMain.on('chrome-metrics', (_e, metrics) => {
  if (metrics?.chromeHeight) chromeHeight = Math.round(metrics.chromeHeight)
  if (metrics?.sidebarWidth) sidebarWidth = Math.round(metrics.sidebarWidth)
  layoutActiveView()
})

ipcMain.on('open-tab', (_e, { projectId, tabId, url, local }) => {
  showView(projectId, tabId, url, local || null)
})

ipcMain.on('reload-active', () => {
  if (!activeKey) return
  const view = views.get(activeKey)
  if (view) view.webContents.reload()
})

app.whenReady().then(() => {
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
