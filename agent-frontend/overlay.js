// agent-frontend/overlay.js
// AgentPanel（方案 A · 唯一可视化容器）：
//   驾驶舱模式下 canvas 已经隐藏，所有 db 生成的可视化都要落到这里。
//   Tab 化：摘要 / 报告 / 表格 / 联动日志。切换只改 display，内容不销毁。
//   头部按钮：⤢ 最大化 / ↗ 新窗 / 📌 钉住 / ─ 最小化到胶囊 / ✕ 关闭。
//   最小化 = 收成右下角 “AI 结果” 胶囊，点开恢复；不清空 Tab 内容。

let panelEl = null
let contentEl = null
let tabsEl = null
let titleEl = null
let capsuleEl = null
let visible = false
let pinned = false
let maximized = false
let minimized = false
let currentTab = 'summary'
const sections = {}
const lastReportHtmlByTab = { report: '' }

const COLORS = {
  primary: '#26c6da',
  primarySoft: 'rgba(38, 198, 218, 0.2)',
  primaryBorder: 'rgba(38, 198, 218, 0.35)',
  aiAccent: '#00d4aa',
  panelBg: 'rgba(8, 20, 40, 0.94)',
  textMain: '#e0e0e0',
  textDim: '#b0c4de',
  textWeak: '#6a7d94',
  warn: '#ffb01e',
  danger: '#f74851',
}

const TABS = [
  { id: 'summary', label: '摘要' },
  { id: 'report',  label: '报告' },
  { id: 'table',   label: '表格' },
  { id: 'log',     label: '联动日志' },
]

// options.mode = 'tab-summary' | 'tab-report' | 'tab-table' | 'tab-log'
function modeToTab(mode) {
  if (typeof mode !== 'string') return null
  if (mode.startsWith('tab-')) {
    const id = mode.slice(4)
    return TABS.some(t => t.id === id) ? id : null
  }
  return null
}

function panelDims() {
  const cockpitOpen = document.body.classList.contains('db-cockpit-open')
  const cockpitW = cockpitOpen ? 'var(--db-cockpit-w, 380px)' : '0px'
  return {
    right: `calc(${cockpitW} + 20px)`,
    width: `min(920px, calc(100vw - ${cockpitW} - 60px))`,
    maxWidth: `calc(100vw - ${cockpitW} - 40px)`,
  }
}

function applyPanelPlacement() {
  if (!panelEl) return
  if (pinned) {
    Object.assign(panelEl.style, {
      position: 'absolute',
      top: '52px',
      left: '8px',
      right: 'auto',
      width: 'calc(100% - 16px)',
      maxWidth: 'none',
      height: '55%',
      maxHeight: '55%',
    })
    const cockpit = document.getElementById('db-cockpit')
    if (cockpit && panelEl.parentElement !== cockpit) cockpit.appendChild(panelEl)
    return
  }
  if (panelEl.parentElement !== document.body) document.body.appendChild(panelEl)
  if (maximized) {
    const cockpitOpen = document.body.classList.contains('db-cockpit-open')
    const cockpitW = cockpitOpen ? 'var(--db-cockpit-w, 380px)' : '0px'
    Object.assign(panelEl.style, {
      position: 'fixed',
      top: '20px',
      left: '20px',
      right: `calc(${cockpitW} + 20px)`,
      width: 'auto',
      maxWidth: 'none',
      height: 'calc(100vh - 40px)',
      maxHeight: 'calc(100vh - 40px)',
    })
    return
  }
  const dims = panelDims()
  Object.assign(panelEl.style, {
    position: 'fixed',
    top: '80px',
    left: 'auto',
    right: dims.right,
    width: dims.width,
    maxWidth: dims.maxWidth,
    height: 'min(85vh, calc(100vh - 120px))',
    maxHeight: 'calc(100vh - 120px)',
  })
}

