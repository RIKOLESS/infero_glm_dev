# infero_glm_dev · 公路预警应急智能体（db）

> 面向"第二届综合交通运输大模型智能体创新应用大赛"的参赛作品。
> db 是一个基于 GLM-5.2 的网页版智能体控制台，配套已有的路网气象平台（luwang）为公路气象值班场景提供 **一句话查询 → 数据研判 → 平台联动 → 简报导出** 的闭环。

---

## 亮点

- **即开即用**：`.env.example` → `start.bat`（或 `python start_glm.py`），无需部署 luwang 平台即可跑通全部 7 个场景（`WEATHER_MODE=demo` 用本地样例数据）。
- **国产大模型主脑**：GLM-5.2 作为主脑（`glm-5.2`，通过阿里云 MaaS 兼容 OpenAI 协议），Qwen 作为视觉副脑仅在需要时补充截图理解。
- **平台驾驶舱交互**：db 独立控制台负责对话与研判，luwang 平台大屏作为可视化驾驶舱；一键跳转 4 个大屏（`shortTerm / analysisReport / rainfall / threeMap`）。
- **闭环 5 阶段**：每份报告都带 `phase` 字段（预报 → 研判 → 决策 → 处置 → 评估），呼应比赛要求。
- **知识分层**：核心记忆只装身份与工具指引，7 份场景 SOP + 6 份报告模板作为 markdown 知识库按需 lazy-load，避免上下文膨胀。
- **数据质量透明**：每份报告都附成功 / 空 / 失败接口清单和数据模式（live/demo），不夸大数据可信度。
- **数据源真实可追溯**：底层聚合的是 luwang 平台 20+ 个真实接口（气象预警、短临排行、风险路段、隐患点、救援点、物资库、地震台网 AMQ 常驻订阅…）。

---

## 快速开始（demo 模式，0 依赖）

```
git clone <this repo>
cd infero_glm_dev
copy .env.example .env      # Windows；Linux/macOS 用 cp
# 编辑 .env，把 GLM_API_KEY 换成你的 key（申请入口：https://bailian.console.aliyun.com/）
start.bat                    # Windows
# 或
python start_glm.py          # 跨平台
```

浏览器会自动打开 `http://127.0.0.1:8000/src/`。

- 首次进入会弹出"生成新 Being"，直接确认即可。
- db 加载完成后，输入 `/exec browser await window.weatherPlatform.shortTermSichuan()` 或直接说"研判一下四川未来两小时的强降雨影响路段"即可看到端到端演示。
- 打开 Canvas 右上角"打开报告 / 导出报告"按钮即可查看完整报告页 / 下载 HTML。

---

## 驾驶舱模式（推荐评委演示，同页展示）

在独立控制台模式之外，我们做了个"驾驶舱模式"：**把 db 嵌到 luwang 平台大屏的同一个页面里**，让评委在一个浏览器窗口就能同时看到大屏可视化和 db 的对话流，中间通过 postMessage 桥直接调 luwang controller（开图层、飞地图、切大屏），无需人工在两个窗口之间切换。

### 前置

- `infero_glm_dev` 已经跑起来（走上面"快速开始"，`start.bat` 起 db 后端 + 独立控制台，占 `:8000`）。
- 克隆 luwang 前端到姐妹目录：`F:/彩云/luwang/luwangfrontend/`（或用环境变量 `LUWANG_FRONTEND_PATH` 指向你的目录）。
- luwang 前端跑一次 `npm install`。

### 启动驾驶舱

```powershell
cd F:\彩云\luwang\luwangfrontend
npx vite --config F:\彩云\infero_glm_dev\infero_glm_dev\agent-frontend\vite.config.js
```

浏览器打开 `http://localhost:8080/`，你会看到：

- **顶栏**：`● db 智能体 · 状态 · 数据模式 · 值班/演示切换 · ◧ 折叠`
- **左侧**：luwang 平台原生大屏（登录页 / bigScreen / analysisReport / …）
- **右侧驾驶舱**：内嵌 db iframe（`http://localhost:8000/src/?mode=cockpit`），完整对话流 + Canvas
- **AgentPanel**（浮层）：db 生成的报告 / 表格 / 图表就地弹在中央
- **右下浮球** `db`：折叠驾驶舱后一键呼出

### 用法

在右侧 iframe 里对 db 说话即可，比如：

- "帮我打开短临大屏，把降雨图层和风险路段图层都打开，飞到四川"
- "研判四川未来两小时强降雨影响路段，把简报浮出来给我看"

db 会检测到 `window.weatherPlatform.cockpit.available === true`，通过 postMessage 直接让 luwang 完成图层开关、地图飞行、路由切换，并把生成的报告 HTML 弹到 AgentPanel 里。

### 独立 vs 驾驶舱

