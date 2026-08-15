/** Copia instaladores de release/ para ../cliente-backoffice (nomes fixos). */
const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const release = path.join(root, 'release')
const dest = path.join(root, '..', 'cliente-backoffice')

const map = [
  ['Diomika-Backoffice-1.0.0-windows.exe', 'Diomika-Backoffice-1.0.0-windows.exe'],
  ['Diomika-Backoffice-1.0.0-mac.dmg', 'Diomika-Backoffice-1.0.0-mac.dmg'],
  ['Diomika-Backoffice-1.0.0-linux.AppImage', 'Diomika-Backoffice-1.0.0-linux.AppImage'],
]

if (!fs.existsSync(dest)) {
  fs.mkdirSync(dest, { recursive: true })
}

let copied = 0
for (const [srcName, dstName] of map) {
  const src = path.join(release, srcName)
  if (!fs.existsSync(src)) {
    console.warn(`AVISO: em falta em release/ — ${srcName}`)
    continue
  }
  const dst = path.join(dest, dstName)
  fs.copyFileSync(src, dst)
  console.log(`OK — ${dstName}`)
  copied += 1
}

if (!copied) {
  console.error('ERRO: nenhum ficheiro copiado. Corra npm run dist:win (e mac/linux na CI).')
  process.exit(1)
}