export function initOverlay() {
  if (panelEl) return

  panelEl = document.createElement('div')
  panelEl.id = 'agent-panel'
  Object.assign(panelEl.style, {
    background: COLORS.panelBg,
    border: `1px solid ${COLORS.primaryBorder}`,
    borderLeft: `3px solid ${COLORS.aiAccent}`,
    borderRadius: '10px',
    boxShadow: '0 12px 40px rgba(0, 0, 0, 0.55)',
    zIndex: '90000',
    display: 'none',
    flexDirection: 'column',
    backdropFilter: 'blur(12px)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    color: COLORS.textMain,
    transition: 'opacity 260ms ease',
    opacity: '0',
  })

  const header = document.createElement('div')
  Object.assign(header.style, {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 12px',
    borderBottom: `1px solid ${COLORS.primaryBorder}`,
    cursor: 'move',
    userSelect: 'none',
    position: 'relative',
    zIndex: '2',
    flexShrink: '0',
    background: COLORS.panelBg,
    gap: '10px',
  })
  header.innerHTML = `
    <div style="display:flex;align-items:center;gap:10px;min-width:0;">
      <div style="width:8px;height:8px;border-radius:50%;background:${COLORS.aiAccent};box-shadow:0 0 8px ${COLORS.aiAccent};flex-shrink:0"></div>
      <span id="agent-panel-title" style="font-size:13px;font-weight:600;color:${COLORS.primary};letter-spacing:0.04em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">db · 智能体输出</span>
      <span style="font-size:10px;padding:1px 6px;border:1px solid ${COLORS.aiAccent};color:${COLORS.aiAccent};border-radius:3px;letter-spacing:0.1em;flex-shrink:0;">AI</span>
    </div>
    <div style="display:flex;gap:2px;flex-shrink:0">
      <button data-act="new-window" title="在新窗口打开当前报告"
              style="background:none;border:none;color:${COLORS.textDim};cursor:pointer;font-size:14px;padding:4px 8px;border-radius:4px;">↗</button>
      <button data-act="max" title="最大化 / 还原"
              style="background:none;border:none;color:${COLORS.textDim};cursor:pointer;font-size:14px;padding:4px 8px;border-radius:4px;">⤢</button>
      <button data-act="pin" title="钉到驾驶舱内"
              style="background:none;border:none;color:${COLORS.textDim};cursor:pointer;font-size:14px;padding:4px 8px;border-radius:4px;">📌</button>
      <button data-act="min" title="最小化到胶囊"
              style="background:none;border:none;color:${COLORS.textDim};cursor:pointer;font-size:14px;padding:4px 8px;border-radius:4px;">─</button>
      <button data-act="close" title="关闭（清空内容）"
              style="background:none;border:none;color:${COLORS.textDim};cursor:pointer;font-size:14px;padding:4px 8px;border-radius:4px;">✕</button>
    </div>
  `

  tabsEl = document.createElement('div')
  Object.assign(tabsEl.style, {
    display: 'flex',
    gap: '2px',
    padding: '4px 8px 0 8px',
    background: COLORS.panelBg,
    borderBottom: `1px solid ${COLORS.primaryBorder}`,
    flexShrink: '0',
  })
  for (const t of TABS) {
    const btn = document.createElement('button')
    btn.dataset.tab = t.id
    btn.textContent = t.label
    btn.style.cssText = `
      background:transparent;border:none;padding:6px 12px;font-size:12px;
      color:${COLORS.textDim};cursor:pointer;border-bottom:2px solid transparent;
      border-radius:4px 4px 0 0;transition:all 200ms ease;
    `
    btn.addEventListener('click', () => switchTab(t.id))
    tabsEl.appendChild(btn)
  }

  contentEl = document.createElement('div')
  contentEl.id = 'agent-panel-content'
  Object.assign(contentEl.style, {
    padding: '0',
    overflow: 'hidden',
    flex: '1',
    fontSize: '13px',
    lineHeight: '1.7',
    position: 'relative',
  })
  for (const t of TABS) {
    const sec = document.createElement('section')
    sec.dataset.tab = t.id
    Object.assign(sec.style, {
      position: 'absolute',
      inset: '0',
      overflow: 'auto',
      padding: t.id === 'report' ? '0' : '14px',
      display: t.id === currentTab ? 'block' : 'none',
    })
    sec.innerHTML = `<div style="color:${COLORS.textWeak};font-size:12px;padding:12px;text-align:center">尚无内容</div>`
    contentEl.appendChild(sec)
    sections[t.id] = sec
  }

  panelEl.appendChild(header)
  panelEl.appendChild(tabsEl)
  panelEl.appendChild(contentEl)
  document.body.appendChild(panelEl)

  titleEl = header.querySelector('#agent-panel-title')

  header.querySelector('[data-act="close"]').addEventListener('click', hideAgentPanel)
  header.querySelector('[data-act="min"]').addEventListener('click', minimizeToCapsule)
  header.querySelector('[data-act="max"]').addEventListener('click', toggleMaximize)
  header.querySelector('[data-act="pin"]').addEventListener('click', togglePin)
  header.querySelector('[data-act="new-window"]').addEventListener('click', openLastReportInNewWindow)

  makeDraggable(header, panelEl)
  paintTabs()
  applyPanelPlacement()

  console.log('[agent-panel] initialized (tabbed)')
}

