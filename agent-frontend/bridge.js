// agent-frontend/bridge.js
// postMessage 桥：处理 db iframe ↔ luwang controller / AgentPanel 的双向通信。
//
// 协议（详见 README.md）：
//   db → parent:   { src: 'db', type: 'cmd', id, cmd: { type, ...args } }
//                  { src: 'db', type: 'state', state: { status, task } }
//                  { src: 'db', type: 'ping' }
//   parent → db:   { src: 'cockpit', type: 'cmd-result', id, ok, data, error }
//                  { src: 'cockpit', type: 'event', event, data }
//                  { src: 'cockpit', type: 'mode', mode }

import controller from './controller.js'
import { getDbOrigin, setDbStatus, toast } from './cockpit.js'

const DB_ORIGIN = getDbOrigin()
// 允许 localhost / 127.0.0.1 两种 origin 的 db 挂进来
const DB_ORIGINS = new Set([
  DB_ORIGIN,
  'http://localhost:8000',
  'http://127.0.0.1:8000',
])

export function initBridge() {
  window.addEventListener('message', async (e) => {
    // 仅接受来自 db iframe 的消息
    if (!DB_ORIGINS.has(e.origin)) return
    const msg = e.data
    if (!msg || msg.src !== 'db') return

    switch (msg.type) {
      case 'ping':
        replyToDb(e.source, {
          src: 'cockpit',
          type: 'pong',
          id: msg.id,
          data: { ready: true, controller: controller.ping() },
        })
        break

      case 'state':
        // db 汇报自身状态：thinking / executing / speaking / idle / error
        try {
          const { status, text, task } = msg.state || {}
          setDbStatus(status || 'idle', text || '', task || '')
        } catch (err) {
          console.warn('[bridge] state update failed:', err)
        }
        break

      case 'cmd': {
        const { id, cmd } = msg
        if (!cmd || !cmd.type) {
          replyToDb(e.source, { src: 'cockpit', type: 'cmd-result', id, ok: false, error: 'invalid cmd' })
          return
        }
        const fn = controller[cmd.type]
        if (typeof fn !== 'function') {
          replyToDb(e.source, { src: 'cockpit', type: 'cmd-result', id, ok: false, error: 'unknown cmd: ' + cmd.type })
          return
        }
        try {
          const args = cmd.args !== undefined ? cmd.args : cmd.payload
          const data = Array.isArray(args) ? await fn(...args) : await fn(args)
          replyToDb(e.source, { src: 'cockpit', type: 'cmd-result', id, ok: true, data })
        } catch (err) {
          console.error('[bridge] cmd failed:', cmd.type, err)
          toast('指令失败：' + cmd.type + ' — ' + err.message, 4000)
          replyToDb(e.source, { src: 'cockpit', type: 'cmd-result', id, ok: false, error: err.message })
        }
        break
      }

      default:
        // 忽略未知类型，不吵杂
        break
    }
  })

  console.log('[bridge] initialized, listening from', DB_ORIGIN)
}

function replyToDb(target, payload) {
  try {
    target.postMessage(payload, DB_ORIGIN)
  } catch (e) {
    console.warn('[bridge] reply failed:', e)
  }
}

// 反向推送：允许 luwang 端主动通知 db（例如平台数据刷新）
export function pushEventToDb(event, data) {
  const iframe = document.querySelector('#db-cockpit .db-iframe')
  if (!iframe || !iframe.contentWindow) return
  iframe.contentWindow.postMessage({ src: 'cockpit', type: 'event', event, data }, DB_ORIGIN)
}
