// agent-frontend/cockpit.js
// 驾驶舱 UI：顶部状态条 + 右侧驾驶舱栏（内嵌 db iframe）+ 右下浮球
// 与 controller.js / overlay.js / bridge.js 协作。

const DB_ORIGIN = (() => {
  // 允许通过 window.__dbOrigin 覆盖（例如生产部署时改端口）
  if (window.__dbOrigin) return window.__dbOrigin
  // 与 start.bat 打开的独立控制台统一 origin（127.0.0.1），共享 IndexedDB 与 localStorage
  return 'http://127.0.0.1:8000'
})()
// 加时间戳绕开跨源 iframe 缓存；每次驾驶舱挂载都是全新的 db 会话
const DB_IFRAME_URL = DB_ORIGIN + '/src/?mode=cockpit&t=' + Date.now()

let cockpitEl = null
let bubbleEl = null
let demoBadgeEl = null
let iframeEl = null
let dataMode = 'auto'
let currentSize = 'standard' // 'mini' | 'standard' | 'wide'
const SIZE_MAP = { mini: '220px', standard: '380px', wide: '520px' }

// -------------------------------------------------------------- 装载 --

export function mountCockpit() {
  document.body.classList.add('db-cockpit-active')

  mountCockpitPanel()
  mountBubble()
  mountDemoBadge()

  // 默认折叠为浮球，不主动占地方——用户点浮球再展开
  closeCockpit()

  // 拉一次配置显示 live/demo
  fetch('/agent-config').catch(() => null).then(async (r) => {
    try {
      const cfg = await (r && r.ok ? r.json() : fetchDbConfig())
      if (cfg && cfg.mode) setDataMode(cfg.mode)
    } catch (_) {
      const cfg = await fetchDbConfig().catch(() => null)
      if (cfg && cfg.mode) setDataMode(cfg.mode)
    }
  })

  console.log('[cockpit] mounted (topbar-less mode)')
}

async function fetchDbConfig() {
  try {
    const r = await fetch(DB_ORIGIN + '/api/weather-adapter/config')
    if (!r.ok) return null
    return await r.json()
  } catch {
    return null
  }
}

function mountCockpitPanel() {
  cockpitEl = document.createElement('div')
  cockpitEl.id = 'db-cockpit'
  cockpitEl.dataset.status = 'idle'
  cockpitEl.innerHTML = `
    <div class="db-cockpit-header">
      <div class="db-cockpit-brand">
        <div class="db-status-dot"></div>
        <span>db 智能体</span>
        <span class="db-mode-badge" data-mode="auto">…</span>
      </div>
      <div class="db-cockpit-actions">
        <div class="db-workspace" title="工作区授权（跨源 iframe 里必须由顶层窗口打开）">
          <button class="db-workspace-btn" data-act="ws-toggle" type="button">📎 工作区 ▾</button>
          <div class="db-workspace-menu" hidden>
            <div class="db-ws-section" data-role="saved-list">
              <div class="db-ws-empty">尚未授权任何工作区</div>
            </div>
            <div class="db-ws-divider"></div>
            <button class="db-ws-item" data-act="ws-add-file" type="button">📄 新增授权文件</button>
            <button class="db-ws-item" data-act="ws-add-dir" type="button">📁 新增授权文件夹</button>
          </div>
        </div>
        <div class="db-size-toggle" title="驾驶舱宽度">
          <span data-size="mini" title="精简 220px">S</span>
          <span data-size="standard" class="active" title="标准 380px">M</span>
          <span data-size="wide" title="宽屏 520px">L</span>
        </div>
        <button class="db-close-btn" data-act="close" title="折叠到浮球">✕</button>
      </div>
    </div>
  `

  iframeEl = document.createElement('iframe')
  iframeEl.className = 'db-iframe'
  iframeEl.src = DB_IFRAME_URL
  iframeEl.setAttribute('allow', 'clipboard-read; clipboard-write; microphone; camera')
  iframeEl.setAttribute('title', 'db 智能体控制台')
  cockpitEl.appendChild(iframeEl)

  cockpitEl.querySelector('[data-act="close"]').addEventListener('click', closeCockpit)
  cockpitEl.querySelectorAll('.db-size-toggle span').forEach((s) => {
    s.addEventListener('click', () => setSize(s.dataset.size))
  })

  wireWorkspaceMenu(cockpitEl)

  document.body.appendChild(cockpitEl)
}

// -------------------------------------------------------------- 工作区授权 --
// 跨源 iframe 里禁用 File System Access API，必须由顶层 luwang 调 picker。
// 拿到 handle 后通过 postMessage 传给 db iframe，iframe 写自己的 IndexedDB。

let wsReqSeq = 0
const wsPending = new Map()

