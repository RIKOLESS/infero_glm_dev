// agent-frontend/controller.js
// 平台控制层：把 luwang 的 Pinia store / mitt emitter / Leaflet map / Vue router
// 封装成一组可 await 的函数，暴露在 window.luwangController。
//
// db 侧只用一句：
//   await window.luwangController.toggleLayer('emergencyPoints', true)
// 也支持组合：
//   await window.luwangController.batch([{...}, {...}], { interval: 300 })
//
// 来自同事 lovelittletree/luwang·controller.js 的抓取思路，改为同页函数调用。

import { showAgentPanel, hideAgentPanel } from './overlay.js'

// -------------------------------------------------------------- 联动日志广播 --
// 把 controller 触发的平台动作以事件形式推给 db iframe，再由 iframe 内的
// db-cockpit-bridge 转发到 dbCockpit.log()（AgentPanel“联动日志”Tab）。
function emitActionLog(text, kind = 'info') {
  try {
    // 1. 本地直接追加到 AgentPanel（不必走 iframe，UI 更即时）
    showAgentPanel('log', { text: '[luwang] ' + text, kind, ts: Date.now() }, { mode: 'tab-log' })
  } catch (e) { /* 面板未初始化时忽略 */ }
  try {
    // 2. 同步通知 db 侧（用于 db 决策链条里也能感知）
    const iframe = document.querySelector('#db-cockpit .db-iframe')
    if (iframe && iframe.contentWindow) {
      iframe.contentWindow.postMessage({
        src: 'cockpit',
        type: 'event',
        event: 'luwang-action',
        data: { text, kind, ts: Date.now() },
      }, iframe.src ? new URL(iframe.src).origin : '*')
    }
  } catch (e) { /* 忽略跨域异常 */ }
}

// -------------------------------------------------------------- 内部辅助 --

function getVueApp() {
  const el = document.querySelector('#app')
  return el && el.__vue_app__ ? el.__vue_app__ : null
}

function getStore(name) {
  const app = getVueApp()
  if (!app) return null
  const pinia = app.config.globalProperties.$pinia
  if (!pinia) return null
  return pinia._s.get(name) || null
}

let _emitter = null
async function getEmitter() {
  if (_emitter) return _emitter
  try {
    const mod = await import('/src/utils/bus.js')
    _emitter = mod.emitter
    return _emitter
  } catch (e) {
    console.warn('[luwangController] emitter import failed:', e.message)
    return null
  }
}

function getMap() {
  const container = document.getElementById('map-leaflet-page-container')
  if (!container) return null

  // 1. 沿 DOM 向上找带 setupState.map 的 Vue 组件
  let el = container
  while (el) {
    const comp = el.__vueParentComponent
    let c = comp
    while (c) {
      if (c.setupState && c.setupState.map) {
        const ref = c.setupState.map
        const map = ref && ref.value !== undefined ? ref.value : ref
        if (map && typeof map.flyTo === 'function') return map
      }
      c = c && c.parent
    }
    el = el.parentElement
  }

  // 2. 从 Leaflet pane 反查
  const pane = container.querySelector('.leaflet-map-pane')
  if (pane) {
    for (const key in pane) {
      const val = pane[key]
      if (val && typeof val === 'object' && typeof val.flyTo === 'function') {
        return val
      }
    }
  }
  return null
}

function findNodeByName(tree, name) {
  if (!Array.isArray(tree)) return null
  const target = String(name || '')
    .replace(/省|市|自治区|特别行政区|壮族|回族|维吾尔|藏族|蒙古/g, '')
    .trim()
  for (const node of tree) {
    const nodeName = String(node.name || '')
      .replace(/省|市|自治区|特别行政区|壮族|回族|维吾尔|藏族|蒙古/g, '')
      .trim()
    if (nodeName === target || node.name === name) return node
    if (node.children && node.children.length) {
      const found = findNodeByName(node.children, name)
      if (found) return found
    }
  }
  return null
}