function paintTabs() {
  if (!tabsEl) return
  for (const btn of tabsEl.querySelectorAll('button')) {
    const active = btn.dataset.tab === currentTab
    btn.style.color = active ? COLORS.aiAccent : COLORS.textDim
    btn.style.borderBottomColor = active ? COLORS.aiAccent : 'transparent'
    btn.style.background = active ? 'rgba(0, 212, 170, 0.08)' : 'transparent'
    btn.style.fontWeight = active ? '600' : '400'
  }
}

function switchTab(id) {
  if (!sections[id]) return
  currentTab = id
  for (const key of Object.keys(sections)) {
    sections[key].style.display = key === id ? 'block' : 'none'
  }
  paintTabs()
}

export function showAgentPanel(panelType, data, options = {}) {
  if (!panelEl) initOverlay()
  if (minimized) restoreFromCapsule({ show: false })
  panelEl.style.display = 'flex'
  visible = true
  applyPanelPlacement()
  requestAnimationFrame(() => { panelEl.style.opacity = '1' })

  if (options.title) titleEl.textContent = options.title
  else titleEl.textContent = 'db · 智能体输出'

  // 决定目标 Tab（优先 options.mode，其次按 panelType 猜）
  let target = modeToTab(options.mode)
  if (!target) {
    if (panelType === 'html') target = 'report'
    else if (panelType === 'table') target = 'table'
    else if (panelType === 'log') target = 'log'
    else target = 'summary'
  }

  const sec = sections[target]
  if (!sec) return

  switch (panelType) {
    case 'text':
      renderText(sec, data)
      break
    case 'table':
      renderTable(sec, data)
      break
    case 'chart':
      renderChart(sec, data)
      break
    case 'html':
      renderHtml(sec, data)
      lastReportHtmlByTab[target] = (data && data.html) || ''
      break
    case 'log':
      appendLog(sec, data)
      break
    default:
      sec.innerHTML = `<pre style="white-space:pre-wrap;color:${COLORS.textDim};padding:12px;">${escapeHtml(JSON.stringify(data, null, 2))}</pre>`
  }

  switchTab(target)
}

export function hideAgentPanel() {
  if (!panelEl) return
  panelEl.style.opacity = '0'
  setTimeout(() => {
    if (panelEl) panelEl.style.display = 'none'
    // 清空各 Tab，避免下次打开是脏数据（最小化才是保留内容）
    for (const key of Object.keys(sections)) {
      sections[key].innerHTML = `<div style="color:${COLORS.textWeak};font-size:12px;padding:12px;text-align:center">尚无内容</div>`
      lastReportHtmlByTab[key] = ''
    }
  }, 240)
  visible = false
  maximized = false
}

// ------------------------------ 最小化到胶囊 ------------------------------

