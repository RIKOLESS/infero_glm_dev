# 同事 luwang_python 方案对比与借鉴 (2026-07-21)

> 来源：https://gitee.com/lovelittletree/luwang，同事 `绎微 (Yìwēi)` 的 python 版 db + 直接注入 luwangfrontend 方案。
> 更新时间：`ee90be5..f239927`（本次拉取新增 1874 行）
> 用途：找出同事新做的、值得我们（web 版 db）借鉴的点，按优先级评估。

## 一、同事这次做了什么

### 1. 7 个 scenes 类（scenes/scene1_warning.py ...scene7_defense.py）
每个 scene 是一个 Python 类，继承 `Scene` 基类，实现三段流程：`_fetch_data → _operate_screen → _show_*`。

- **scene1 短临预警** —— 最完整：全国态势/按省/按城市/按经纬度半径/按路线/降雨排行/7天趋势/预警播报/**跨省对比** 9 种查询模式；调 6 个 API（overview/topRainfall/typeStats/provinceAnalysis/weeklyTrend/rainfallWarning/routeSegmentAlerts）；含 haversine 距离过滤；内置 30 个省份中心 + 30 个城市中心坐标；发 ECharts 堆叠柱状图。
- scene2-7 是骨架（46-130 行），逻辑较简单

### 2. controller.js 新增能力
- **drawMarkers / clearMarkers** —— agent 可以在 Leaflet 地图上画彩色标记点（含聚合、弹窗），非常有用（画救援点、隐患点、震中）
- **selectArea 支持多省** —— `cmd.provinces` 同时高亮多个省，服务跨省对比场景

### 3. overlay.js 新增能力
- **append 模式** —— 一个 AgentPanel 内堆叠"文本+表格+图表"多块内容，中间有分割线
- **inject.js 动态加载 ECharts** —— 让 chart 更稳定

### 4. 完整的场景数据字典（scenes/scene1_cases.md、cases/__init__.py）
- 用例集，覆盖 20+ 种自然语言问法

## 二、能力对比

| 能力 | 同事 python 版 | 我方 web 版（infero_glm_dev） | 结论 |
|---|---|---|---|
| 智能体框架 | Genesis fork | infero + glm 定制版 | 各有千秋 |
| 大屏操控 | inject.js 直连 Vue app + WebSocket | agent-frontend cockpit + postMessage 桥 | 我方更松耦合（同页共生） |
| 一键智能查询 | scene 类 `.run()` 方法 | `smartQuery(userText)` | 相似度高，我方已实现 |
| 短临预警查询模式 | **9 种**（含跨省/按路线/半径） | 1 种（省份+场景） | **我方需扩展** |
| 报告输出 | show_text + show_table + show_chart 分散 | renderReport 统一 HTML 报告 | 我方更完整 |
| 地图标记 (marker) | **drawMarkers ✅** | ❌ 无 | **可借鉴** |
| ECharts 图表 | ✅ 已用 | 只在报告页有 SVG bar | 可加强 |
| 演示模式（无 token 也能跑） | ❌ 未见 | ✅ WEATHER_MODE=demo | 我方优势 |
| 知识库/playbook | ❌ 未见 | ✅ docs/playbooks + docs/reports | 我方优势 |
| 后端 API 抽象 | 直接 fetch luwang API | WeatherAdapter 中间层 | 我方更清晰 |
| 即开即用（评委验收） | 需 3 步（ws-server + vite + luwang） | start.bat 一键 | 我方优势 |

## 三、建议借鉴清单（按优先级）

### P0（立即可做，1 天内）

1. **给 smartQuery 加"9 种查询模式"** —— 参考 scene1_warning.py
   - 当前只识别"省份"，扩展识别"城市名 / 经纬度 / 路线号 / '排行' / '趋势' / '播报' / '对比' 等意图关键词"
   - 效果：用户问"看下 G76 的预警"、"贵州和云南对比"、"最近 7 天降雨趋势" 都能一键出图
   - 实现：`smartQuery` 内加 intent 二级识别（city/location/road/compare/ranking/trend）

2. **报告加"路段桩号清单"** —— 对齐比赛"路段编号 + 起止桩号"硬要求
   - 现在报告有"重点路段明细表"但字段不全，需保证 `highway/segment/rainfall/level` 都有
   - 已通过 `collectRiskRows` 兼容多种字段名，需 QA 验证 live 模式下真拉出数据

### P1（1-2 天内）

3. **加 drawMarkers 能力** —— 让 db 能在 luwang 地图上画点
   - 用法：救援车辆点、物资库、地震震中、高危路段
   - 实现：在我方 `controller.js` 里加 `drawMarkers/clearMarkers`，跟同事的完全一样即可
   - 意义：让"应急资源调配 / 车辆救援 / 地震排查" 3 个 scene 立刻有可视化能力

4. **加 ECharts 到浮层** —— 让 renderReport 之外的答复也能带图
   - 场景：7 天预警趋势 / 类型分级饼图 / 跨省对比柱状图
   - 已在 overlay.js 支持 chart 类型，缺 ECharts 加载 + 数据适配

### P2（准备决赛/演示时）

5. **省份/城市坐标字典** —— 现在 smartQuery 硬编码了 14 个省，同事有 30 个省 + 30 个城市
   - 抄同事的 `_get_province_center / _get_city_center` 一键补齐
6. **AgentPanel append 模式** —— 让"文本结论 + 明细表 + 趋势图"堆在一个面板
   - 目前我方走"一份完整报告 iframe"，其实覆盖了 append 的场景，可以不做
7. **scene1_cases.md 里的 20+ 用例迁移到我方 tests/user_test_cases.md** —— 直接扩展我们的测试样例库

## 四、不建议借鉴的

1. **不要引入 Python scenes 后端类** —— 我们的 smartQuery + WeatherAdapter 已经在做同一件事，重构代价大且不带来新能力
2. **不要走 WebSocket 桥** —— 我们的 postMessage 已经解决了通信问题，且免了额外服务
3. **不要抄 inject.js 的动态 vite 注入** —— 我们的 `agent-frontend` 已经是等价方案

## 五、决策与承诺

**本次实施**（今天，1 小时内）：
- ✅ 修 AgentPanel 拖动 / 关闭 bug（iframe pointer-events）
- ✅ 让 smartQuery 自动 renderReport 出完整报告（不再只显示 5 个数字）
- ✅ 更新 GLM_API_KEY
- ✅ 存比赛需求文字版（本目录 `competition_requirements.md`）

**下一步计划**（今晚/明天）：
- P0-1：smartQuery 加 9 种查询模式识别
- P1-3：controller.js 加 drawMarkers（画救援点/隐患点/震中）
- P2-5：补全 30 省 + 30 城市中心坐标字典
- P2-7：迁移同事的 20+ 用例到我方测试文档

**评估**：同事版本在"短临预警场景的深度"上确实做得更细，但整体架构和演示便利性我们不弱。**核心 gap 在 scene1 广度 + 地图标记 + 图表** —— 都是加法，不需要重构。