function collectNodesByLevel(nodes, level) {
  const result = []
  if (!Array.isArray(nodes)) return result
  for (const node of nodes) {
    if (Number(node.level) === level) {
      result.push({ code: node.code, level: node.level, name: node.name })
    }
    if (node.children && node.children.length) {
      result.push(...collectNodesByLevel(node.children, level))
    }
  }
  return result
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// -------------------------------------------------------------- 命令集 --

// 图层字段名映射：外部友好名 -> Pinia 内部字段
const LAYER_MAP = {
  emergencyPoints: 'isShowEmergencyPoints',
  countryMaterials: 'isShowCountryMaterials',
  dangerPoints: 'isShowDangerPoints',
  riskSegments: 'isShowRiskSegmentsPoints',
  image7Days: 'isShowImage7Days',
  alertLayer: 'isShowaAlertLayer',
}

async function toggleLayer(layer, on) {
  const store = getStore('bigScreenLayerManage')
  if (!store) throw new Error('bigScreenLayerManage store 未就绪（大屏可能还未加载）')
  const field = LAYER_MAP[layer]
  if (!field) throw new Error(`未知图层: ${layer}（可用: ${Object.keys(LAYER_MAP).join(', ')}）`)
  store[field] = !!on
  await triggerLayerBlink(layer)
  emitActionLog('图层 ' + layer + ' → ' + (on ? 'ON' : 'OFF'), on ? 'ok' : 'info')
  return { layer, on: !!on }
}

async function triggerLayerBlink(layer) {
  // 视觉反馈：给对应图层按钮加短暂高亮 CSS class
  const btn = document.querySelector(`[data-layer="${layer}"]`)
  if (!btn) return
  btn.classList.add('agent-layer-blink')
  setTimeout(() => btn.classList.remove('agent-layer-blink'), 800)
}

async function selectArea(province) {
  const emitter = await getEmitter()
  if (!emitter) throw new Error('emitter 未就绪')
  if (!province) {
    emitter.emit('resetAreaTree')
    return { province: null, reset: true }
  }
  const store = getStore('bigScreenLayerManage')
  if (!store || !store.provinceTree) throw new Error('provinceTree 尚未加载')
  const node = findNodeByName(store.provinceTree, province)
  if (!node) throw new Error(`未找到省份: ${province}`)
  const leafNodes = collectNodesByLevel([node], 3)
  const payload = { checkedNodes: leafNodes.length ? leafNodes : [node] }
  emitter.emit('changeAreaTree', payload)
  return { province, node: { code: node.code, name: node.name }, districts: payload.checkedNodes.length }
}

async function selectRoad(cqlStrObj) {
  const emitter = await getEmitter()
  if (!emitter) throw new Error('emitter 未就绪')
  emitter.emit('changeWaysTree', cqlStrObj)
  return { ok: true }
}

async function flyTo({ center, zoom, bounds, duration = 1.5 } = {}) {
  const map = getMap()
  if (!map) throw new Error('Leaflet map 未就绪')
  if (bounds) map.fitBounds(bounds, { duration })
  else if (center) map.flyTo(center, zoom || 8, { duration })
  else throw new Error('flyTo 需要 center 或 bounds')
  emitActionLog(bounds
    ? '飞到区域 [' + bounds.join(', ') + ']'
    : '飞到 (' + center.join(', ') + ') zoom=' + (zoom || 8))
  return { center, zoom, bounds }
}

async function playAnimation(options) {
  const emitter = await getEmitter()
  if (!emitter) throw new Error('emitter 未就绪')
  emitter.emit('play', options || {})
  return { ok: true }
}

async function stopAnimation() {
  const emitter = await getEmitter()
  if (!emitter) throw new Error('emitter 未就绪')
  emitter.emit('stop')
  return { ok: true }
}

// -------------------------------------------------------------- 地图标记 --
// 借鉴 lovelittletree/luwang · controller.js（drawMarkers/clearMarkers），
// 让 db 能把救援点/隐患点/震中直接标到 Leaflet 地图上。
let _agentMarkerLayer = null

async function drawMarkers({ markers = [], clear = true } = {}) {
  const map = getMap()
  if (!map) throw new Error('Leaflet map 未就绪')
  const L = window.L
  if (!L) throw new Error('window.L (Leaflet) 未加载')

  if (clear && _agentMarkerLayer) {
    map.removeLayer(_agentMarkerLayer)
    _agentMarkerLayer = null
  }
  if (typeof L.markerClusterGroup === 'function') {
    _agentMarkerLayer = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 40,
      iconCreateFunction: (cluster) => L.divIcon({
        html: `<div style="background:rgba(0,212,170,.9);color:#001;border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;box-shadow:0 0 12px rgba(0,212,170,.6)">${cluster.getChildCount()}</div>`,
        className: 'agent-cluster',
        iconSize: [30, 30],
      }),
    })
  } else {
    _agentMarkerLayer = L.layerGroup()
  }

  for (const m of markers) {
    if (m == null || m.lat == null || m.lng == null) continue
    const color = m.color || '#00d4aa'
    const icon = L.divIcon({
      html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 0 10px ${color};"></div>`,
      className: 'agent-marker',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    })
    const marker = L.marker([m.lat, m.lng], { icon })
    if (m.title || m.content) {
      const popupHtml = `<div style="font-size:12px;color:#123;min-width:140px;max-width:280px">
        ${m.title ? `<div style="font-weight:700;margin-bottom:4px;color:#064d75">${escapeHtml(m.title)}</div>` : ''}
        ${m.content ? `<div style="line-height:1.6">${escapeHtml(m.content)}</div>` : ''}
        ${m.distance != null ? `<div style="margin-top:6px;color:#00a67d;font-weight:600">距离：${Number(m.distance).toFixed(1)} km</div>` : ''}
      </div>`
      marker.bindPopup(popupHtml)
    }
    _agentMarkerLayer.addLayer(marker)
  }
  map.addLayer(_agentMarkerLayer)
  emitActionLog('地图标记 ' + markers.length + ' 个', 'ok')
  return { count: markers.length }
}

