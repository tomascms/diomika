const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('monitorHub', {
  getConfig: () => ipcRenderer.invoke('get-config'),
  onConfig: (cb) => {
    ipcRenderer.on('config', (_e, data) => cb(data))
  },
  openTab: (projectId, tabId, url, local) => {
    ipcRenderer.send('open-tab', { projectId, tabId, url, local })
  },
  getHubConfig: () => ipcRenderer.invoke('get-hub-config'),
  getRecentAlerts: (limit) => ipcRenderer.invoke('get-recent-alerts', limit),
  setChromeMetrics: (metrics) => {
    ipcRenderer.send('chrome-metrics', metrics)
  },
  reloadActive: () => ipcRenderer.send('reload-active'),
})
