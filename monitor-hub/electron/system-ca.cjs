/**
 * Garante que fetch/https usam as CAs do sistema (Windows).
 * Sem isto, Node/Electron falha com "fetch failed" / "unable to verify the first certificate"
 * em redes com SSL inspection ou cadeias Cloudflare.
 */
function applySystemCA() {
  try {
    const tls = require('tls')
    if (typeof tls.getCACertificates === 'function' && typeof tls.setDefaultCACertificates === 'function') {
      tls.setDefaultCACertificates(tls.getCACertificates('system'))
      return 'system-ca'
    }
  } catch {
    /* ignore */
  }
  return null
}

module.exports = { applySystemCA }