async function clearMarkers() {
  const map = getMap()
  if (!map || !_agentMarkerLayer) return { ok: true, cleared: 0 }
  map.removeLayer(_agentMarkerLayer)
  const n = _agentMarkerLayer.getLayers ? _agentMarkerLayer.getLayers().length : 0
  _agentMarkerLayer = null
  emitActionLog('清除地图标记 ' + n + ' 个')
  return { ok: true, cleared: n }
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

async function togglePanel({ panel, on } = {}) {
  const targets = panel === 'both' ? ['left', 'right'] : [panel || 'right']
  const results = []
  for (const name of targets) {
    const el = document.querySelector(`.${name}-wrapper`)
    if (!el) {
      results.push({ panel: name, ok: false, reason: 'element not found' })
      continue
    }
    const comp = el.__vueParentComponent
    if (comp && comp.setupState && 'isCollapse' in comp.setupState) {
      comp.setupState.isCollapse = on !== undefined ? !!on : !comp.setupState.isCollapse
      results.push({ panel: name, ok: true, isCollapse: comp.setupState.isCollapse })
    } else {
      const btn = el.querySelector(`.${name}-collapse-btn`)
      if (btn) {
        btn.click()
        results.push({ panel: name, ok: true, via: 'click' })
      } else {
        results.push({ panel: name, ok: false, reason: 'no collapse control' })
      }
    }
  }
  return results
}

async function navigate(pageOrPath) {
  const app = getVueApp()
  const router = app && app.config.globalProperties.$router
  if (router) {
    await router.push(pageOrPath)
    return { ok: true, via: 'router', to: pageOrPath }
  }
  window.location.href = pageOrPath
  return { ok: true, via: 'location', to: pageOrPath }
}

async function openBigScreen(type) {
  const routes = {
    shortTerm: '/bigScreenBox/shortTermForecast',
    analysisReport: '/bigScreenBox/analysisReport',
    threeMap: '/bigScreenBox/threeMap',
    rainfall: '/bigScreenBox/bigScreen',
    bigScreen: '/bigScreenBox/bigScreen',
  }
  const labelMap = {
    shortTerm: '短临预报大屏',
    analysisReport: '分析看板',
    threeMap: '3D 大屏',
    rainfall: '降雨大屏',
    bigScreen: '降雨大屏',
  }
  const target = routes[type] || type
  const label = labelMap[type] || target
  const app = getVueApp()
  const router = app && app.config.globalProperties.$router
  if (router) {
    const current = router.currentRoute && router.currentRoute.value && router.currentRoute.value.path
    if (current === target) {
      emitActionLog('已在 ' + label + '，跳过导航')
      return { ok: true, via: 'skip', to: target, alreadyOnPage: true }
    }
    await router.push(target)
    await sleep(1000)
    emitActionLog('打开 ' + label, 'ok')
    return { ok: true, via: 'router', to: target }
  }
  window.location.href = target
  emitActionLog('打开 ' + label + '（外部跳转）', 'ok')
  return { ok: true, via: 'location', to: target }
}

// AgentPanel 相关
function renderOverlay({ panelType = 'text', data = {}, options = {} } = {}) {
  showAgentPanel(panelType, data, options)
  return { ok: true }
}

function clearOverlay() {
  hideAgentPanel()
  return { ok: true }
}

// 组合命令
async function batch(commands = [], { interval = 300, stopOnError = false } = {}) {
  const results = []
  for (const cmd of commands) {
    try {
      const fn = window.luwangController[cmd.type]
      if (typeof fn !== 'function') throw new Error(`未知命令: ${cmd.type}`)
      const args = cmd.args !== undefined ? cmd.args : cmd.payload
      const result = Array.isArray(args) ? await fn(...args) : await fn(args)
      results.push({ type: cmd.type, ok: true, result })
    } catch (e) {
      results.push({ type: cmd.type, ok: false, error: e.message })
      if (stopOnError) break
    }
    if (interval > 0) await sleep(interval)
  }
  return results
}

// 探针：从 db iframe 探测 controller 是否就绪
function ping() {
  return {
    ready: true,
    layers: Object.keys(LAYER_MAP),
    hasStore: !!getStore('bigScreenLayerManage'),
    hasMap: !!getMap(),
    ts: Date.now(),
  }
}

// -------------------------------------------------------------- 导出 --

const controller = {
  toggleLayer,
  selectArea,
  selectRoad,
  flyTo,
  playAnimation,
  stopAnimation,
  togglePanel,
  navigate,
  openBigScreen,
  drawMarkers,
  clearMarkers,
  renderOverlay,
  clearOverlay,
  batch,
  ping,
}

// 挂载全局
window.luwangController = controller

export default controller