function ensureCapsule() {
  if (capsuleEl) return capsuleEl
  capsuleEl = document.createElement('div')
  capsuleEl.id = 'agent-panel-capsule'
  Object.assign(capsuleEl.style, {
    position: 'fixed',
    right: 'calc(var(--db-cockpit-w, 0px) + 20px)',
    bottom: '20px',
    background: COLORS.panelBg,
    border: `1px solid ${COLORS.primaryBorder}`,
    borderLeft: `3px solid ${COLORS.aiAccent}`,
    borderRadius: '999px',
    padding: '8px 14px',
    color: COLORS.aiAccent,
    fontSize: '12px',
    fontWeight: '600',
    cursor: 'pointer',
    zIndex: '90001',
    display: 'none',
    alignItems: 'center',
    gap: '6px',
    boxShadow: '0 6px 20px rgba(0,0,0,0.35)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  })
  capsuleEl.innerHTML = '<span style="width:8px;height:8px;border-radius:50%;background:' + COLORS.aiAccent + ';box-shadow:0 0 6px ' + COLORS.aiAccent + '"></span><span>AI 结果</span>'
  capsuleEl.addEventListener('click', () => restoreFromCapsule({ show: true }))
  document.body.appendChild(capsuleEl)
  return capsuleEl
}

function minimizeToCapsule() {
  ensureCapsule()
  minimized = true
  if (panelEl) panelEl.style.display = 'none'
  capsuleEl.style.display = 'inline-flex'
}

function restoreFromCapsule({ show = true } = {}) {
  minimized = false
  if (capsuleEl) capsuleEl.style.display = 'none'
  if (panelEl && show) {
    panelEl.style.display = 'flex'
    applyPanelPlacement()
    requestAnimationFrame(() => { panelEl.style.opacity = '1' })
  }
}

// ------------------------------ 最大化 / 钉住 / 新窗 ------------------------------

function toggleMaximize() {
  maximized = !maximized
  if (maximized && pinned) pinned = false
  applyPanelPlacement()
}

function togglePin() {
  pinned = !pinned
  if (pinned && maximized) maximized = false
  if (pinned && !document.getElementById('db-cockpit')) {
    console.warn('[agent-panel] no cockpit to pin to')
    pinned = false
  }
  applyPanelPlacement()
}

function openLastReportInNewWindow() {
  const html = lastReportHtmlByTab.report
  if (!html) {
    alert('当前没有可导出的报告（请先让 db 生成一份报告）')
    return
  }
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const w = window.open(url, '_blank', 'width=1200,height=860')
  if (!w) alert('浏览器拦截了弹窗，请手动允许弹窗后再试。')
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}

// ------------------------------ 渲染器 ------------------------------

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderText(sec, data) {
  const { title, content, stats } = data || {}
  let html = ''
  if (title) {
    html += `<div style="font-size:15px;font-weight:600;color:${COLORS.primary};margin-bottom:12px;">${escapeHtml(title)}</div>`
  }
  if (Array.isArray(stats) && stats.length) {
    html += '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;">'
    for (const s of stats) {
      html += `
        <div style="background:${COLORS.primarySoft};border:1px solid ${COLORS.primaryBorder};border-radius:8px;padding:8px 12px;min-width:80px;text-align:center;flex:1;">
          <div style="font-size:11px;color:${COLORS.textWeak};margin-bottom:4px;">${escapeHtml(s.label)}</div>
          <div style="font-size:18px;font-weight:700;color:${escapeHtml(s.color || COLORS.primary)};">${escapeHtml(s.value)}</div>
        </div>
      `
    }
    html += '</div>'
  }
  if (content) {
    html += `<div style="color:${COLORS.textDim};white-space:pre-wrap;">${escapeHtml(content)}</div>`
  }
  if (!html) html = `<div style="color:${COLORS.textWeak};font-size:12px;padding:12px;text-align:center">尚无内容</div>`
  sec.innerHTML = html
}

function renderTable(sec, data) {
  const { title, columns = [], rows = [] } = data || {}
  let html = ''
  if (title) {
    html += `<div style="font-size:15px;font-weight:600;color:${COLORS.primary};margin-bottom:12px;">${escapeHtml(title)}</div>`
  }
  html += '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:12px;">'
  html += '<thead><tr>'
  for (const col of columns) {
    html += `<th style="padding:8px 10px;text-align:left;border-bottom:2px solid ${COLORS.primaryBorder};color:${COLORS.primary};font-weight:600;">${escapeHtml(col)}</th>`
  }
  html += '</tr></thead><tbody>'
  for (const row of rows) {
    html += '<tr>'
    for (const cell of row) {
      html += `<td style="padding:6px 10px;border-bottom:1px solid rgba(255,255,255,0.06);color:${COLORS.textMain};">${escapeHtml(cell != null ? cell : '-')}</td>`
    }
    html += '</tr>'
  }
  html += '</tbody></table></div>'
  sec.innerHTML = html
}

function renderChart(sec, data) {
  const { title } = data || {}
  let html = ''
  if (title) {
    html += `<div style="font-size:15px;font-weight:600;color:${COLORS.primary};margin-bottom:12px;">${escapeHtml(title)}</div>`
  }
  const chartId = 'agent-chart-' + Date.now()
  html += `<div id="${chartId}" style="width:100%;height:320px;"></div>`
  sec.innerHTML = html
  setTimeout(() => {
    const el = document.getElementById(chartId)
    if (el && window.echarts) {
      const chart = window.echarts.init(el, 'dark')
      chart.setOption((data && (data.option || data.chartOption)) || {})
      chart.resize()
    } else if (el) {
      el.innerHTML = `<div style="color:${COLORS.textWeak};text-align:center;padding-top:120px;">ECharts 未加载，无法渲染图表</div>`
    }
  }, 60)
}

function renderHtml(sec, data) {
  const html = (data && data.html) || ''
  // 报告 Tab 铺满，无内边距
  sec.style.padding = '0'
  sec.innerHTML = html || `<div style="color:${COLORS.textWeak};font-size:12px;padding:12px;text-align:center">尚无报告</div>`
}

function appendLog(sec, data) {
  // 首次追加时把占位 "尚无内容" 清掉
  if (sec.querySelector('.db-log-empty') || !sec.querySelector('.db-log-list')) {
    sec.innerHTML = '<div class="db-log-list" style="display:flex;flex-direction:column;gap:4px;font-family:monospace;font-size:12px"></div>'
  }
  const list = sec.querySelector('.db-log-list')
  const ts = data && data.ts ? new Date(data.ts) : new Date()
  const timeStr = String(ts.getHours()).padStart(2, '0') + ':' + String(ts.getMinutes()).padStart(2, '0') + ':' + String(ts.getSeconds()).padStart(2, '0')
  const kind = (data && data.kind) || 'info'
  const icon = kind === 'warn' ? '⚠' : kind === 'error' ? '✗' : kind === 'ok' ? '✓' : '·'
  const color = kind === 'warn' ? COLORS.warn : kind === 'error' ? COLORS.danger : kind === 'ok' ? COLORS.aiAccent : COLORS.textDim
  const row = document.createElement('div')
  row.style.cssText = `display:flex;gap:8px;color:${color};padding:4px 8px;border-left:2px solid ${color};background:rgba(0,0,0,0.15);border-radius:0 4px 4px 0;`
  row.innerHTML = `<span style="color:${COLORS.textWeak}">[${timeStr}]</span><span style="width:14px;text-align:center">${icon}</span><span style="flex:1;word-break:break-all">${escapeHtml((data && data.text) || '')}</span>`
  list.appendChild(row)
  // 只保留最近 120 条
  while (list.children.length > 120) list.removeChild(list.firstChild)
  list.scrollTop = list.scrollHeight
}

// ------------------------------ 拖拽 ------------------------------

function makeDraggable(handle, el) {
  let dragging = false
  let sx = 0, sy = 0, sl = 0, st = 0
  let iframesToRestore = []

  const start = (e) => {
    if (e.target.tagName === 'BUTTON') return
    if (pinned || maximized) return
    dragging = true
    const rect = el.getBoundingClientRect()
    sx = e.clientX
    sy = e.clientY
    sl = rect.left
    st = rect.top
    el.style.transition = 'none'
    iframesToRestore = Array.from(document.querySelectorAll('iframe'))
    iframesToRestore.forEach(f => { f.style.pointerEvents = 'none' })
    e.preventDefault()
  }

  const move = (e) => {
    if (!dragging) return
    const nx = Math.max(0, Math.min(window.innerWidth - 60, sl + (e.clientX - sx)))
    const ny = Math.max(0, Math.min(window.innerHeight - 40, st + (e.clientY - sy)))
    el.style.left = nx + 'px'
    el.style.top = ny + 'px'
    el.style.right = 'auto'
  }

  const endDrag = () => {
    if (!dragging) return
    dragging = false
    el.style.transition = ''
    iframesToRestore.forEach(f => { f.style.pointerEvents = '' })
    iframesToRestore = []
  }

  handle.addEventListener('mousedown', start)
  document.addEventListener('mousemove', move)
  document.addEventListener('mouseup', endDrag)
  window.addEventListener('blur', endDrag)
}
