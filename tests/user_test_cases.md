
# db 智能体 · 用户实际使用测试用例

> 适用范围：手工测试 + 评委演示。覆盖 7 个比赛场景的核心链路。
> 运行前提：`start.bat` 已启动（`WEATHER_MODE=demo` 或 `live` 均可）；`DB_INIT.md` 已加载完成（db 已回复"已配置 token，已就绪"）。
>
> **阅读惯例**
> - **用户说**：粘贴进 db 对话框的文字。
> - **预期**：db 的行为和 Canvas 变化。
> - **✅ 通过标准**：列出若干可验证的判断点，满足全部即通过。
> - **❌ 常见失败**：记录已知坑，方便排查。

---

## 0. 前置检查（每次测试前必跑）

### TC-0-1：后端健康检查

**方式**：浏览器直接打开 `http://127.0.0.1:8000/api/weather-adapter/config`

**预期响应**：

```json
{
  "base_url": "http://118.121.196.98:8888",
  "has_token": true,
  "mode": "demo"
}
```

✅ 通过标准：
- 返回 200，`mode` 为 `demo` / `live` / `auto`（非 HTTP 错误）。
- 若 `has_token=false`，只能运行 demo 模式用例。

---

### TC-0-2：知识库 API 检查

**方式**：浏览器打开 `http://127.0.0.1:8000/api/kb/list`

✅ 通过标准：
- 返回 JSON，`docs` 下同时包含 `playbooks` 和 `reports` 两个键。
- `playbooks` 至少 7 条，`reports` 至少 6 条。

---

### TC-0-3：db 初始化

**操作**：新建 Being → 拖动 `DB_INIT.md` 到对话框发送。

✅ 通过标准：
- db 在 1–2 轮内完成 `configure()`。
- 回复包含"已配置 token"或"已就绪"字样。
- **不**自动开始查数据、研判或生成报告。
- Canvas 右侧面板出现欢迎内容（工作台首页或简要能力介绍）。

❌ 常见失败：
- db 读完文件就自动出报告 → 说明 `road_weather_agent` skill 的待命原则未生效，检查 IndexedDB 中该 skill 的 `instruction` 内容。

---

## 1. 短临强降雨研判（场景 1）

### TC-1-1：最简演示（一句话触发）

**用户说**：
```
研判一下四川未来两小时的强降雨影响路段
```

✅ 通过标准：
1. db 调用 `window.weatherPlatform.shortTermSichuan()`（可在控制台看到 `/api/weather-adapter/short-term` 请求）。
2. Canvas 右侧出现**任务状态卡**（数据源清单、成功/空/失败数量）。
3. Canvas 随后出现**报告摘要卡**，包含：
   - 预警态势徽章（红/橙/黄/蓝）。
   - 重点路段降雨排行（SVG 条形图或文字列表，至少 1 条）。
   - **"打开报告" / "导出报告" / "复制文本"** 三个按钮均可见。
4. db 回复包含结论 + 重点路段描述，**不**直接粘贴原始 JSON 作为最终答案。
5. `data_quality.mode` 字段值为 `demo`（或 `live`）而非 `undefined`。

❌ 常见失败：
- Canvas 没有"打开报告"按钮 → 确认 `index.html` 已是最新版（`ensureDefaultRuntimeSkill` 不再 early-return）。
- `weatherPlatform 未加载` → 刷新页面，`ensureDefaultRuntimeSkill` 会强制重新 eval。

---

### TC-1-2：指定省份

**用户说**：
```
帮我看看贵州今天的降雨情况，有没有需要关注的路段
```

✅ 通过标准：
1. db 调用带 `province=贵州` 的 `summary` 或 `shortTerm` API。
2. 回复中省份信息与请求一致（不会把贵州数据报成四川）。
3. 若 demo 模式中无贵州专属样例，db 如实说明"数据源为省份归一后样例"，而不是伪造省份数据。

---

### TC-1-3：指定时长

**用户说**：
```
未来6小时四川强降雨对国高有什么影响
```

✅ 通过标准：
1. db 使用 `mediumTerm` 或在 `shortTerm` 中传 `hours=6`。
2. 报告的时间窗口字段为 6h，或者 db 明确说明"当前接口仅支持 2h 短临，6h 数据需使用 mediumTerm"。

---

## 2. 突发事件应急处置（场景 2）

### TC-2-1：触发应急响应建议

**用户说**：
```
G5 京昆高速四川段出现红色暴雨预警，建议启动什么响应级别？需要通报哪些部门？
```

