# agent-frontend · db 驾驶舱模式

> 把 db 智能体嵌入 luwang 平台大屏页面的注入插件。启动后，luwang 平台原生大屏保留原样，右侧多一条驾驶舱栏（内嵌 db），报告以浮层形式弹在中央。
>
> 本目录设计借鉴同事 [lovelittletree/luwang · agent-frontend](https://gitee.com/lovelittletree/luwang) 方案（Vite 外部 config + inject 脚本），把桥接协议从 WebSocket 换成 postMessage，简化部署。

## 目录

| 文件 | 作用 |
|---|---|
| `vite.config.js` | 外部 Vite 配置：合并 luwangfrontend 原配置 + 我们的插件，端口沿用 8080 |
| `agent-inject-plugin.js` | Vite 插件：向 luwang `index.html` 注入 `inject.js` |
| `inject.js` | 注入入口：等 Vue app 就绪 → 挂驾驶舱 UI + AgentPanel + 嵌 db iframe |
| `controller.js` | 平台控制层：暴露 `window.luwangController`（toggleLayer / selectArea / flyTo / batch …） |
| `cockpit.js` | 驾驶舱 UI：顶栏状态条 + 右侧抽屉（内嵌 db iframe） + 右下浮球 |
| `overlay.js` | AgentPanel 浮层：text / table / chart / html 四种渲染器，可拖 / 可钉 |
| `bridge.js` | postMessage 桥：处理 db iframe ↔ luwang controller 的双向通信 |
| `styles.css` | 驾驶舱 + AgentPanel 统一样式（沿用平台青蓝色板） |

## 启动

前置：

- `luwangfrontend` 目录已存在（默认在 `../../luwang/luwangfrontend/`，可通过环境变量 `LUWANG_FRONTEND_PATH` 覆盖）。
- `infero_glm_dev` 已跑起来（`start.bat`，默认 8000 端口），驾驶舱模式的 db iframe 会加载 `http://localhost:8000/src/?mode=cockpit`。

启动驾驶舱模式：

```powershell
cd F:\彩云\luwang\luwangfrontend
npx vite --config F:\彩云\infero_glm_dev\infero_glm_dev\agent-frontend\vite.config.js
```

浏览器自动打开 `http://localhost:8080`，进入 luwang 大屏后右侧驾驶舱自动展开。

若要临时回落"独立控制台"模式（不装 db 驾驶舱），只跑原生 `npx vite`，db 单独开 `http://localhost:8000/src/` 即可。

## 通信协议（postMessage）

### db → parent

```jsonc
// 请求 luwang controller 执行指令
{ "src": "db", "type": "cmd", "id": "req-1", "cmd": { "type": "toggleLayer", "layer": "emergencyPoints", "on": true } }

// 请求 AgentPanel 显示内容
{ "src": "db", "type": "cmd", "id": "req-2", "cmd": { "type": "renderOverlay", "panelType": "html", "data": { "html": "…" } } }

// 通知父窗口 db 状态变化（供顶栏状态条同步）
{ "src": "db", "type": "state", "state": { "status": "thinking", "task": "研判贵州" } }
```

### parent → db

```jsonc
// 指令执行完毕回执
{ "src": "cockpit", "type": "cmd-result", "id": "req-1", "ok": true, "data": null }

// 平台事件推送
{ "src": "cockpit", "type": "event", "event": "layer-changed", "data": { "layer": "emergencyPoints", "on": true } }

// 让 db 显示指定视图（未来扩展）
{ "src": "cockpit", "type": "ui", "ui": "show-welcome" }
```

## 与"独立控制台"模式的关系

| 特性 | 独立控制台（`localhost:8000/src/`）| 驾驶舱模式（`localhost:8080`）|
|---|---|---|
| db 大脑 | 一致 | 一致 |
| 知识库 | 一致 | 一致 |
| WeatherAdapter | 一致 | 一致 |
| 平台联动 | `window.open` 跳新窗口 | 同页驾驶舱 controller，直接开图层、飞地图 |
| 报告展示 | Canvas + 独立报告页 | Canvas + AgentPanel 就地浮层 |
| 适合场景 | 深度分析、离线复盘 | 值班驾驶舱、演示评委 |
