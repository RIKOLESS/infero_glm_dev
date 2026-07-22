# db 知识库

这个目录是 **公路预警应急智能体（db）** 的知识层。它不是普通文档，也是 db 运行时通过 `/api/kb/*` 主动检索的资料库——skill 层保持精简（只放身份 + 能力代码），场景 SOP 和报告模板放到这里按需加载。

## 目录

| 目录 | 内容 | 谁读它 |
|---|---|---|
| `platform_inventory.md` | luwang 平台 API + 数据源 + 前端页面全景 vs 比赛需求对照 | 评委 / db 判断能力边界 |
| `playbooks/` | 7 大比赛场景的 SOP（预报-研判-决策-处置-评估五节结构） | db 遇到场景任务时 `kb.read('playbooks/xxx')` |
| `reports/` | 6 类报告模板（值班简报 / 应急处置方案 / 救援调配表 / 物资调配 / 地震排查任务 / 防御提示） | db 生成报告前 `kb.read('reports/xxx')` 拿模板 |
| `api/` | luwang 接口手册简版 | db 需要构造非常规查询时参考 |

## 知识层设计原则

1. **不进 core memory**：只有 db 显式调用 `window.kb.read(name)` 时，那一段才进入当前轮次上下文，用完随消息滚动自然遗忘，不占永久位。
2. **按能力分类，不按场景切 skill**：7 场景 SOP = 7 份 md，共享同一个 `knowledge_base` skill 检索能力。避免"一个场景一个 skill、共享逻辑写 7 遍"的膨胀。
3. **可审计**：所有内容都是 markdown，git 追踪、评委可直接读。
4. **可扩展**：新增场景只需加一份 md，不改 skill 代码。

## HTTP 接口

后端 `server/knowledge_base.py` 暴露：

```
GET /api/kb/list                    # 返回按目录分组的文档索引 + 标题
GET /api/kb/read?name=playbooks/short_term_warning
GET /api/kb/search?q=山洪
```

前端 `weather_platform` skill 会封装成 `window.kb.list()` / `window.kb.read(name)` / `window.kb.search(q)`。

## 5-phase 闭环叙事

比赛评分维度里"闭环管理"（预报—研判—决策—处置—评估）是核心叙事。每个 playbook 的 5 节结构直接对应这 5 个阶段，报告顶部的 `phase` 徽章也是同一套编码：

| 阶段 | 场景动作 |
|---|---|
| `forecast` | 短临预警查询 / 数值预报解读 |
| `analyze` | 多源数据交叉、多灾种耦合、桩号级研判 |
| `decide` | 响应级别建议、力量预置方案、救援匹配 |
| `act` | 大屏联动展示、报告发放、任务派单 |
| `review` | 闭环回写、数据来源留痕、不确定点标注 |
