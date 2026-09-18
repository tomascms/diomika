/**
 * Diomika Backoffice — Electron (Win/Mac/Linux).
 * Proxy /api → API cloud com header de gate (WAF + API).
 * Usa electron.net (Chromium) — fiável com antivirus/SSL inspection (AVG, etc.).
 */
const { app, BrowserWindow, shell, dialog, net } = require('electron')
const http = require('http')
const fs = require('fs')
const path = require('path')

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

function apiTargetUrl(reqUrl) {
  const incoming = new URL(reqUrl || '/', 'http://127.0.0.1')
  const targetPath = (incoming.pathname.replace(/^\/api/, '') || '/') + incoming.search
  return `${API_ORIGIN}${targetPath.startsWith('/') ? targetPath : `/${targetPath}`}`
}

function apiHealthOk() {
  return new Promise((resolve) => {
    const req = net.request({ method: 'GET', url: `${API_ORIGIN}/health` })
    req.setHeader('User-Agent', 'DiomikaBackoffice/1.0')
    if (DESKTOP_GATE) req.setHeader('x-diomika-desktop', DESKTOP_GATE)
    req.on('response', (res) => {
      res.on('data', () => {})
      res.on('end', () => resolve(res.statusCode >= 200 && res.statusCode < 500))
    })
    req.on('error', () => resolve(false))
    req.end()
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

// Só estes headers do renderer podem ir para electron.net — sec-fetch-* etc. causam ERR_INVALID_ARGUMENT
const FORWARD_HEADERS = new Set([
  'accept',
  'content-type',
  'authorization',
  'x-api-key',
  'idempotency-key',
])

function copyForwardHeaders(req, upstream) {
  for (const [key, value] of Object.entries(req.headers)) {
    const lower = key.toLowerCase()
    if (!FORWARD_HEADERS.has(lower)) continue
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) value.forEach((v) => upstream.setHeader(key, v))
    else upstream.setHeader(key, String(value))
  }
}

function proxyToApi(req, res) {
  const targetUrl = apiTargetUrl(req.url)
  const method = (req.method || 'GET').toUpperCase()

  const upstream = net.request({
    method,
    url: targetUrl,
    redirect: 'follow',
  })

  upstream.setHeader('accept-encoding', 'identity')
  upstream.setHeader('user-agent', 'DiomikaBackoffice/1.0')
  upstream.setHeader('accept', 'application/json')
  if (DESKTOP_GATE) upstream.setHeader('x-diomika-desktop', DESKTOP_GATE)
  copyForwardHeaders(req, upstream)

  upstream.on('response', (upRes) => {
    const outHeaders = { ...upRes.headers }
    delete outHeaders['cross-origin-resource-policy']
    delete outHeaders['cross-origin-opener-policy']
    delete outHeaders['content-encoding']
    delete outHeaders['content-length']
    delete outHeaders['transfer-encoding']
    delete outHeaders['connection']
    delete outHeaders['keep-alive']
    const chunks = []
    upRes.on('data', (chunk) => chunks.push(Buffer.from(chunk)))
    upRes.on('end', () => {
      const body = Buffer.concat(chunks)
      if (body.length) outHeaders['content-length'] = String(body.length)
      if (!res.headersSent) res.writeHead(upRes.statusCode || 502, outHeaders)
      res.end(body)
    })
    upRes.on('error', () => {
      if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify({ detail: 'Falha ao ler resposta da API.' }))
    })
  })

  upstream.on('error', (err) => {
    const msg = JSON.stringify({
      detail: `API inacessível (${API_ORIGIN}). Verifique a internet. (${err.message})`,
    })
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
    res.end(msg)
  })

  if (method === 'GET' || method === 'HEAD') {
    upstream.end()
    return
  }

  req.on('data', (chunk) => upstream.write(chunk))
  req.on('end', () => upstream.end())
  req.on('error', () => {
    try {
      upstream.abort()
    } catch {
      /* ignore */
    }
  })
  req.resume()
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
  localServer = await createWindow()
  // Estado online/offline fica no painel (AppShell) — sem popup ao arrancar.
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
