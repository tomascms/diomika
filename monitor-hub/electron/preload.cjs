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
  dismissTab: (tab, items) => ipcRenderer.invoke('dismiss-tab', { tab, items }),
  dismissAll: () => ipcRenderer.invoke('dismiss-all-tabs'),
})
