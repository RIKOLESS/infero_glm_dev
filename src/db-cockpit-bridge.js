/*
 * src/db-cockpit-bridge.js
 * 驾驶舱模式的 db 侧桥。加载后自动做三件事：
 *   1. 检测本页是否被 iframe 嵌在 luwang 驾驶舱内
 *   2. 若是，通过 postMessage 与父窗口握手，握手成功后在本 window 挂
 *      `window.luwangController` 代理（同名函数集，返回 Promise）
 *   3. 提供 `window.dbCockpit` 便捷方法（上报状态、呼出 AgentPanel、订阅事件）
 *
 * 独立控制台模式（未被 iframe 嵌套）下，本文件加载后不做任何副作用，
 * 只在 `window.dbCockpit` 上挂一个 `mode='standalone'` 标记。
 *
 * 与 agent-frontend/bridge.js 是配对协议。
 */

(function () {
  'use strict';

  const isEmbedded = window.parent !== window;
  // 接受 localhost 与 127.0.0.1 两种 origin（浏览器视为不同域，但都是同一台 luwang）
  const LUWANG_ORIGINS = new Set([
    'http://localhost:8080',
    'http://127.0.0.1:8080',
  ]);
  const extraOrigin = new URLSearchParams(location.search).get('parentOrigin');
  if (extraOrigin) LUWANG_ORIGINS.add(extraOrigin);
  // 主 origin 用于回信（postMessage target）—— 优先与 document.referrer 匹配
  let LUWANG_ORIGIN = 'http://localhost:8080';
  try {
    const refOrigin = new URL(document.referrer || '').origin;
    if (LUWANG_ORIGINS.has(refOrigin)) LUWANG_ORIGIN = refOrigin;
  } catch (_) {}

  // === 通用状态 ===
  const state = {
    mode: 'standalone',        // 'standalone' | 'cockpit'
    controllerReady: false,    // 握手成功后置 true
    controllerMethods: [],
    listeners: {},             // event -> Set<fn>
    reqSeq: 0,
    pending: new Map(),        // id -> { resolve, reject, timer }
    handshakePromise: null,
  };

  // === postMessage 发送 ===
  function post(msg) {
    if (!isEmbedded) return;
    try {
      window.parent.postMessage(msg, LUWANG_ORIGIN);
    } catch (e) {
      console.warn('[db-bridge] postMessage failed:', e);
    }
  }

  function nextId() {
    state.reqSeq += 1;
    return 'db-' + Date.now() + '-' + state.reqSeq;
  }

  function request(cmd, { timeout = 15000 } = {}) {
    if (!isEmbedded || !state.controllerReady) {
      return Promise.reject(
        new Error('luwangController 不可用（当前非驾驶舱模式或握手未完成）')
      );
    }
    return new Promise((resolve, reject) => {
      const id = nextId();
      const timer = setTimeout(() => {
        state.pending.delete(id);
        reject(new Error('luwang cmd 超时: ' + cmd.type));
      }, timeout);
      state.pending.set(id, { resolve, reject, timer });
      post({ src: 'db', type: 'cmd', id, cmd });
    });
  }

  // === IndexedDB 小助手（工作区句柄读写） ===
  function openGenesisDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open('GenesisDB');
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error || new Error('open GenesisDB failed'));
    });
  }
  function getBeingId() {
    return window.currentBeingId || null;
  }
  async function listAllFsHandles() {
    const beingId = getBeingId();
    if (!beingId) return [];
    const db = await openGenesisDB();
    return new Promise((resolve) => {
      const tx = db.transaction('beings', 'readonly').objectStore('beings').getAll();
      tx.onsuccess = () => {
        const rows = tx.result || [];
        resolve(rows.filter(r => r && r.id && r.id.startsWith(beingId + '/fs_')
          && r.value && (r.value.kind === 'file' || r.value.kind === 'directory')));
      };
      tx.onerror = () => resolve([]);
    });
  }
  async function putFsHandle(id, handle) {
    const db = await openGenesisDB();
    return new Promise((resolve, reject) => {
      const req = db.transaction('beings', 'readwrite').objectStore('beings').put({ id, value: handle });
      req.onsuccess = () => resolve(true);
      req.onerror = () => reject(req.error || new Error('put fs handle failed'));
    });
  }
  async function deleteFsHandle(id) {
    const db = await openGenesisDB();
    return new Promise((resolve) => {
      const req = db.transaction('beings', 'readwrite').objectStore('beings').delete(id);
      req.onsuccess = () => resolve(true);
      req.onerror = () => resolve(false);
    });
  }
  function autoSendSysMsg(text) {
    try {
      const inputEl = document.getElementById('input');
      const sendBtn = document.getElementById('send-btn');
      if (!inputEl || !sendBtn) return false;
      const draft = inputEl.value;
      inputEl.value = text;
      sendBtn.click();
      if (draft && draft.trim() !== '') {
        setTimeout(() => { inputEl.value = draft; inputEl.focus(); }, 100);
      }
      return true;
    } catch (e) {
      console.warn('[db-bridge] autoSendSysMsg failed:', e);
      return false;
    }
  }

  // === 消息接收 ===
  window.addEventListener('message', async (e) => {
    if (!isEmbedded) return;
    if (!LUWANG_ORIGINS.has(e.origin)) return;
    const msg = e.data;
    if (!msg || msg.src !== 'cockpit') return;

    switch (msg.type) {
      case 'pong': {
        const p = state.pending.get(msg.id);
        if (p) {
          clearTimeout(p.timer);
          state.pending.delete(msg.id);
          p.resolve(msg.data);
        }
        break;
      }
      case 'cmd-result': {
        const p = state.pending.get(msg.id);
        if (!p) return;
        clearTimeout(p.timer);
        state.pending.delete(msg.id);
        if (msg.ok) p.resolve(msg.data);
        else p.reject(new Error(msg.error || 'unknown error'));
        break;
      }
      case 'event': {
        const listeners = state.listeners[msg.event];
        if (listeners) {
          for (const fn of listeners) {
            try { fn(msg.data); } catch (err) { console.error('[db-bridge] listener err:', err); }
          }
        }
        break;
      }
      case 'mode': {
        window.__dbUiMode = msg.mode;
        const listeners = state.listeners['ui-mode'];
        if (listeners) for (const fn of listeners) fn(msg.mode);
        break;
      }
      case 'ui-size': {
        const size = msg.size || 'standard';
        window.__dbCockpitSize = size;
        document.body.classList.remove('db-cockpit-size-mini', 'db-cockpit-size-standard', 'db-cockpit-size-wide');
        document.body.classList.add('db-cockpit-size-' + size);
        const listeners = state.listeners['ui-size'];
        if (listeners) for (const fn of listeners) fn(size);
        break;
      }
      case 'fs-handle': {
        // 父窗口调 picker 拿到 handle 后传进来。写入 IndexedDB 并通知 db。
        try {
          const beingId = getBeingId();
          if (!beingId) {
            post({ src: 'db', type: 'fs-ack', id: msg.id, ok: false, error: 'currentBeingId not ready' });
            break;
          }
          const handle = msg.handle;
          if (!handle || !handle.name || !handle.kind) {
            post({ src: 'db', type: 'fs-ack', id: msg.id, ok: false, error: 'invalid handle' });
            break;
          }
          const key = beingId + '/fs_' + handle.name;
          await putFsHandle(key, handle);
          const kindLabel = handle.kind === 'directory' ? '文件夹' : '文件';
          autoSendSysMsg('[系统通知] 人类已通过驾驶舱授权你访问本地' + kindLabel + ' "' + handle.name + '"。句柄键名: "' + key + '"。');
          post({ src: 'db', type: 'fs-ack', id: msg.id, ok: true, data: { id: key, name: handle.name, kind: handle.kind } });
          // 触发 iframe 内工具栏刷新
          document.dispatchEvent(new CustomEvent('db-fs-handle-updated'));
        } catch (err) {
          post({ src: 'db', type: 'fs-ack', id: msg.id, ok: false, error: err.message });
        }
        break;
      }
      case 'fs-list': {
        try {
          const handles = await listAllFsHandles();
          const items = [];
          for (const h of handles) {
            let perm = 'prompt';
            try { perm = await h.value.queryPermission({ mode: 'readwrite' }); } catch (_) {}
            items.push({ id: h.id, name: h.value.name, kind: h.value.kind, permission: perm });
          }
          post({ src: 'db', type: 'fs-list-result', id: msg.id, ok: true, data: items });
        } catch (err) {
          post({ src: 'db', type: 'fs-list-result', id: msg.id, ok: false, error: err.message });
        }
        break;
      }
      case 'fs-wake': {
        try {
          const handles = await listAllFsHandles();
          const target = handles.find(h => h.id === msg.handleId);
          if (!target) {
            post({ src: 'db', type: 'fs-ack', id: msg.id, ok: false, error: 'handle not found' });
            break;
          }
          const perm = await target.value.requestPermission({ mode: 'readwrite' });
          const ok = perm === 'granted';
          if (ok) {
            autoSendSysMsg('[系统通知] 人类已重新唤醒本地"' + target.value.name + '"的读写权限。');
          }
          post({ src: 'db', type: 'fs-ack', id: msg.id, ok, data: { permission: perm } });
          document.dispatchEvent(new CustomEvent('db-fs-handle-updated'));
        } catch (err) {
          post({ src: 'db', type: 'fs-ack', id: msg.id, ok: false, error: err.message });
        }
        break;
      }
      case 'fs-remove': {
        try {
          const handles = await listAllFsHandles();
          const target = handles.find(h => h.id === msg.handleId);
          if (target) {
            await deleteFsHandle(msg.handleId);
            autoSendSysMsg('[系统通知] 人类已撤销本地"' + target.value.name + '"的授权。');
          }
          post({ src: 'db', type: 'fs-ack', id: msg.id, ok: true });
          document.dispatchEvent(new CustomEvent('db-fs-handle-updated'));
        } catch (err) {
          post({ src: 'db', type: 'fs-ack', id: msg.id, ok: false, error: err.message });
        }
        break;
      }
      default:
        break;
    }
  });

  // === 握手 ===
  function handshake() {
    if (!isEmbedded) return Promise.resolve(false);
    if (state.handshakePromise) return state.handshakePromise;
    state.handshakePromise = new Promise((resolve) => {
      const id = nextId();
      const timer = setTimeout(() => {
        state.pending.delete(id);
        console.warn('[db-bridge] handshake timeout, staying standalone');
        resolve(false);
      }, 5000);
      state.pending.set(id, {
        resolve: (data) => {
          state.controllerReady = true;
          state.mode = 'cockpit';
          state.controllerMethods = Object.keys((data && data.controller) || {});
          installControllerProxy();
          console.log('[db-bridge] handshake OK, cockpit ready, methods:', state.controllerMethods);
          resolve(true);
        },
        reject: () => resolve(false),
        timer,
      });
      post({ src: 'db', type: 'ping', id });
    });
    return state.handshakePromise;
  }

  // === controller 代理 ===
  function installControllerProxy() {
    const proxy = {};
    const known = new Set([
      'toggleLayer', 'selectArea', 'selectRoad', 'flyTo',
      'playAnimation', 'stopAnimation', 'togglePanel',
      'navigate', 'openBigScreen',
      'drawMarkers', 'clearMarkers',
      'renderOverlay', 'clearOverlay',
      'batch', 'ping',
    ]);
    // 已知函数
    for (const name of known) {
      proxy[name] = (...args) =>
        request({ type: name, args: args.length === 1 ? args[0] : args });
    }
    // 服务端返回的实际函数集（以 pong 返回的为准）
    for (const name of state.controllerMethods) {
      if (proxy[name]) continue;
      proxy[name] = (...args) =>
        request({ type: name, args: args.length === 1 ? args[0] : args });
    }
    // 元信息
    Object.defineProperty(proxy, '__proxy', { value: true });
    window.luwangController = proxy;
  }

  // === 便捷方法（db 主脑用） ===
  const dbCockpit = {
    get mode() { return state.mode; },
    get ready() { return state.controllerReady; },

    /** 上报 db 状态到驾驶舱顶栏 */
    reportStatus(status, text, task) {
      if (!isEmbedded) return;
      post({ src: 'db', type: 'state', state: { status, text, task } });
    },

    /** 呼出 AgentPanel 显示报告（html 类型） */
    async showReportHtml(html, options = {}) {
      if (!state.controllerReady) throw new Error('cockpit 未就绪');
      return request({
        type: 'renderOverlay',
        args: [{
          panelType: 'html',
          data: { html },
          options: Object.assign({ mode: 'tab-report' }, options || {}),
        }],
      });
    },

    /** 呼出 AgentPanel 显示文本 */
    async showText(title, content, stats, options = {}) {
      return request({
        type: 'renderOverlay',
        args: [{
          panelType: 'text',
          data: { title, content, stats },
          options: Object.assign({ title, mode: 'tab-summary' }, options || {}),
        }],
      });
    },

    /** 呼出 AgentPanel 显示表格 */
    async showTable(title, columns, rows, options = {}) {
      return request({
        type: 'renderOverlay',
        args: [{
          panelType: 'table',
          data: { title, columns, rows },
          options: Object.assign({ title, mode: 'tab-table' }, options || {}),
        }],
      });
    },

    /** 关闭 AgentPanel */
    async hidePanel() {
      return request({ type: 'clearOverlay' });
    },

    /** 向 AgentPanel 的“联动日志” Tab 追加一行 */
    async log(text, kind = 'info') {
      if (!state.controllerReady) return;
      try {
        return await request({
          type: 'renderOverlay',
          args: [{
            panelType: 'log',
            data: { text, kind, ts: Date.now() },
            options: { mode: 'tab-log' },
          }],
        });
      } catch (_) { /* 不打断主流程 */ }
    },

    /** 订阅平台事件（layer-changed / route-selected 等） */
    on(event, fn) {
      if (!state.listeners[event]) state.listeners[event] = new Set();
      state.listeners[event].add(fn);
      return () => state.listeners[event].delete(fn);
    },

    /** 手动重试握手（如首次未及时握上） */
    retryHandshake() {
      state.handshakePromise = null;
      state.controllerReady = false;
      return handshake();
    },
  };
  window.dbCockpit = dbCockpit;

  // 启动
  if (isEmbedded) {
    handshake().then((ok) => {
      if (!ok) {
        console.log('[db-bridge] running standalone (parent is not luwang cockpit)');
      }
    });
  } else {
    console.log('[db-bridge] standalone mode (no parent frame)');
  }
})();