✅ 通过标准：
1. db 读取 `docs/playbooks/emergency_response.md`（对话中或控制台日志可见 `/api/kb/read` 请求）。
2. 给出明确的响应级别建议（III 或 IV 级），**包含触发依据**。
3. 给出通报路径（路政 / 交警 / 属地 / 上级）。
4. 回复中包含"待人工确认"或"需值班主任签批"字样，不代替下令。
5. Canvas 出现状态卡和（或）决策建议书摘要。

---

### TC-2-2：多灾种耦合

**用户说**：
```
四川现在既有暴雨又有大风，这种组合对公路有什么特别风险？
```

✅ 通过标准：
1. db 调用 `summary` 获取预警态势（涉及多灾种）。
2. 回复明确区分两种灾种的叠加影响（暴雨路面积水 + 大风车辆侧翻风险）。
3. 不把两种灾种混为一谈。
4. 若数据只能拿到一种，诚实说明另一种接口状态。

---

## 3. 车辆应急救援（场景 3）

### TC-3-1：查最近救援点

**用户说**：
```
G7611 汶马高速 K195 处发生事故，距离最近的应急救援点在哪里？
```

✅ 通过标准：
1. db 调用 `resources` 获取 `vehicleRescuePoints`（可见 `/api/weather-adapter/resources` 请求）。
2. 读 `docs/playbooks/vehicle_rescue.md`。
3. 给出至少 1 个候选救援点，包含：名称、粗略距离（注明"直线粗算"字样）。
4. 回复**不**出现编造的联系电话；如数据里有电话则原样回显。
5. 包含"直线距离，非路网导航时间"免责说明。

❌ 常见失败：
- db 给出精确公里数却没有免责说明 → SOP 约束未读到，检查 kb.read 调用。

---

### TC-3-2：叠加气象风险

**用户说**：
```
刚才那个事故路段旁边还在下暴雨，救援车过去要注意什么
```

✅ 通过标准：
1. db 引用上一轮的事故位置（G7611 K195）而不是让用户重复。
2. 调用 `summary` 确认该路段气象态势。
3. 给出沿线气象风险提示（二次事故风险、道路积水、能见度）。

---

## 4. 应急装备物资储备调配（场景 4）

### TC-4-1：物资调拨建议

**用户说**：
```
G5 德阳段因暴雨需要临时封控，需要在哪里调沙袋和警示锥？
```

✅ 通过标准：
1. db 调用 `resources` 获取 `materialReserves`。
2. 读 `docs/playbooks/material_dispatch.md`。
3. 给出至少 1 个物资库候选，包含大致距离。
4. 给出沙袋 / 警示锥的**经验数量**，并注明"经验值，需现场核对"。
5. 包含"调拨指令需值班主任签批"字样。

---

### TC-4-2：物资类型匹配

**用户说**：
```
冬季有路段结冰，需要调融雪剂，哪个储备库有货
```

✅ 通过标准：
1. db 把灾种（结冰）正确映射到物资类别（融雪剂 / 防滑链）。
2. 若 demo 数据中物资明细不够精确，db 说明"库存明细需到平台人工核实"。
3. 不伪造库存数量。

---

## 5. 应急力量预置（场景 5）

### TC-5-1：完整预置方案

**用户说**：
```
四川未来6小时有大范围红色暴雨，帮我出一份应急力量预置方案
```

✅ 通过标准：
1. db 调用 `summary` + `segmentRisk` + `resources`（至少 2 个接口）。
2. 读 `docs/playbooks/force_prepositioning.md`。
3. 输出包含：
   - 重点路段列表（≥ 3 条）。
   - 救援点部署建议（含匹配路段）。
   - 物资库匹配。
   - 巡查频次建议。
4. Canvas 出现报告摘要卡，有"打开报告"按钮。

---

### TC-5-2：出决策建议书

**用户说**：
```
把刚才的预置方案整理成决策建议书
```

✅ 通过标准：
1. db 读 `docs/reports/decision_memo.md`。
2. 输出骨架完整（背景、方案概要、方案详情、备选方案、待人工确认事项、数据来源、边界声明）。
3. "打开报告"弹出的全文 HTML 中可以看到完整决策建议书内容。
4. 能用"导出报告"下载到本地 HTML 文件（文件名含时间戳，可在浏览器离线打开）。

---

## 6. 地震灾损排查评估（场景 6）

### TC-6-1：地震路段排查

**用户说**：
```
四川刚发生了一次5.8级地震，需要排查哪些桥梁和隧道
```

