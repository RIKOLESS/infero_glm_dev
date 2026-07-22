# playbook · 地震灾损排查评估

> 适用触发词：地震、震感、烈度、震中、灾损、桥梁排查、隧道排查、路基排查。
> 场景对齐：比赛场景 6（地震灾损排查评估）。
> 推荐报告模板：`reports/incident_report.md`（事件通报）+ `reports/after_action.md`（复盘）。

---

## 一、预报（forecast）

**目标**：一旦收到地震消息，立刻圈定烈度范围内的路段与隐患点，输出排查任务清单。

数据源与调用：

- `await window.weatherPlatform.earthquake({ province })`：拿最新震例（中国地震台网 AMQ 常驻订阅），返回 `{ time, magnitude, depth, epicenter, intensityHint, ... }` 及圈内路段/隐患点上下文。
- `await window.weatherPlatform.resources({ province })`：救援点 + 物资库 + 风险路段 + 隐患点。
- `await window.weatherPlatform.summary({ province })`：叠加当前是否有降雨、大风等次生风险。

关键字段：

- `earthquake.latest`：震级 / 深度 / 震中经纬度 / 参考地点 / 发布时间。
- `hazardPoints`（`tunnel / bridge / slope / drainage`）：桥梁、隧道、边坡、排水，需按距离震中重排。
- `riskSegments`：既有风险路段。

---

## 二、研判（analyze）

按四步：

1. **震级分档**（参考经验，可调）：
   - M < 4.5：一般无需大范围排查，值班关注即可。
   - 4.5 ≤ M < 6.0：以震中 50 km 为半径圈定重点排查。
   - 6.0 ≤ M < 7.0：以震中 100 km 为半径圈定重点排查，桥梁 / 隧道 / 高边坡逐一核查。
   - M ≥ 7.0：全省进入 II 级以上响应，跨省协调。
2. **烈度区圈定**：
   - 若接口返回 `intensityHint / intensityCircles` 直接使用。
   - 否则用震中经纬度 + 半径粗算（明确写"半径为经验粗算，须以震后正式烈度图为准"）。
3. **路段与隐患点提取**：
   - 从 `hazardPoints` 提取圈内桥梁 / 隧道 / 高边坡 / 排水关键设施。
   - 从 `riskSegments` 提取圈内既有风险路段。
   - 按距离震中排序，形成排查优先级 TOP N。
4. **次生风险叠加**：
   - 若同期有降雨/大风：滑坡、泥石流风险升高，加"次生灾害警戒"。
   - 若为山区且季节偏雨：主动提示"关注余震 + 次生"。

---

## 三、决策（decide）

输出排查任务清单：

```
地震灾损排查建议（震后 0–6h）
震例：<M x.x · 震中：<地点> · 时间：<UTC+8>>

一、圈定范围
- 建议排查半径：~<X> km（依震级经验，未接入正式烈度图）
- 覆盖省份：<省份列表>

二、优先排查设施（TOP N）
1. <桥梁/隧道/边坡名称> · <路线 · 桩号> · 距震中 ~<Y> km
2. ...

三、力量部署
- 救援点：<最近救援点列表>
- 物资库：<最近物资库列表>
- 建议由 <单位> 牵头，<对接单位> 协同

四、次生风险提示
- 是否有同期降雨/大风预警：<有/无 · 简述>
- 余震关注：M 5.0 以上震例 24h 内需持续跟踪

五、注意事项
- 本建议基于台网台站首波估算，正式烈度图以中国地震局发布为准
- db 不下达排查指令，须由指挥部门签批
```

---

## 四、处置（act）

db 侧动作：

1. `renderStatus(bundle)`：Canvas 展示震例卡 + 排查设施 TOP N。
2. 出 `reports/incident_report.md` 事件通报，重点写"震例信息 + 排查范围 + 优先路段 + 通报对象"。
3. `openBigScreen('threeMap')` 便于空间核对（若平台有地震专题图层，路径由 `localStorage.luwang_screen_routes` 覆盖）。
4. 建立小时级复查机制：每 1h 拉一次 `earthquake` 与 `summary`，跟踪余震与次生。

---

## 五、评估（review）

事件闭环后：

- **排查完成度**：TOP N 设施是否全部核查、是否补充新的设施进 TOP。
- **实际灾损**：与初期估算对比，记录漏判 / 误判。
- **响应时长**：从震后消息接入 → 首份通报 → 排查方案下发的时长。
- **数据可用性**：`cenc_earthquake` 数据是否及时（如平台断源，明说走 demo fallback）。
- 用 `reports/after_action.md` 归档，重点写"半径估算 vs 正式烈度图"的偏差。

---

## 附：常见坑与提醒

- **半径粗算 ≠ 正式烈度图**：db 输出中必须显式说明"经验半径"，避免误导。
- **数据来源可能延迟**：AMQ 消息偶尔滞后，`earthquake.latest` 显示时间要与当前时间对比，超过 30 分钟前的震例主动标记"最新一次已过 30 分钟"。
- **不要混淆震级与烈度**：震级是能量，烈度是破坏程度，避免用词混用。
- **隐患点数据分类**：`hazardPoints` 的 `category` 字段可能是 `tunnel / bridge / slope / drainage`，缺失时按名称粗猜并注明"分类未标注"。