| 特性 | 独立控制台 `:8000/src/` | 驾驶舱 `:8080` |
|---|---|---|
| db 主脑 / 知识库 / WeatherAdapter | 一致 | 一致 |
| 平台联动 | `window.open` 弹新标签 | 同页 controller 直接跳 |
| 报告展示 | Canvas + 独立报告页 | Canvas + 中央 AgentPanel |
| 适合场景 | 深度分析、离线复盘 | 值班驾驶舱、评委演示 |

驾驶舱是"额外的展现层"：`agent-frontend/` 里的所有代码都不改 luwang 源码（走 Vite `--config` 注入 + `/@fs/` 加载），也不改 db 源码（`src/db-cockpit-bridge.js` 在独立模式下退化为空操作），git pull 两侧仓库都无冲突。

细节协议（postMessage）见 [`agent-frontend/README.md`](agent-frontend/README.md)。

---

## 系统架构

```
                           ┌───────────────────────────────────┐
                           │  值班员 / 评委（浏览器）           │
                           │  http://127.0.0.1:8000/src/       │
                           └───────────────┬───────────────────┘
                                           │
                     ┌─────────────────────┼──────────────────────┐
                     │                     │                      │
              ┌──────▼──────┐    ┌─────────▼─────────┐    ┌──────▼──────┐
              │ db 主脑     │    │  Canvas / 报告页  │    │ luwang 大屏 │
              │ GLM-5.2     │    │  简报 · 导出      │    │ (独立窗口)  │
              └──────┬──────┘    └─────────▲─────────┘    └──────▲──────┘
                     │  /api/chat          │                     │
                     │                     │ 简报数据            │ 一键跳转
                     ▼                     │                     │
             ┌───────────────────────────────────────────────────┴──────┐
             │  Python 后端  server/  (start_glm.py)                    │
             │                                                          │
             │  glm_proxy       主脑/副脑请求路由 + 图像脱敏             │
             │  weather_adapter  luwang API 归一 + 数据质量 + demo 兜底 │
             │  knowledge_base   docs/*.md 只读接入                     │
             │  skill_hub        local_hub/ 本地 skill 存取             │
             │  demo_data        data/samples/*.json 本地样例           │
             └────────────┬──────────────────────────┬──────────────────┘
                          │                          │
                 ┌────────▼────────┐         ┌───────▼────────┐
                 │ 阿里云 MaaS      │         │  luwang 后端    │
                 │ (glm-5.2 / qwen) │         │  Go / Gin       │
                 └──────────────────┘         └────────────────┘
                                                       │
                                              ┌────────▼────────┐
                                              │ PostGIS / MySQL │
                                              │  20+ 数据源     │
                                              └─────────────────┘
```

关键设计：

1. **单进程 Python 后端**：`server/` 目录内 8 个模块，每个 <500 行，评委可 5 分钟读完。
2. **前端零构建**：`src/index.html` 一个文件，`file:` 或 `http:` 打开都能跑。
3. **两套数据路径**：`WEATHER_MODE=live` 走 luwang 真实接口；`WEATHER_MODE=demo` 直接读 `data/samples/*.json`；`WEATHER_MODE=auto` 优先 live，失败回落 demo。

---

## 目录结构

```
infero_glm_dev/
├─ README.md                    # 本文件
├─ .env.example                 # 环境变量模板
├─ start.bat / start_glm.py     # 一键启动
├─ src/
│  └─ index.html                # db 前端（Being + Canvas + Skill Hub）
├─ server/                      # Python 后端模块
│  ├─ main.py                   # HTTP 服务入口
│  ├─ handler.py                # 路由汇总
│  ├─ config.py                 # 环境变量 / 常量 / 省份编码
│  ├─ http_utils.py             # JSON 请求/响应工具
│  ├─ glm_proxy.py              # 主脑/副脑代理 + 图像脱敏
│  ├─ weather_adapter.py        # luwang 接口归一 + 场景 bundle + 数据质量
│  ├─ demo_data.py              # 本地样例加载
│  ├─ knowledge_base.py         # docs/*.md 只读接入 (/api/kb/*)
│  └─ skill_hub.py              # 本地 skill 存取
├─ docs/                        # 知识层（db 通过 window.kb.read 按需加载）
│  ├─ README.md                 # 知识层设计
│  ├─ platform_inventory.md     # luwang 平台 API 与场景/数据源对照
│  ├─ playbooks/                # 7 份场景 SOP（5 阶段结构）
│  │  ├─ short_term_rainfall.md
│  │  ├─ emergency_response.md
│  │  ├─ vehicle_rescue.md
│  │  ├─ material_dispatch.md
│  │  ├─ force_prepositioning.md
│  │  ├─ earthquake_survey.md
│  │  └─ defense_advisory.md
│  └─ reports/                  # 6 份报告模板
│     ├─ duty_brief.md
│     ├─ risk_alert.md
│     ├─ incident_report.md
│     ├─ daily_summary.md
│     ├─ after_action.md
│     └─ decision_memo.md
├─ data/
│  └─ samples/                  # WEATHER_MODE=demo 时的样例数据
├─ local_hub/                   # 本地 skill 仓库
└─ tests/
   └─ smoke_demo.py             # demo 模式端到端冒烟测试
```