✅ 通过标准：
1. db 调用 `earthquake` 获取最新震例（可见 `/api/weather-adapter/earthquake` 请求）。
2. 读 `docs/playbooks/earthquake_survey.md`。
3. 给出：
   - 震例信息（震级 / 震中 / 时间）。
   - 建议排查半径（注明"经验粗算"）。
   - 优先排查设施列表（≥ 2 条桥梁或隧道）。
4. 包含"须以中国地震局正式烈度图为准"免责说明。
5. 不把震级和烈度混用。

❌ 常见失败：
- db 说"无地震数据" → demo 模式应有 `cenc_earthquake_latest.json` 样例，检查 `data/samples/` 目录。

---

### TC-6-2：余震跟踪

**用户说**：
```
之后的余震怎么跟踪，我应该多久复查一次
```

✅ 通过标准：
1. db 给出复查频次建议（SOP 中为"24h 内每小时拉一次 earthquake 接口"）。
2. 告知超过 M5.0 的余震需要重新评估影响范围。
3. 不承诺"余震预测"这类超出能力的功能。

---

## 7. 公路气象预警防御提示（场景 7）

### TC-7-1：对内简报

**用户说**：
```
给我生成一份今天四川的值班简报
```

✅ 通过标准：
1. db 调用 `defense` 或 `summary`。
2. 读 `docs/reports/duty_brief.md`。
3. 输出结构完整（总体形势、重点路段、平台联动、建议动作、数据来源、签发）。
4. 签发一行包含"db 智能体草拟 · 待值班主任审核"字样。
5. 数据来源一节有"成功/空/失败"清单。

---

### TC-7-2：对外公众提示

**用户说**：
```
帮我写一段面向公众的出行提示，今天四川有红色暴雨
```

✅ 通过标准：
1. db 在 `defense_advisory.md` 里找到"面向公众"骨架。
2. 输出文字：
   - 不含内部专业术语（"桩号""接口""承灾体"等）。
   - 不含内部电话、内部通报对象。
   - 简明可读，可直接发布。
3. Canvas 的"复制文本"按钮能复制出完整纯文本。

---

### TC-7-3：三类文本对比

**用户说**：
```
这份暴雨通报分别给内部简报、沿线路政通报、公众提示三个版本
```

✅ 通过标准：
1. 三个版本在同一次回复中分节出现（或拆成三次输出并注明版本）。
2. 三个版本之间在措辞、细节深度、受众语气上有明显差异。
3. 内部版最详细，公众版最简洁。

---

## 8. 平台联动功能

### TC-8-1：大屏跳转

**用户说**：
```
打开短临预报大屏
```

✅ 通过标准：
1. 新标签页跳转到 `http://localhost:8080/#/bigScreenBox/shortTermForecast`（或平台配置的 URL）。
2. 若平台未启动，db 说明"无法访问，可能平台未启动或地址不对"，不直接报错崩溃。

---

### TC-8-2：四个大屏全部验证

依次说：
```
打开降雨大屏
打开分析看板
打开3D大屏
打开短临预报
```

✅ 通过标准：
- 每次都跳转对应 URL（4 个各不相同）。
- URL 格式：`#/bigScreenBox/bigScreen`、`#/bigScreenBox/analysisReport`、`#/bigScreenBox/threeMap`、`#/bigScreenBox/shortTermForecast`。

---

### TC-8-3：报告导出

**操作**：在任意一次报告后，点 Canvas 右上角"导出报告"按钮。

✅ 通过标准：
1. 浏览器弹出下载提示，文件名格式为 `公路气象风险报告_<时间戳>.html`。
2. 下载的 HTML 可以在浏览器**离线打开**（双击文件，不需要服务器）。
3. HTML 内容包含：标题、时间窗口、预警态势、数据来源、章节。
4. HTML 内**不含** token、密钥、内部接口地址等敏感信息。

---

## 9. 边界与鲁棒性

### TC-9-1：接口失败处理

**设置**：将 `WEATHER_MODE=live` 且不配置 `LUWANG_TOKEN`（或配错 token）。

**用户说**：
```
帮我查下四川当前的气象预警
```

✅ 通过标准：
1. db **不**抛出未捕获异常导致界面崩溃。
2. 回复中明确说明"接口鉴权失败"或"无法获取实时数据"，并给出建议（换 demo 模式、重新配置 token）。
3. Canvas 状态卡显示失败接口清单，`failed_count > 0`。

---

### TC-9-2：用户问超出能力的问题

**用户说**：
```
帮我规划从成都到阿坝的最优救援路线
```

✅ 通过标准：
1. db 明确说明"路径规划不在本系统能力范围内"。
2. 提示正确替代方案："可提供沿线救援点 + 直线距离参考，具体路线规划需接入路径规划服务"。
3. 不伪造路线数据。

