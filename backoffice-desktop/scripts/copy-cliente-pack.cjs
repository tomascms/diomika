/** Copia instaladores de release/ para pastas cliente-backoffice. */
const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const release = path.join(root, 'release')
const releaseFresh = path.join(root, 'release-fresh')
const version = require('../package.json').version

const artifacts = [
  `Diomika-Backoffice-${version}-windows.exe`,
  `Diomika-Backoffice-${version}-mac.dmg`,
  `Diomika-Backoffice-${version}-linux.AppImage`,
]

const destDirs = [
  path.join(root, '..', 'cliente-backoffice'),
  path.join(root, '..', '..', 'cliente-backoffice'),
]

for (const dest of destDirs) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true })
  }
}

let copied = 0
const missing = []

for (const name of artifacts) {
  let src = path.join(release, name)
  if (!fs.existsSync(src)) {
    src = path.join(releaseFresh, name)
  }
  if (!fs.existsSync(src)) {
    missing.push(name)
    continue
  }
  for (const dest of destDirs) {
    const dst = path.join(dest, name)
    fs.copyFileSync(src, dst)
    console.log(`OK — ${path.relative(root, dst) || dst}`)
    copied += 1
  }
}

if (missing.length) {
  console.warn(`AVISO: em falta em release/ — ${missing.join(', ')}`)
}

if (!copied) {
  console.error('ERRO: nenhum ficheiro copiado.')
  process.exit(1)
}
