const { app, BrowserWindow, WebContentsView, ipcMain, session } = require('electron')
const path = require('path')
const fs = require('fs')

const CONFIG_PATH = path.join(__dirname, '..', 'projects.json')

function loadConfig() {
  const raw = fs.readFileSync(CONFIG_PATH, 'utf8')
  return JSON.parse(raw)
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

function showView(projectId, tabId, url) {
  if (!mainWindow) return
  const key = viewKey(projectId, tabId)
  hideAllViews()

  let view = views.get(key)
  if (!view) {
    const partition = `persist:monitor-${projectId}`
    view = new WebContentsView({
      webPreferences: {
        partition,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    })
    views.set(key, view)
    view.webContents.setWindowOpenHandler(({ url: openUrl }) => {
      view.webContents.loadURL(openUrl)
      return { action: 'deny' }
    })
    view.webContents.loadURL(url)
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

ipcMain.on('chrome-metrics', (_e, metrics) => {
  if (metrics?.chromeHeight) chromeHeight = Math.round(metrics.chromeHeight)
  if (metrics?.sidebarWidth) sidebarWidth = Math.round(metrics.sidebarWidth)
  layoutActiveView()
})

ipcMain.on('open-tab', (_e, { projectId, tabId, url }) => {
  showView(projectId, tabId, url)
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