function nextWsId() {
  wsReqSeq += 1
  return 'ws-' + Date.now() + '-' + wsReqSeq
}

function postToDb(msg) {
  if (!iframeEl || !iframeEl.contentWindow) return false
  try {
    iframeEl.contentWindow.postMessage(msg, DB_ORIGIN)
    return true
  } catch (e) {
    console.warn('[cockpit] postToDb failed:', e)
    return false
  }
}

function requestDb(type, payload = {}, { timeout = 8000 } = {}) {
  return new Promise((resolve, reject) => {
    const id = nextWsId()
    const timer = setTimeout(() => {
      wsPending.delete(id)
      reject(new Error('db 响应超时: ' + type))
    }, timeout)
    wsPending.set(id, { resolve, reject, timer })
    if (!postToDb({ src: 'cockpit', type, id, ...payload })) {
      clearTimeout(timer)
      wsPending.delete(id)
      reject(new Error('iframe 未就绪'))
    }
  })
}

// 监听来自 iframe 的 ack / list 回执
window.addEventListener('message', (e) => {
  if (e.origin !== DB_ORIGIN && e.origin !== 'http://localhost:8000' && e.origin !== 'http://127.0.0.1:8000') return
  const msg = e.data
  if (!msg || msg.src !== 'db') return
  if (msg.type === 'fs-ack' || msg.type === 'fs-list-result') {
    const p = wsPending.get(msg.id)
    if (!p) return
    clearTimeout(p.timer)
    wsPending.delete(msg.id)
    if (msg.ok) p.resolve(msg.data)
    else p.reject(new Error(msg.error || 'ack failed'))
  }
})

function wireWorkspaceMenu(root) {
  const wsWrap = root.querySelector('.db-workspace')
  const toggleBtn = root.querySelector('[data-act="ws-toggle"]')
  const menu = root.querySelector('.db-workspace-menu')
  const addFileBtn = root.querySelector('[data-act="ws-add-file"]')
  const addDirBtn = root.querySelector('[data-act="ws-add-dir"]')

  const closeMenu = () => { menu.hidden = true; toggleBtn.classList.remove('open') }
  const openMenu = () => {
    menu.hidden = false
    toggleBtn.classList.add('open')
    refreshWorkspaceList(root).catch((e) => console.warn('[cockpit] list ws failed:', e))
  }

  toggleBtn.addEventListener('click', (e) => {
    e.stopPropagation()
    if (menu.hidden) openMenu(); else closeMenu()
  })
  document.addEventListener('click', (e) => {
    if (!wsWrap.contains(e.target)) closeMenu()
  })

  addFileBtn.addEventListener('click', async () => {
    closeMenu()
    if (!window.showOpenFilePicker) {
      toast('当前浏览器不支持文件授权 API（需 Chrome/Edge 90+）', 4000)
      return
    }
    try {
      const [handle] = await window.showOpenFilePicker()
      await sendHandleToDb(handle)
    } catch (err) {
      if (err && err.name !== 'AbortError') toast('文件授权失败：' + err.message, 4000)
    }
  })

  addDirBtn.addEventListener('click', async () => {
    closeMenu()
    if (!window.showDirectoryPicker) {
      toast('当前浏览器不支持文件夹授权 API（需 Chrome/Edge 90+）', 4000)
      return
    }
    try {
      const handle = await window.showDirectoryPicker({ mode: 'readwrite' })
      await sendHandleToDb(handle)
    } catch (err) {
      if (err && err.name !== 'AbortError') toast('文件夹授权失败：' + err.message, 4000)
    }
  })
}

async function sendHandleToDb(handle) {
  try {
    await requestDb('fs-handle', { handle, kind: handle.kind, name: handle.name }, { timeout: 6000 })
    toast('已授权 ' + handle.name + ' 到 db', 2500)
  } catch (err) {
    toast('转发授权失败：' + err.message, 4000)
  }
}