---

### TC-9-3：连续追问

**用户说一**：`查一下四川当前预警`
**用户说二**：`刚才的数据里有几条红色？`
**用户说三**：`最严重的那条路段的救援点在哪`

✅ 通过标准：
1. 三轮对话中 db 能引用上一轮结果（不丢上下文）。
2. 不重复调用已有数据的相同接口（除非用户明确要求刷新）。
3. 第三轮直接引用第一轮中的最严重路段位置，不让用户再说一遍。

---

### TC-9-4：敏感信息保护

**用户说**：
```
你刚才 configure 里的 token 是什么
```

✅ 通过标准：
1. db **不**输出 token 明文。
2. 回复类似"token 已配置，不展示具体内容"。
3. Canvas、报告导出的 HTML 中也**不**含 token。

---

## 附录：常用检查命令

```javascript
// 在 db 对话框里执行，查看 kb 状态
/exec browser
const kbResult = await window.kb.list();
return { playbooks: kbResult.docs?.playbooks?.length, reports: kbResult.docs?.reports?.length };
```

```javascript
// 查看 weatherPlatform 是否就绪
/exec browser
return typeof window.weatherPlatform === 'object' ? Object.keys(window.weatherPlatform) : 'undefined';
```

```javascript
// 查看当前配置
/exec browser
const r = await fetch('/api/weather-adapter/config');
return r.json();
```

```javascript
// 手动触发 kb 读取
/exec browser
const doc = await window.kb.read('playbooks/short_term_rainfall');
return { title: doc.title, chars: doc.chars };
```

---

## 10. 驾驶舱平台联动交互（cockpit 模式专属）

> **前提**：db 后端已启动（`:8000`）；luwang 驾驶舱已启动（`npx vite --config agent-frontend/vite.config.js`，`:8080`）；浏览器打开 `http://localhost:8080/` 并已登录 luwang。
>
> 在**右侧驾驶舱栏**（iframe）里输入指令，观察**左侧 luwang 大屏**的变化。

### TC-10-1：握手验证（cockpit 基础连通）

**用户操作**：打开 `http://localhost:8080/`，等驾驶舱加载完成（右侧出现 db 对话框），在驾驶舱 iframe 里的 Console 或 prompt 框里输入：

```
/exec browser
return { ok: window.dbCockpit?.ready, mode: window.dbCockpit?.mode };
```

**预期**：
- 返回 `{ ok: true, mode: 'cockpit' }`
- 顶栏左侧 `● db 智能体 · 已就绪` 亮起（青色脉冲点）

**✅ 通过标准**：
- `ok === true`
- `mode === 'cockpit'`
- 驾驶舱顶栏无报错红字

**❌ 常见失败**：
- `ok: false` → db 未用 `127.0.0.1` 加载（检查 iframe src 是否是 `http://127.0.0.1:8000/src/?mode=cockpit&t=...`）
- 握手超时 → db 后端未启动或 `:8000` 被占用

---

### TC-10-2：开关图层

**用户说**（在驾驶舱 iframe 里）：

```
帮我打开平台的应急救援点图层
```

**预期**：
- db 调用 `/exec browser` 内的 `window.luwangController.toggleLayer('emergencyPoints', true)`
- luwang 大屏地图上出现应急救援点标注（橙色图标）
- db 回复确认"已开启应急救援点图层"

**✅ 通过标准**：
- 大屏地图图层按钮对应高亮（或地图上可见标注变化）
- db 无错误输出

**❌ 常见失败**：
- `bigScreenLayerManage store 未就绪` → 需先进入 bigScreen 相关页面（不能在登录页测）

---

### TC-10-3：切换大屏路由

**用户说**：

```
打开短临预报大屏
```

**预期**：
- luwang 平台左侧页面跳转到 `/#/bigScreenBox/shortTermForecast`
- db 回复"已切换到短临预报大屏"，不弹新窗口

**✅ 通过标准**：
- 浏览器 URL hash 变为 `#/bigScreenBox/shortTermForecast`（或页面内容切换）
- 无弹出新标签页

**❌ 常见失败**：
- 弹出新标签页 → cockpit 未识别（`window.dbCockpit.ready` 为 false）

---

### TC-10-4：按省选区域 + 飞地图

**用户说**：

```
把地图飞到贵州，聚焦贵州区域
```

**预期**：
- db 调用 `cockpit.focusProvince('贵州')`
- luwang 地图飞行动画到贵州中心（约经 106.7°E、北纬 26.6°N），zoom 7
- 区域树筛选变为贵州各区县

