const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('monitorHub', {
  getConfig: () => ipcRenderer.invoke('get-config'),
  onConfig: (cb) => {
    ipcRenderer.on('config', (_e, data) => cb(data))
  },
  openTab: (projectId, tabId, url) => {
    ipcRenderer.send('open-tab', { projectId, tabId, url })
  },
  setChromeMetrics: (metrics) => {
    ipcRenderer.send('chrome-metrics', metrics)
  },
  reloadActive: () => ipcRenderer.send('reload-active'),
})
