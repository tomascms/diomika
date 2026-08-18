const fs = require('fs')
const path = require('path')

const HUB = path.join(__dirname, '..')
const release = path.join(HUB, 'release')
const files = fs
  .readdirSync(release)
  .filter((f) => f.startsWith('Diomika-Command-Center-') && f.endsWith('-windows.exe'))
  .sort()

if (!files.length) {
  console.error('X portable não encontrado em release/')
  process.exit(1)
}

const name = files[files.length - 1]
const src = path.join(release, name)
const dest = path.join(HUB, name)
fs.copyFileSync(src, dest)

const desktop = path.join(process.env.USERPROFILE || '', 'Desktop')
const configSrc = path.join(HUB, 'config.local.json')
const desktopExe = path.join(desktop, name)
const desktopCfg = path.join(desktop, 'config.local.json')

fs.copyFileSync(src, desktopExe)
if (fs.existsSync(configSrc)) {
  fs.copyFileSync(configSrc, desktopCfg)
}

for (const old of fs.readdirSync(desktop).filter((f) => f.startsWith('Diomika-Command-Center-') && f.endsWith('-windows.exe') && f !== name)) {
  try {
    fs.unlinkSync(path.join(desktop, old))
  } catch {
    /* ignore */
  }
}

console.log('OK', path.basename(dest))
console.log('OK Desktop', desktopExe)