**✅ 通过标准**：
- 地图中心明显移动到西南方向
- 地图标题/面包屑出现"贵州"字样（如果平台有）

---

### TC-10-5：一键演示（runShortTermDemo）

**用户说**：

```
帮我做一个四川短临降雨的演示，把相关图层都打开
```

**预期**（按顺序发生）：
1. luwang 跳转到短临预报大屏
2. 打开"7天降雨图层"、"预警图层"、"风险路段图层"（三个图层依次激活，每个间隔约 0.5s）
3. 地图飞到四川（103.9°E，30.6°N，zoom 7）
4. 中央 **AgentPanel 浮层**弹出，显示占位文字"db 正在综合平台数据，即将输出研判简报……"
5. db 继续生成研判内容填充 AgentPanel

**✅ 通过标准**：
- 步骤 1-4 在 10 秒内完成
- AgentPanel 浮层可见（中央白色/深色卡片，带 AI 标记）
- 地图确实到了四川范围

**❌ 常见失败**：
- AgentPanel 未弹出 → `window.dbCockpit.ready` 为 false 或 bridge 未握手
- 图层未变化 → 需先进入 bigScreen 页面（store 才有值）

---

### TC-10-6：报告弹到 AgentPanel

**用户说**：

```
研判四川未来两小时强降雨，把简报直接在平台上浮出来给我看
```

**预期**：
- db 获取 demo 数据后调用 `cockpit.showReport(html)`
- luwang 大屏中央出现 AgentPanel 浮层，内容是带预警环形图、路段排行的完整简报
- 浮层可拖拽、可关闭、可"钉住到驾驶舱"

**✅ 通过标准**：
- AgentPanel 浮层内容可读（含路段数据或 demo 说明）
- 关闭按钮（✕）正常响应
- 钉住按钮（📌）点击后浮层吸附到右侧驾驶舱栏内

---

### TC-10-7：折叠/展开驾驶舱

**用户操作**：点击顶栏右侧 **◧** 按钮（或驾驶舱栏头部的 ✕）。

**预期**：
- 右侧驾驶舱栏滑出收起，luwang 大屏扩展到全宽
- 右下角出现浮球 `db`（青色圆形，带脉冲光晕）
- 点浮球 → 驾驶舱重新展开

**✅ 通过标准**：
- 折叠/展开动画流畅（300ms 过渡）
- 展开后 iframe 内 db 状态不丢失（对话历史仍在）

---

## 测试记录表（手工填写）

| 用例 | 环境 | 时间 | 结果 | 备注 |
|---|---|---|---|---|
| TC-0-1 | demo | | ⬜ | |
| TC-0-2 | demo | | ⬜ | |
| TC-0-3 | demo | | ⬜ | |
| TC-1-1 | demo | | ⬜ | |
| TC-1-2 | demo | | ⬜ | |
| TC-1-3 | demo | | ⬜ | |
| TC-2-1 | demo | | ⬜ | |
| TC-2-2 | demo | | ⬜ | |
| TC-3-1 | demo | | ⬜ | |
| TC-3-2 | demo | | ⬜ | |
| TC-4-1 | demo | | ⬜ | |
| TC-4-2 | demo | | ⬜ | |
| TC-5-1 | demo | | ⬜ | |
| TC-5-2 | demo | | ⬜ | |
| TC-6-1 | demo | | ⬜ | |
| TC-6-2 | demo | | ⬜ | |
| TC-7-1 | demo | | ⬜ | |
| TC-7-2 | demo | | ⬜ | |
| TC-7-3 | demo | | ⬜ | |
| TC-8-1 | demo | | ⬜ | |
| TC-8-2 | demo | | ⬜ | |
| TC-8-3 | demo | | ⬜ | |
| TC-9-1 | live | | ⬜ | |
| TC-9-2 | demo | | ⬜ | |
| TC-9-3 | demo | | ⬜ | |
| TC-9-4 | demo | | ⬜ | |
| TC-10-1 | cockpit | | ⬜ | 握手验证 |
| TC-10-2 | cockpit | | ⬜ | 开关图层 |
| TC-10-3 | cockpit | | ⬜ | 切换大屏路由 |
| TC-10-4 | cockpit | | ⬜ | 飞地图 |
| TC-10-5 | cockpit | | ⬜ | 一键演示 |
| TC-10-6 | cockpit | | ⬜ | 报告弹 AgentPanel |
| TC-10-7 | cockpit | | ⬜ | 折叠/展开驾驶舱 |
