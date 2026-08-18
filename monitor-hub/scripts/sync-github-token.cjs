const { execFileSync } = require('child_process')
const fs = require('fs')
const path = require('path')
const { saveHubConfig } = require('../electron/config.cjs')

const GH = process.platform === 'win32'
  ? 'C:\\Program Files\\GitHub CLI\\gh.exe'
  : 'gh'

function getGhToken() {
  try {
    return execFileSync(GH, ['auth', 'token'], { encoding: 'utf8' }).trim()
  } catch {
    return ''
  }
}

/** Mock mínimo de app Electron para reutilizar config.cjs */
const app = { isPackaged: false }

function main() {
  const token = getGhToken()
  if (!token) {
    console.error('X gh não autenticado — corre gh auth login')
    process.exit(1)
  }
  saveHubConfig(app, { github: { token } })
  console.log('OK GitHub token guardado em config.local.json')
}

main()
