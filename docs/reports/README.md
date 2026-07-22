# reports — 报告模板目录

> db 生成简报 / 通报 / 报告时，通过 `await window.kb.read('reports/xxx')` 拉取对应骨架，再用实际数据填空。核心记忆里不放模板正文，避免上下文膨胀。

## 目录

| 模板 | 文件 | 场景 |
|---|---|---|
| 值班简报 | `duty_brief.md` | 值班交接、常态化早/晚班简报 |
| 风险预警通报 | `risk_alert.md` | 面向沿线单位的分级通报 |
| 事件通报 | `incident_report.md` | 具体突发事件 / 应急事件的对内通报 |
| 每日总结 | `daily_summary.md` | 日报 / 值班日结 |
| 复盘评估 | `after_action.md` | 事件闭环后的 AAR / 教训归档 |
| 决策建议书 | `decision_memo.md` | 面向决策者的方案陈述（力量预置 / 物资调拨 / 救援调派） |

## 通用格式约定

所有模板遵循以下要素：

- **标题**：`【类别】主题 · 时间戳（UTC+8）`
- **摘要**：3 行以内，先给结论。
- **正文**：分节，每节 3–8 行，避免大段散文。
- **数据来源**：结尾一段固定字段，说明 WeatherAdapter 调用、成功/空/失败接口、数据模式（live/demo）。
- **签发信息**：单位 + 时间；db 生成的报告写 "db 智能体草拟 · 待值班主任审核"。

## 使用示例

```javascript
// 生成一份值班简报
const tpl = await window.kb.read('reports/duty_brief');
// tpl.content 是 markdown 模板；db 用当前数据实例化后交给 renderReport / openReport
```

或者结合 `weatherPlatform.reportDraft` + `openReport` 直接展示。
