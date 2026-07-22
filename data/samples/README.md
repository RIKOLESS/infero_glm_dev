# Demo Mode 样例数据

这里的每个 `*.json` 文件都 **1:1 模仿真实 luwang 后端接口的响应结构**，用于评委无 token / 无网络时的离线演示。

## 命名约定

样例文件名 = 接口路径去掉前导 `/` 并把 camelCase 转成 snake_case：

| luwang 接口 | 样例文件 |
|---|---|
| `/api/weather/alert/publishLevelStats` | `api_weather_alert_publish_level_stats.json` |
| `/api/road/rank/shortTerm` | `api_road_rank_short_term.json` |
| `/api/rainfallWarning/highImpactSegments` | `api_rainfall_warning_high_impact_segments.json` |

`server/weather_adapter.py::_default_demo_key()` 负责路径 → 样例名转换；也可以在 `call_luwang_bundle` 里显式传第四个参数 `demo_key`。

## 场景覆盖

| 场景 | 用到的样例 |
|---|---|
| 1. 短临预警 | `api_road_rank_short_term` / `api_road_segment_affected_top10` / `api_rainfall_warning_high_impact_segments` / `api_rainfall_warning_affected_segment_counts` / `api_rainfall_warning_data_update_times` |
| 2. 突发事件处置 | 复用短临预警数据 + `api_weather_alert_publish_level_stats` |
| 3. 车辆救援 | `api_overview_vehicle_rescue_points` |
| 4. 物资调配 | `api_overview_material_reserves` |
| 5. 力量预置 | 3 + 4 组合 |
| 6. 地震排查 | `api_weather_earthquake_latest` + `api_overview_risk_segments` + `api_overview_hazard_points` + `api_overview_vehicle_rescue_points` |
| 7. 防御提示 | `api_weather_alert_publish_level_stats` + `api_weather_alert_type_stats` + `api_weather_alert_province_stats` + `api_weather_alert_weekly_trend` + `api_weather_risk_warning_latest` |

## 剧情设定

样例数据讲的是同一个故事：**2026-07-20 傍晚，四川强降雨影响都汶高速、蓉昌高速等国高路段，同时汶川附近发生 5.8 级地震**。

- 短临降雨 TOP10 全部集中在四川及川南山区
- 河洪 / 地质 / 山洪三类风险预警同时发布
- 汶川县地震（震级 5.8，烈度 7.0），叠加已有的边坡隐患
- 救援点和物资储备库覆盖成都、绵阳、雅安三个基地

这样 db 智能体在 demo 模式下能生成一份**多灾种耦合**（暴雨 + 地质 + 地震）的完整研判报告，正好呼应报名表里"多灾种耦合风险研判模型对高风险路段的识别准确率较人工经验显著提升"的评分维度。

## 如何添加/修改样例

1. 直接编辑对应文件，保存即刷新（`server/demo_data.py` 有轻量缓存，改动后重启 `start_glm.py` 即可）。
2. 结构参考 `F:/彩云/luwang/luwangbackend/server/model/business/vo/*.go`。
3. 保持 `code / msg / data` 三级结构，`data` 可以是数组或对象，`server/weather_adapter.luwang_payload` 会自动拆包。
