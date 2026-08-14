let config = { projects: [] }
let activeProjectId = null
let activeTabId = null

const projectsEl = document.getElementById('projects')
const tabsEl = document.getElementById('tabs')
const reloadBtn = document.getElementById('reload')

function reportMetrics() {
  const sidebar = document.getElementById('sidebar')
  const tabsBar = document.getElementById('tabs-bar')
  window.monitorHub.setChromeMetrics({
    sidebarWidth: sidebar.getBoundingClientRect().width,
    chromeHeight: tabsBar.getBoundingClientRect().height,
  })
}

function activeProject() {
  return config.projects.find((p) => p.id === activeProjectId) || config.projects[0]
}

function renderProjects() {
  projectsEl.innerHTML = ''
  for (const project of config.projects) {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'project-btn' + (project.id === activeProjectId ? ' active' : '')
    btn.textContent = project.name
    btn.addEventListener('click', () => selectProject(project.id))
    projectsEl.appendChild(btn)
  }
}

function renderTabs() {
  const project = activeProject()
  tabsEl.innerHTML = ''
  if (!project) return
  for (const tab of project.tabs || []) {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'tab-btn' + (tab.id === activeTabId ? ' active' : '')
    btn.textContent = tab.label
    btn.addEventListener('click', () => openTab(tab))
    tabsEl.appendChild(btn)
  }
}

function openTab(tab) {
  const project = activeProject()
  if (!project || !tab) return
  activeTabId = tab.id
  renderTabs()
  reportMetrics()
  window.monitorHub.openTab(project.id, tab.id, tab.url)
}

function selectProject(projectId) {
  activeProjectId = projectId
  const project = activeProject()
  renderProjects()
  const first = project?.tabs?.[0]
  if (first) openTab(first)
  else renderTabs()
}

function boot(data) {
  config = data || { projects: [] }
  if (!config.projects?.length) {
    projectsEl.textContent = 'Sem projectos em projects.json'
    return
  }
  activeProjectId = config.projects[0].id
  renderProjects()
  const first = config.projects[0].tabs?.[0]
  if (first) openTab(first)
  reportMetrics()
}

reloadBtn.addEventListener('click', () => window.monitorHub.reloadActive())
window.addEventListener('resize', reportMetrics)

window.monitorHub.onConfig(boot)
window.monitorHub.getConfig().then(boot)
