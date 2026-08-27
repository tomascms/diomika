const PLAYBOOKS = {
  'api-down': {
    title: 'API offline',
    file: 'deploy/deploy_vm.py',
    steps: [
      'Confirma https://api.diomika.com/health no browser.',
      'Verifica Cloudflare Tunnel (Zero Trust) e a VM GCP.',
      'Corre «Health check» e depois «Verify production» neste hub.',
      'Se a VM estiver ok: python deploy/deploy_vm.py',
    ],
    actions: ['run-health', 'run-monitor-check', 'run-verify', 'copy-cursor-prompt'],
  },
  latency: {
    title: 'Latência elevada',
    file: 'backend-api/core/middleware.py',
    steps: [
      'Vê erros Axiom e Sentry na mesma janela temporal.',
      'Confirma carga na e2-micro (swap / docker).',
      'Corre verify_production para isolar smoke vs carga.',
    ],
    actions: ['run-health', 'run-verify', 'copy-cursor-prompt'],
  },
  sentry: {
    title: 'Erro Sentry',
    file: null,
    steps: [
      'Abre o issue no Sentry (link no incidente).',
      'Copia o prompt Cursor com stack e ficheiro suspeito.',
      'Corrige no Cursor; depois marca o issue como resolvido.',
    ],
    actions: ['copy-cursor-prompt', 'sentry-resolve', 'open-path'],
  },
  uptime: {
    title: 'Monitor down',
    file: 'deploy/monitor_check.py',
    steps: [
      'Corre Health check local.',
      'Confirma UptimeRobot e o workflow GitHub Uptime.',
      'Se só um alvo falha, isola API vs loja vs BD.',
    ],
    actions: ['run-health', 'run-monitor-check'],
  },
  'ci-fail': {
    title: 'CI falhou',
    file: '.github/workflows/ci.yml',
    steps: [
      'Abre a run falhada no GitHub Actions.',
      'Reproduz o job localmente se for teste/security gate.',
      'Não ignores falhas de security_gate / verify_rls.',
    ],
    actions: ['copy-cursor-prompt'],
  },
  'waf-spike': {
    title: 'Pico WAF / ataques',
    file: 'deploy/cloudflare/waf_rules.json',
    steps: [
      'Confirma se são probes a /admin (esperado) ou volume anómalo.',
      'Se admin devolver 200 sem gate → incidente crítico admin-exposed.',
      'Revê regras WAF e rate limits se o pico for abusivo.',
    ],
    actions: ['run-health', 'copy-cursor-prompt'],
  },
  'admin-exposed': {
    title: 'Superfície admin exposta',
    file: 'backend-api/core/path_guard.py',
    steps: [
      'URGENTE: /admin ou /system respondeu sem X-Diomika-Desktop.',
      'Activa SECURITY_LOCKDOWN se necessário.',
      'Confirma WAF rule block-admin-system-except-desktop.',
    ],
    actions: ['run-health', 'copy-cursor-prompt', 'open-path'],
  },
  'synthetic-fail': {
    title: 'Jornada sintética falhou',
    file: 'frontend-web/src/router/index.js',
    steps: [
      'Homepage pode estar up mas o catálogo/API falhou.',
      'Testa /categorias e catálogo no browser.',
      'Corre monitor_check e verify_production.',
    ],
    actions: ['run-health', 'run-monitor-check', 'run-verify'],
  },
  'analytics-drop': {
    title: 'Queda de tráfego',
    file: 'frontend-web/src/lib/posthog.js',
    steps: [
      'Confirma PostHog consentimento / chave EU.',
      'Compara com Uptime (loja pode estar down).',
      'Verifica Pages deploy recente.',
    ],
    actions: ['run-health', 'copy-cursor-prompt'],
  },
  'business-stall': {
    title: 'Tráfego sem pedidos',
    file: 'frontend-web/src/views/CartView.vue',
    steps: [
      'Há visitas mas poucos/zero orçamentos.',
      'Testa formulário + Turnstile em produção.',
      'Vê erros Sentry no submit de contacto/orçamento.',
    ],
    actions: ['run-health', 'copy-cursor-prompt'],
  },
  'business-unread': {
    title: 'Inbox comercial',
    file: null,
    steps: ['Abre o backoffice e marca/responde orçamentos e mensagens.'],
    actions: [],
  },
  'setup-analytics': {
    title: 'Analytics sem dados',
    file: 'monitor-hub/scripts/setup-from-env.cjs',
    steps: ['Configuração → Importar do .env (Supabase + PostHog).'],
    actions: [],
  },
}

function getPlaybook(action) {
  return PLAYBOOKS[action] || {
    title: action || 'Incidente',
    file: null,
    steps: ['Rever o detalhe do alerta e o contexto nas abas Analytics / Segurança.'],
    actions: ['run-health', 'copy-cursor-prompt'],
  }
}

function buildCursorPrompt(incident, snapshot) {
  const pb = getPlaybook(incident.action)
  const lines = [
    'Corrige o seguinte problema de produção Diomika.',
    '',
    `Título: ${incident.title}`,
    `Severidade: ${incident.severity || '—'}`,
    `Acção/playbook: ${incident.action || '—'}`,
    `Detalhe: ${incident.detail || '—'}`,
    incident.file || pb.file ? `Ficheiro suspeito: ${incident.file || pb.file}` : '',
    '',
    'Contexto hub:',
    `- API ok: ${snapshot?.health?.api?.ok}`,
    `- Site ok: ${snapshot?.health?.site?.ok}`,
    `- Sentry unresolved: ${snapshot?.sentry?.unresolved}`,
    `- Score: ${snapshot?.score}`,
    '',
    'Passos sugeridos:',
    ...pb.steps.map((s, i) => `${i + 1}. ${s}`),
    '',
    'Repo: Diomika (FastAPI + Vue + Electron). Não commits secrets.',
  ]
  return lines.filter(Boolean).join('\n')
}

module.exports = { PLAYBOOKS, getPlaybook, buildCursorPrompt }