---

## 演示脚本（推荐评委 3 分钟看完）

以下步骤都能在 `WEATHER_MODE=demo` 下 100% 复现，不需要真实平台 token。

1. **能力自检**：`Take a look around` — db 在 Canvas 挂出工作台首页，列出四大能力与四个大屏入口。
2. **短临降雨研判**：`研判一下四川未来 2 小时的强降雨影响路段` — 拉短临排行 + 受影响路段 + 风险区 + 隐患点，Canvas 出摘要卡（含"打开报告 / 导出报告 / 复制文本"三个按钮）。
3. **大屏联动**：点 Canvas 里的"打开短临大屏" — 新窗口进 luwang 平台 `bigScreenBox/shortTermForecast`；如果没登录，可自行 login 后重跳。
4. **值班简报**：`请出一份四川片区的值班简报` — db 读 `docs/reports/duty_brief.md` 骨架，用当前数据实例化。
5. **物资调拨**：`如果 G5 京昆四川段发生山洪阻断，最近的救援车辆和物资库怎么调` — db 读 `docs/playbooks/vehicle_rescue.md` + `material_dispatch.md`，出决策建议书。
6. **地震排查**：`最近一次四川地震需要排查哪些桥梁隧道` — db 读 `docs/playbooks/earthquake_survey.md`，取 `earthquake` + `resources`，圈定排查任务。
7. **导出报告**：任意一次报告右上角"导出报告" — 下载可离线打开、打印、提交的 HTML。

---

## 与 luwang 平台的关系

- luwang 提供：数据接入 + GIS 计算 + 可视化大屏（Go Gin + Vue3 + Leaflet / Cesium）。
- db 补足：自然语言问答入口 + 多灾种耦合研判 + 闭环叙事 + 文本生成 + 驾驶舱操作。
- **db 不改 luwang 源码**：一切通过 luwang 的 HTTP API 交互；视觉副脑仅用来确认页面状态，不作为事实数据源。
- 详见 `docs/platform_inventory.md`。

---

## 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `GLM_API_KEY` | 阿里云 MaaS 的 GLM key（自动前缀 `Bearer `） | 必填 |
| `GLM_AUTH_HEADER` | 已带 `Bearer ` 前缀的完整 Authorization | 可替代 `GLM_API_KEY` |
| `GLM_MODEL` | 主脑模型名 | `glm-5.2` |
| `GLM_UPSTREAM` | 上游 chat/completions 地址 | 阿里云默认 |
| `VISION_MODEL` | 视觉副脑模型 | `qwen3.7-plus` |
| `LUWANG_BASE_URL` | luwang 后端地址 | `http://118.121.196.98:8888` |
| `LUWANG_TOKEN` | luwang 登录 token | 空（demo/auto 可留空） |
| `WEATHER_MODE` | `live` / `demo` / `auto` | `auto` |
| `INFERO_PORT` | 前端 + 后端监听端口 | `8000` |

**推荐评委配置**：`WEATHER_MODE=demo` + 填写 `GLM_API_KEY` 即可端到端跑通全部 7 个场景。

---

## 隐私与合规

- token / 密钥 / cookie **绝不写进对话、报告、Canvas 或长期记忆**；db 侧只显示"已配置 token / 未配置 token"。
- `data/samples/*.json` 是根据平台真实接口结构构造的样例数据，**不含任何真实事故 / 人员 / 电话信息**。
- 平台联动只做展示引导，不下达任何指令；正式指令由值班主任 / 应急指挥中心签批。
- 决策类输出（响应级别、力量调派、物资调拨）默认保留"待人工确认"字样，明确 db 的边界。

---

## 相关项目

- 原版（Gemini 系）：<https://github.com/infero-net/infero/tree/dev>
- Python 版（同事分支）：<https://github.com/xi-studio/Genesis>
- 本仓库（GLM-5.2 + luwang 接入）：<https://github.com/RIKOLESS/infero_glm_dev>
- 路网气象平台前端：<https://gitee.com/cdcaiyun/luwangfrontend>
- 路网气象平台后端：<https://gitee.com/cdcaiyun/luwangbackend>

---

## 感谢与致敬

- 大赛：第二届综合交通运输大模型智能体创新应用大赛。
- 平台方：四川彩云环境科技有限公司（luwang 平台）。
- 模型方：阿里云 MaaS（GLM-5.2 与 Qwen）。
- 原型：infero-net 团队与 xi-studio 团队的开源工作。
