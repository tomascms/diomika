const { spawn } = require('child_process')
const path = require('path')
const { shell } = require('electron')
const { resolveIssue } = require('./services/sentry.cjs')
const { loadHubConfig } = require('./config.cjs')
const { getPlaybook, buildCursorPrompt } = require('./playbooks.cjs')
const { getUserRoot } = require('./paths.cjs')

function repoRoot(app) {
  if (app.isPackaged) return getUserRoot(app)
  return path.join(__dirname, '..', '..')
}

function resolveRepoPath(app, rel) {
  if (!rel) return null
  const root = app.isPackaged ? getUserRoot(app) : path.join(__dirname, '..', '..')
  return path.join(root, rel.replace(/^\//, ''))
}

function getClipboard() {
  return require('electron').clipboard
}

function getNotification() {
  return require('electron').Notification
}

async function runWhitelisted(app, actionId, payload = {}, onChunk) {
  const cfg = loadHubConfig(app)
  const root = app.isPackaged ? getUserRoot(app) : path.join(__dirname, '..', '..')

  if (actionId === 'run-health') {
    const { probeHealth } = require('./services/health.cjs')
    const { runSynthetics } = require('./synthetics.cjs')
    const health = await probeHealth(cfg)
    const syn = await runSynthetics(cfg)
    return { ok: health.api.ok && health.site.ok && syn.ok, health, synthetics: syn }
  }

  if (actionId === 'run-verify' || actionId === 'run-monitor-check') {
    const script =
      actionId === 'run-verify'
        ? path.join(root, 'deploy', 'verify_production.py')
        : path.join(root, 'deploy', 'monitor_check.py')
    const args = actionId === 'run-monitor-check' ? [script, '--ready'] : [script]
    return runPython(args, root, onChunk)
  }

  if (actionId === 'open-path') {
    const target = resolveRepoPath(app, payload.path || payload.file)
    if (!target) return { ok: false, error: 'Sem ficheiro' }
    const err = await shell.openPath(target)
    return { ok: !err, error: err || null, path: target }
  }

  if (actionId === 'sentry-resolve') {
    const r = await resolveIssue(cfg, payload.issueId)
    return r
  }

  if (actionId === 'copy-cursor-prompt') {
    const text = buildCursorPrompt(payload.incident || {}, payload.snapshot || {})
    getClipboard().writeText(text)
    return { ok: true, chars: text.length }
  }

  if (actionId === 'get-playbook') {
    return { ok: true, playbook: getPlaybook(payload.action) }
  }

  return { ok: false, error: `Acção não permitida: ${actionId}` }
}

function runPython(args, cwd, onChunk) {
  return new Promise((resolve) => {
    const child = spawn('python', args, { cwd, env: process.env, shell: false })
    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (buf) => {
      const s = buf.toString()
      stdout += s
      if (onChunk) onChunk(s)
    })
    child.stderr.on('data', (buf) => {
      const s = buf.toString()
      stderr += s
      if (onChunk) onChunk(s)
    })
    child.on('error', (e) => resolve({ ok: false, error: e.message, stdout, stderr }))
    child.on('close', (code) => resolve({ ok: code === 0, code, stdout, stderr }))
  })
}

function notifyCritical(title, body) {
  const Notification = getNotification()
  if (!Notification.isSupported()) return
  const n = new Notification({ title: title || 'Diomika Ops', body: body || 'Estado crítico', urgency: 'critical' })
  n.show()
}

module.exports = { runWhitelisted, resolveRepoPath, notifyCritical, repoRoot }
