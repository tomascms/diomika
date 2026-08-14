/**
 * Diomika Backoffice — Electron (Win/Mac/Linux).
 * Proxy /api → API cloud com header de gate (WAF + API).
 */
const { app, BrowserWindow, shell, dialog } = require('electron')
const http = require('http')
const https = require('https')
const fs = require('fs')
const path = require('path')
const { URL } = require('url')

const isDev = Boolean(process.env.VITE_DEV_SERVER_URL)
const API_ORIGIN = (
  process.env.DIOMIKA_API_ORIGIN ||
  require('./api-origin.cjs') ||
  'https://api.diomika.com'
).replace(/\/+$/, '')

function loadDesktopGate() {
  try {
    const g = require('./desktop-gate.cjs')
    if (typeof g === 'string' && g.trim()) return g.trim()
  } catch {
    /* missing in dev without script */
  }
  return (process.env.DIOMIKA_DESKTOP_GATE || '').trim()
}

const DESKTOP_GATE = loadDesktopGate()
const DIST_DIR = path.join(__dirname, '../dist')

function transportFor(url) {
  return url.protocol === 'https:' ? https : http
}

function apiHealthOk() {
  return new Promise((resolve) => {
    const target = new URL(`${API_ORIGIN}/health`)
    const lib = transportFor(target)
    const req = lib.get(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port || (target.protocol === 'https:' ? 443 : 80),
        path: target.pathname + target.search,
        timeout: 8000,
        headers: { 'User-Agent': 'DiomikaBackoffice/1.0' },
      },
      (res) => {
        res.resume()
        resolve(res.statusCode >= 200 && res.statusCode < 500)
      },
    )
    req.on('error', () => resolve(false))
    req.on('timeout', () => {
      req.destroy()
      resolve(false)
    })
  })
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.map': 'application/json',
}

function safeJoin(root, reqPath) {
  const decoded = decodeURIComponent(reqPath.split('?')[0] || '/')
  const cleaned = decoded.replace(/^\/+/, '')
  const full = path.normalize(path.join(root, cleaned || 'index.html'))
  if (!full.startsWith(path.normalize(root + path.sep)) && full !== path.normalize(root)) {
    return null
  }
  return full
}

function proxyToApi(req, res) {
  const incoming = new URL(req.url || '/', 'http://127.0.0.1')
  const targetPath = (incoming.pathname.replace(/^\/api/, '') || '/') + incoming.search
  const target = new URL(targetPath, API_ORIGIN + '/')
  const lib = transportFor(target)

  const headers = { ...req.headers, host: target.host }
  delete headers.origin
  delete headers.referer
  delete headers['accept-encoding']
  headers['user-agent'] = 'DiomikaBackoffice/1.0'
  if (DESKTOP_GATE) headers['x-diomika-desktop'] = DESKTOP_GATE

  const upstream = lib.request(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port || (target.protocol === 'https:' ? 443 : 80),
      method: req.method,
      path: target.pathname + target.search,
      headers,
    },
    (upRes) => {
      const outHeaders = { ...upRes.headers }
      delete outHeaders['cross-origin-resource-policy']
      delete outHeaders['cross-origin-opener-policy']
      res.writeHead(upRes.statusCode || 502, outHeaders)
      upRes.pipe(res)
    },
  )

  upstream.on('error', (err) => {
    const msg = JSON.stringify({
      detail: `API inacessível (${API_ORIGIN}). Verifique a internet. (${err.message})`,
    })
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
    res.end(msg)
  })

  req.pipe(upstream)
}

function serveStatic(req, res) {
  const incoming = new URL(req.url || '/', 'http://127.0.0.1')
  let filePath = safeJoin(DIST_DIR, incoming.pathname === '/' ? '/index.html' : incoming.pathname)
  if (!filePath) {
    res.writeHead(403)
    res.end('Forbidden')
    return
  }
  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    filePath = path.join(DIST_DIR, 'index.html')
  }
  if (!fs.existsSync(filePath)) {
    res.writeHead(404)
    res.end('UI em falta')
    return
  }
  const ext = path.extname(filePath).toLowerCase()
  res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' })
  fs.createReadStream(filePath).pipe(res)
}

function createLocalServer() {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      try {
        const pathname = new URL(req.url || '/', 'http://127.0.0.1').pathname
        if (pathname === '/api' || pathname.startsWith('/api/')) {
          proxyToApi(req, res)
          return
        }
        if (req.method !== 'GET' && req.method !== 'HEAD') {
          res.writeHead(405)
          res.end('Method Not Allowed')
          return
        }
        serveStatic(req, res)
      } catch (err) {
        res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' })
        res.end(String(err && err.message ? err.message : err))
      }
    })
    server.on('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address()
      resolve({ server, port: addr.port })
    })
  })
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1320,
    height: 880,
    minWidth: 960,
    minHeight: 640,
    title: 'Diomika Backoffice',
    backgroundColor: '#0c0e14',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://127.0.0.1') || url.startsWith('http://localhost')) {
      return { action: 'deny' }
    }
    shell.openExternal(url)
    return { action: 'deny' }
  })

  if (isDev) {
    await win.loadURL(process.env.VITE_DEV_SERVER_URL)
    return null
  }

  const { server, port } = await createLocalServer()
  await win.loadURL(`http://127.0.0.1:${port}/`)
  return server
}

let localServer = null

app.whenReady().then(async () => {
  if (!isDev && !DESKTOP_GATE) {
    dialog.showErrorBox(
      'Build incompleto',
      'Falta DIOMIKA_DESKTOP_GATE neste instalador. Peça um build novo à Diomika.',
    )
  }
  if (!isDev) {
    const ok = await apiHealthOk()
    if (!ok) {
      dialog.showErrorBox(
        'Sem ligação à API',
        `Não foi possível contactar ${API_ORIGIN}.\nConfirme a internet e tente de novo.`,
      )
    }
  }
  localServer = await createWindow()
})

app.on('window-all-closed', () => {
  if (localServer) {
    try {
      localServer.close()
    } catch {
      /* ignore */
    }
    localServer = null
  }
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow().then((server) => {
      localServer = server
    })
  }
})