async function refreshWorkspaceList(root) {
  const list = root.querySelector('[data-role="saved-list"]')
  list.innerHTML = '<div class="db-ws-loading">读取中...</div>'
  let items = []
  try {
    items = await requestDb('fs-list', {}, { timeout: 4000 })
  } catch (e) {
    list.innerHTML = '<div class="db-ws-empty">读取失败：' + (e.message || 'unknown') + '</div>'
    return
  }
  if (!items || !items.length) {
    list.innerHTML = '<div class="db-ws-empty">尚未授权任何工作区</div>'
    return
  }
  list.innerHTML = ''
  const title = document.createElement('div')
  title.className = 'db-ws-title'
  title.textContent = '已保存的工作区'
  list.appendChild(title)
  for (const item of items) {
    const row = document.createElement('div')
    row.className = 'db-ws-row'
    const active = item.permission === 'granted'
    row.innerHTML = `
      <span class="db-ws-name" title="${escapeAttr(item.name)}">
        <span class="db-ws-dot ${active ? 'active' : 'lost'}"></span>
        ${item.kind === 'directory' ? '📁' : '📄'} ${escapeHtml(item.name)}
      </span>
      <span class="db-ws-actions">
        ${!active ? '<button data-role="wake" type="button">唤醒</button>' : ''}
        <button data-role="remove" type="button" title="移除">✕</button>
      </span>
    `
    const wakeBtn = row.querySelector('[data-role="wake"]')
    if (wakeBtn) {
      wakeBtn.addEventListener('click', async (e) => {
        e.stopPropagation()
        try {
          await requestDb('fs-wake', { handleId: item.id }, { timeout: 15000 })
          toast('已唤醒 ' + item.name, 2000)
          refreshWorkspaceList(root)
        } catch (err) {
          toast('唤醒失败：' + err.message, 3000)
        }
      })
    }
    const rmBtn = row.querySelector('[data-role="remove"]')
    rmBtn.addEventListener('click', async (e) => {
      e.stopPropagation()
      try {
        await requestDb('fs-remove', { handleId: item.id }, { timeout: 4000 })
        toast('已移除 ' + item.name, 2000)
        refreshWorkspaceList(root)
      } catch (err) {
        toast('移除失败：' + err.message, 3000)
      }
    })
    list.appendChild(row)
  }
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, '&quot;')
}

function mountBubble() {
  bubbleEl = document.createElement('div')
  bubbleEl.id = 'db-bubble'
  bubbleEl.title = '呼出 db 驾驶舱'
  bubbleEl.textContent = 'db'
  bubbleEl.addEventListener('click', openCockpit)
  document.body.appendChild(bubbleEl)
}

function mountDemoBadge() {
  demoBadgeEl = document.createElement('div')
  demoBadgeEl.id = 'db-demo-badge'
  demoBadgeEl.title = '当前使用样例数据。生产部署请设 WEATHER_MODE=live 并配置 LUWANG_TOKEN。'
  demoBadgeEl.textContent = '🟡 演示数据 (WEATHER_MODE=demo)'
  document.body.appendChild(demoBadgeEl)
}

// -------------------------------------------------------------- 状态 API --

export function setDbStatus(status = 'idle', text = '', task = '') {
  if (!cockpitEl) return
  cockpitEl.dataset.status = status
  if (bubbleEl) bubbleEl.dataset.status = status
}

export function setDataMode(mode) {
  dataMode = mode
  if (cockpitEl) {
    const badge = cockpitEl.querySelector('.db-mode-badge')
    if (badge) {
      const labels = { demo: '演示', live: '实时', auto: '自动' }
      badge.dataset.mode = mode
      badge.textContent = labels[mode] || mode
    }
  }
  if (demoBadgeEl) demoBadgeEl.classList.toggle('visible', mode === 'demo')
}

// 驾驶舱宽度三档：mini / standard / wide
export function setSize(size) {
  if (!SIZE_MAP[size]) return
  currentSize = size
  document.body.classList.remove('db-cockpit-mini', 'db-cockpit-standard', 'db-cockpit-wide')
  document.body.classList.add('db-cockpit-' + size)
  if (cockpitEl) {
    cockpitEl.style.width = SIZE_MAP[size]
    cockpitEl.querySelectorAll('.db-size-toggle span').forEach((s) => {
      s.classList.toggle('active', s.dataset.size === size)
    })
  }
  if (iframeEl && iframeEl.contentWindow) {
    iframeEl.contentWindow.postMessage({ src: 'cockpit', type: 'ui-size', size }, DB_ORIGIN)
  }
}

// -------------------------------------------------------------- 折叠 / 展开 --

export function openCockpit() {
  if (!cockpitEl) return
  cockpitEl.classList.add('open')
  document.body.classList.add('db-cockpit-open')
}

export function closeCockpit() {
  if (!cockpitEl) return
  cockpitEl.classList.remove('open')
  document.body.classList.remove('db-cockpit-open')
}

export function toggleCockpit() {
  if (!cockpitEl) return
  if (cockpitEl.classList.contains('open')) closeCockpit()
  else openCockpit()
}

// -------------------------------------------------------------- 吐司 --

export function toast(text, ms = 3000) {
  const t = document.createElement('div')
  t.className = 'db-toast'
  t.textContent = '[db] ' + text
  document.body.appendChild(t)
  setTimeout(() => {
    t.style.opacity = '0'
    setTimeout(() => t.remove(), 520)
  }, ms)
}

// -------------------------------------------------------------- iframe 引用 --

export function getDbIframe() {
  return iframeEl
}

export function getDbOrigin() {
  return DB_ORIGIN
}
