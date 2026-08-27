const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('hub', {
  getConfig: () => ipcRenderer.invoke('get-config'),
  saveConfig: (partial) => ipcRenderer.invoke('save-config', partial),
  importEnv: () => ipcRenderer.invoke('import-env'),
  refreshNow: () => ipcRenderer.invoke('refresh-now'),
  onSnapshot: (cb) => {
    ipcRenderer.on('snapshot', (_e, data) => cb(data))
  },
  onSnapshotError: (cb) => {
    ipcRenderer.on('snapshot-error', (_e, msg) => cb(msg))
  },
  githubStartDevice: () => ipcRenderer.invoke('github-start-device'),
  githubPollDevice: (payload) => ipcRenderer.invoke('github-poll-device', payload),
  githubTryGhCli: () => ipcRenderer.invoke('github-try-gh-cli'),
  openConfigFile: () => ipcRenderer.invoke('open-config-file'),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  dismissTab: (tab, items) => ipcRenderer.invoke('dismiss-tab', { tab, items }),
  dismissAll: (snapshot) => ipcRenderer.invoke('dismiss-all-tabs', { snapshot }),
  restoreDismissed: () => ipcRenderer.invoke('restore-dismissed'),
  incidentAck: (key) => ipcRenderer.invoke('incident-ack', key),
  incidentResolve: (key) => ipcRenderer.invoke('incident-resolve', key),
  getIncidents: () => ipcRenderer.invoke('get-incidents'),
  runAction: (actionId, payload) => ipcRenderer.invoke('run-action', { actionId, payload }),
  getPlaybook: (action) => ipcRenderer.invoke('get-playbook', action),
  copyPrompt: (incident, snapshot) => ipcRenderer.invoke('copy-prompt', { incident, snapshot }),
  exportReport: () => ipcRenderer.invoke('export-report'),
})
