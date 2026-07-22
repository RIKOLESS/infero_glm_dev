// agent-frontend/inject.js
// 驾驶舱入口：Vite 插件把本文件注入 luwang 的 index.html。
// 等 Vue app 挂载 → 加载 controller / overlay / cockpit / bridge，
// 挂上驾驶舱 UI 和 AgentPanel。

import './styles.css'
import controller from './controller.js'
import { initOverlay } from './overlay.js'
import { mountCockpit, toast } from './cockpit.js'
import { initBridge } from './bridge.js'

console.log('[agent-inject] loaded')

// -------------------------------------------------------------- 等待 --

function waitFor(check, { interval = 100, timeout = 15000, label = '' } = {}) {
  return new Promise((resolve) => {
    const start = Date.now()
    const tick = () => {
      let ok = false
      try { ok = check() } catch { ok = false }
      if (ok) return resolve(true)
      if (Date.now() - start >= timeout) {
        console.warn(`[agent-inject] timeout waiting for ${label || 'condition'}`)
        return resolve(false)
      }
      setTimeout(tick, interval)
    }
    tick()
  })
}

// -------------------------------------------------------------- 主流程 --

async function init() {
  // 等 Vue app 挂载
  const vueReady = await waitFor(
    () => {
      const el = document.querySelector('#app')
      return el && el.__vue_app__
    },
    { label: 'Vue app mount' }
  )
  if (!vueReady) {
    console.warn('[agent-inject] Vue app not detected, still mounting UI (controller may be partial)')
  }

  // controller 已在 import 时挂 window.luwangController，这里只是保险
  if (!window.luwangController) {
    console.error('[agent-inject] controller missing')
    return
  }

  // 挂载 AgentPanel（藏着，等 db 呼出）
  initOverlay()

  // 挂载驾驶舱 UI（内含 db iframe）
  mountCockpit()

  // 启动 postMessage 桥
  initBridge()

  // 首屏提示
  setTimeout(() => toast('驾驶舱已就绪，右侧输入指令让 db 操作平台', 3200), 400)

  // 暴露一个调试入口
  window.__dbCockpit = {
    controller: window.luwangController,
    ping: () => window.luwangController.ping(),
  }
}

// 页面 ready 就跑
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init)
} else {
  init()
}
