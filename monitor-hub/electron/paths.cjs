const path = require('path')
const fs = require('fs')

/** Pasta gravável: ao lado do .exe (portable) ou raiz do repo em dev. */
function getUserRoot(app) {
  if (app.isPackaged) {
    return path.dirname(process.execPath)
  }
  return path.join(__dirname, '..')
}

/** Ficheiros embebidos no build (extraResources/hub). */
function getBundledRoot(app) {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'hub')
  }
  return path.join(__dirname, '..')
}

function resolveOptionalFile(userRoot, bundledRoot, name) {
  const userPath = path.join(userRoot, name)
  if (fs.existsSync(userPath)) return userPath
  const bundledPath = path.join(bundledRoot, name)
  if (fs.existsSync(bundledPath)) return bundledPath
  return userPath
}

function getProjectsPath(app) {
  const userRoot = getUserRoot(app)
  const bundledRoot = getBundledRoot(app)
  return resolveOptionalFile(userRoot, bundledRoot, 'projects.json')
}

function getLocalConfigPath(app) {
  return path.join(getUserRoot(app), 'config.local.json')
}

function getLocalExamplePath(app) {
  return resolveOptionalFile(
    getUserRoot(app),
    getBundledRoot(app),
    'config.local.example.json',
  )
}

function getUiPath(app, fileName) {
  if (app.isPackaged) {
    return path.join(__dirname, '..', 'ui', fileName)
  }
  return path.join(__dirname, '..', 'ui', fileName)
}

function ensureLocalConfig(app) {
  const localPath = getLocalConfigPath(app)
  if (fs.existsSync(localPath)) {
    return { firstRun: false, localPath, userRoot: getUserRoot(app) }
  }
  const examplePath = getLocalExamplePath(app)
  if (!fs.existsSync(examplePath)) {
    return { firstRun: false, localPath, userRoot: getUserRoot(app), missingExample: true }
  }
  fs.copyFileSync(examplePath, localPath)
  return { firstRun: true, localPath, userRoot: getUserRoot(app) }
}

function readAlertsLogPath(app, hubConfig) {
  const fromConfig = (hubConfig?.alertsLogPath || '').trim()
  if (fromConfig) {
    return path.isAbsolute(fromConfig)
      ? fromConfig
      : path.join(getUserRoot(app), fromConfig)
  }
  if (!app.isPackaged) {
    return path.join(__dirname, '..', '..', 'deploy', 'alerts.log')
  }
  return path.join(getUserRoot(app), 'alerts.log')
}

module.exports = {
  getUserRoot,
  getBundledRoot,
  getProjectsPath,
  getLocalConfigPath,
  getLocalExamplePath,
  getUiPath,
  ensureLocalConfig,
  readAlertsLogPath,
}
