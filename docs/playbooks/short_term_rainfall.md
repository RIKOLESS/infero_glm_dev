# playbook · 短临强降雨与高影响路段

> 适用触发词：短临、强降雨、暴雨、山洪、内涝、路段影响、雨情研判。
> 场景对齐：比赛场景 1（公路气象短临预警）+ 附带数据源 4（气象数值预报和雷达拼图）。
> 推荐报告模板：`reports/duty_brief.md`（值班简报）或 `reports/risk_alert.md`（风险预警通报）。

---

## 一、预报（forecast）

**目标**：识别未来 2 小时内可能触发红/橙色降雨的重点路段。

数据源与调用：

- `await window.weatherPlatform.summary({ province })`：聚合预警统计 + 短临排行 + 受影响路段 TOP10 + 风险区。
- `await window.weatherPlatform.shortTerm({ province, hours: 2 })`：短临降雨与影响路段，字段侧重桩号级别。
- `await window.weatherPlatform.shortTermSichuan()`：四川通用示范（含大屏跳转），无省份指定时快速起手。

关键字段：

- `publishLevelStats` 或 `alert/publishLevelStats`：本轮红/橙/黄/蓝预警数量。
- `shortTermRank` / `road/rank/shortTerm`：桩号级降雨排行，字段常见 `highwayName / segmentLabel / maxRainfall`。
- `affectedTop10` / `road/segment/affectedTop10`：受影响 TOP10 路段。
- `riskZoneClass1 / class2`：连续降雨一/二类风险区，判断"降雨叠加历史积水"。

**判定阈值**（结合平台内部规则，若数据缺失则说明）：

- 短时（1h）> 20mm、或 3h > 50mm：进入橙色关注。
- 短时（1h）> 50mm、或 3h > 100mm：红色关注，须给出防御提示。
- 位于 `riskZoneClass1` 内的橙色以上降雨：直接按红色处置。

---

## 二、研判（analyze）

按顺序完成：

1. **总体形势**：本轮降雨规模、覆盖省份、发布中 R/O/Y/B 数量，一句话概括。
2. **重点路段筛选**：
   - 从 `shortTermRank / affectedTop10 / highImpactSegments` 汇总，去重取 TOP 5-10 条。
   - 每条给出 `所属路线 · 桩号或路段名 · 累计/短时降雨 · 风险标签`。
   - 若某路段同时命中 `class1 / class2 风险区` 或 `hazardPoints`，加 "叠加隐患点" 提示。
3. **趋势判断**：
   - 未来 2h 是否仍在增强（若接口返回时序），如无时序数据就说明"仅当前时刻"。
4. **数据质量**：
   - 引用 `summary.data_quality.success / empty / failed`；失败/空数据接口逐一列出。

---

## 三、决策（decide）

给出可执行方案，避免"很危险"式空话。

响应级别建议：

| 情形 | 建议响应级别 | 关键操作 |
|---|---|---|
| 出现红色降雨影响国高主干线 | 建议启动 **III 级响应**（跨省协调）| 通报路网中心 + 沿线路政 + 交警 |
| 橙色降雨叠加连续降雨一类风险区 | 建议启动 **IV 级响应**（省内联动）| 通报省高指挥中心 + 相关路段管理处 |
| 单站红色但未影响主干线 | 值班加密监视 | 值班主任签发信息通报 |

处置动作清单（按需要选用）：

- 派遣路政沿线巡查（提示注意桩号）。
- 检查隧道排水、边坡视频监控（`hazardPoints` 里的桥梁 / 隧道 / 边坡）。
- 在关键节点预置警示锥、导向、临时限速。
- 通报应急管理局气象服务组、水利部门（若涉及山洪风险区）。

---

## 四、处置（act）

db 侧动作：

1. `window.weatherPlatform.renderStatus(bundle)`：在右侧 Canvas 挂出任务卡片，含数据源清单。
2. `window.weatherPlatform.renderReport(report)`：出简报摘要卡（含"打开报告 / 导出报告 / 复制文本"按钮）。
3. `window.weatherPlatform.openBigScreen('shortTerm')`：一键跳转短临预报大屏，让值班员直观看到风险空间分布。
4. 若用户要求可视化叠加，可提示"3D 大屏见 `openBigScreen('threeMap')`、总览看 `analysisReport`"。

对外沟通建议：

- 值班简报走 `reports/duty_brief.md`，注重"最新数据 + 已通报对象 + 建议动作"。
- 风险预警通报走 `reports/risk_alert.md`，主标注"级别 / 影响时间 / 影响路段 / 防御措施"。

---

## 五、评估（review）

事件结束后（或次日值班交接前）：

- 从 `overview/keySegments` 反查各路段是否发生阻断、封控、事故。
- 对比预警 → 实际发生：预警提前量、命中率、误报率各多少。
- 简报里"经验教训"部分至少 2 条：一条数据类（哪个接口有延迟/空），一条流程类（通报是否及时）。
- 用 `reports/after_action.md` 出复盘小结，归档到值班日志。

---

## 附：常见坑与提醒

- **PROVINCE 参数**：接口有的用 `provinceCode`（`51`），有的用 `province` 名，WeatherAdapter 已做归一，直接传中文/编码都行。
- **时间窗口**：`shortTerm` 默认 2h，若用户问 6h/12h，改用 `mediumTerm` 的 `hours` 参数。
- **空数据不是失败**：`data_state='empty'` 时要说明"该接口本轮无风险条目"，不要判为接口挂掉。
- **不许伪造桩号**：数据缺失时明确说"本轮暂无该路段桩号级明细"，而不是编造数字。
