# luwang 平台能力盘点 vs 比赛需求对照

> 更新时间：2026-07-20
> 用途：db 智能体识别可用数据源、评委审核代码时快速了解平台能力边界。

## 一、平台后端 API 总览

### 大屏 `/api/dashboard/*`
| 接口 | 说明 |
|---|---|
| `/api/dashboard/list` | 大屏预警列表 |
| `/api/dashboard/riskStatistics` | 风险统计看板数据 |
| `/api/dashboard/provinces` | 省份下拉 |
| `/api/dashboard/getHighwayDetail` | 高速路详情弹窗 |
| `/api/dashboard/getSegmentDetailById` | 单路段详情 |
| `/api/dashboard/updateTime` | 数据更新时间 |

### 概况 `/api/overview/*`
| 接口 | 说明 |
|---|---|
| `/api/overview` | 总体概况统计 |
| `/api/overview/provinceAnalysis` | 省份数据分析 |
| `/api/overview/topRainfall` | TOP10 降雨排名 |
| `/api/overview/rainfallIntensity` | 降雨强度分布 |
| `/api/overview/provinceDetail` | 各省详细分析 |
| `/api/overview/keySegments` | 重点路段预警与应急措施 |
| `/api/overview/adminRegions` | 全国行政区划树 |
| `/api/overview/luwangRoadFilterTree` | 路网筛选树（国高/省高） |
| `/api/overview/luwangRoadSegments` | 按分类筛选路段 |
| `/api/overview/luwangRoadRouteCodes` | 路线编号列表 |
| `/api/overview/vehicleRescuePoints` | 车辆应急救援点 |
| `/api/overview/materialReserves` | 国家物资储备库 |
| `/api/overview/riskSegments` | 风险路段（disaster_risk / flash_flood） |
| `/api/overview/hazardPoints` | 涉灾隐患点（tunnel / bridge / slope / drainage） |

### 气象预警 `/api/weather/alert/*`
| 接口 | 说明 |
|---|---|
| `/api/weather/alert/typeStats` | 预警类型分级统计 |
| `/api/weather/alert/publishLevelStats` | 四种层级预警类型×级别数量 |
| `/api/weather/alert/provinceStats` | 各省预警分级统计 |
| `/api/weather/alert/regionStats` | 政区下预警明细 |
| `/api/weather/alert/search` | 预警信息搜索 |
| `/api/weather/alert/regions` | 行政区划级联树 |
| `/api/weather/alert/weeklyTrend` | 近七天红橙黄蓝趋势 |
| `POST /api/weather/alert/push` | 外部推送（公开） |

### 风险与地震 `/api/weather/*`
| 接口 | 说明 |
|---|---|
| `/api/weather/riskWarning/latest` | 中央气象台风险预警（河洪/地质/山洪） |
| `/api/weather/earthquake/latest` | **中国地震台网中心地震记录** |

### 路段排行与风险区 `/api/road/*`
| 接口 | 说明 |
|---|---|
| `/api/road/rank/shortTerm` | 短临降雨排行 |
| `/api/road/rank/mediumTerm` | 中长期降雨排行（2h/6h/12h/24h/48h） |
| `/api/road/rank/realtime` | 实况排名（降雨/风速/温度） |
| `/api/road/rank/history` | 历史降雨排行 |
| `/api/road/segment/affectedTop10` | 受影响路段 TOP10（雨/雾/风/台风） |
| `/api/road/riskZone/class1` | 连续降雨一类风险区 |
| `/api/road/riskZone/class2` | 连续降雨二类风险区 |

### 降雨预警 `/api/rainfallWarning/*`
| 接口 | 说明 |
|---|---|
| `/api/rainfallWarning/highImpactSegments` | 恶劣天气高影响路段 |
| `/api/rainfallWarning/affectedSegmentCounts` | 受影响路段六边形聚合 |
| `/api/rainfallWarning/continuousRainRisks` | 短期/长期连续降雨 |
| `/api/rainfallWarning/realtimeRainfallRank` | 实时降雨影响排名 |
| `/api/rainfallWarning/dataUpdateTimes` | 各数据源更新时间 |
| `/api/rainfallWarning/regionWarningPoints` | 按政区返回预警点位 |
| `/api/rainfallWarning/routeSegmentAlerts` | 按路线返回路段中心点及三种天气预警 |

### 地图自定义政区 `/api/map/customRegion/*`
支持 CRUD，用于用户组合多省筛选。

### GeoServer WMS 图层
- 地址：`http://118.121.196.98:30081/geoserver/traffic/wms`
- 常用图层：`traffic:luwang_highways` / `traffic:china_district` / `traffic:china_province`
- 影响图层：`traffic:luwang_impact_heavy_rain_map`（降雨）/ `luwang_impact_strong_wind_map`（大风）/ `luwang_impact_dense_fog_map`（大雾）
- 影响等级：1-6（无雨/小/中/大/暴/大暴/特大暴雨）

## 二、平台前端页面

| 路由 | 页面 | 关键能力 |
|---|---|---|
| `/#/login` | 登录 | GVA 标准登录 |
| `/#/bigScreen` | 降雨大屏（2D） | Leaflet + WMS，天气图层切换、路网筛选、影响等级过滤 |
| `/#/bigScreenBox/analysisReport` | 分析看板 | 概况 + 各省柱图 + TOP10 + 应急措施表 |
| `/#/bigScreenBox/threeMap` | 3D 大屏 | Cesium/Three，图层管理 |
| `/#/bigScreenBox/shortTermForecast` | 短临预报大屏 | 时间轴 + 图层管理 + 风险卡片 |

## 三、平台后端定时任务

| 任务 | 周期 | 数据流 |
|---|---|---|
| `RefreshHighwaySummary` | 5min | 高速路气象聚合物化视图 |
| `SyncWeatherExternalAlerts` | 10min | 国家预警发布中心（SM4 解密） |
| `SyncNmcRiskWarnings` | 1h | NMC 三类风险预警爬虫 |
| `SyncTyphoonImpacts` | 1h | 彩云台风 API + PostGIS 路段相交 |
| `StartEarthquakeAMQConsumer` | 常驻 | 中国地震台网中心 AMQ 消息队列 |

## 四、7 大比赛场景 × 平台能力

| # | 场景 | 后端支持 | 前端支持 | 差距/db 需自造 |
|---|---|---|---|---|
| 1 | **公路气象短临预警** | ✅ `rank/shortTerm` + `affectedTop10` + `rainfallWarning/highImpactSegments`；后端已具备桩号级输出 | ✅ 短临预报大屏 | 1km/5min 精度由外部气象源决定；db 侧无需自造，重点是**输出可读的桩号级风险描述** |
| 2 | **突发事件应急处置** | ⚠️ `dashboard/riskStatistics` 提供级别统计，但**无预案库结构化数据** | ⚠️ 无独立预案页 | **db 需自造预案 SOP 知识库**（放 `docs/playbooks/emergency_response.md`），基于气象+风险数据智能匹配响应级别 |
| 3 | **车辆应急救援** | ✅ `vehicleRescuePoints` 全网救援点经纬度 | ✅ threeMap/bigScreen 图层展示 | **路径规划平台没做**：db 侧做距离粗算 + 说明性建议，不真跑 GIS 路径算法（评委可接受，标明"最优路径需接入路径规划服务"） |
| 4 | **应急装备物资储备调配** | ✅ `materialReserves` 物资储备库 | ✅ 图层展示 | **调拨方案生成平台没做**：db 侧结合灾情距离+匹配度自造简化方案 |
| 5 | **应急力量预置** | ⚠️ 救援点 + 物资 + 风险路段都有原子数据，但**缺"力量-风险"匹配** | ⚠️ 无预置成效评估页 | db 需自造预置模板 + 成效评估维度 |
| 6 | **地震灾损排查评估** | ✅ **`cenc_earthquake` 表 + `/api/weather/earthquake/latest` + AMQ 常驻消费 + mock 种子数据** | ⚠️ 无地震专题页 | 数据齐全，db 侧需做**烈度圈影响路段圈定 + 排查任务优先级**（PostGIS 空间计算已在 typhoon 有先例，可复用思路） |
| 7 | **公路气象预警防御提示** | ✅ `alert/*` 各省分级统计 + `publishLevelStats` | ✅ 大屏可展示 | **"防御提示文本自动生成"平台没做**：正是 db 的价值所在——数据 → 分级响应文本 |

**结论**：7 场景中 **5 个平台已有充分数据支撑**（1/3/4/6/7），**2 个需要 db 侧做知识层封装**（2/5）。**没有场景需要造假数据**——demo 模式下所有接口都能返回真实平台数据结构，只是断网时 fallback。

## 五、6 内 + 4 外数据源 × 平台数据

### 内部 6 类
| 数据源 | 平台是否有 | 覆盖情况 |
|---|---|---|
| 公路基础信息 | ✅ | `luwang_roads` 全国高速 29.8w 线段 + `national_roads` 旧表 |
| 承灾体普查 | ⚠️ 部分 | `luwang_roads.category_l2` 有分类；无独立普查接口 |
| 汛冬两季风险隐患排查 | ✅ | `map_layer_risk_segment`（disaster_risk / flash_flood）+ `map_layer_hazard_point`（隧道/桥梁/边坡/排水） |
| 车辆应急救援 | ✅ | `map_layer_vehicle_rescue` |
| 应急物资储备 | ✅ | `map_layer_material_reserve` |
| 公路灾毁阻断 | ❌ | 无独立表；demo 模式可 mock 少量样例 |

### 外部 4 类
| 数据源 | 平台是否有 | 覆盖情况 |
|---|---|---|
| 气象数值预报和雷达拼图 | ✅ | 数值预报字段（`national_roads.forecast_*`）+ 短临排行；雷达图层通过 GeoServer WMS 提供 |
| 地理信息 | ✅ | PostGIS + `admin_region` + `luwang_roads.geom` |
| 全国地震预警 | ✅ | **`cenc_earthquake` 表 + AMQ 常驻订阅 + mock 种子数据可离线复现** |
| 山洪地质灾害预警 | ✅ | `nmc_risk_warning`（河洪/地质/山洪）+ NMC 爬虫定时任务 |

**结论**：10 类数据里 **9 类平台有真实来源**，只有 `公路灾毁阻断` 需要 demo 时 mock，可以走"该数据源当前无实时接入"的诚实叙事。

## 六、db 智能体的价值定位（对评委）

平台已经解决了：**数据接入、GIS 计算、可视化展示**。

db 智能体补足的是：
1. **自然语言问答入口** —— 值班员一句话即可查询平台数据。
2. **多灾种耦合研判** —— 跨多个 API 组合信息（如"降雨 + 风险路段 + 救援点"三接口一次调）。
3. **闭环叙事** —— 预报 → 研判 → 决策 → 处置 → 评估 全链条串起来。
4. **文本生成** —— 值班简报、应急处置方案、防御提示文本，减少人工写作。
5. **平台驾驶舱操作** —— 让 db 帮值班员打开对应大屏、切图层、定位路段。

## 七、Demo 模式 fallback 策略

评委路径的样例数据（`data/samples/*.json`）按照真实接口 schema 构造，覆盖 7 场景：

| 场景 | 样例文件 | 数据来源 |
|---|---|---|
| 1. 短临预警 | `short_term_rank.json` | 模仿 `rank/shortTerm` 响应，含桩号 |
| 2. 突发事件 | `dashboard_risk_statistics.json` | 模仿 `dashboard/riskStatistics` |
| 3. 车辆救援 | `vehicle_rescue_points.json` | 模仿 `overview/vehicleRescuePoints` |
| 4. 物资调配 | `material_reserves.json` | 模仿 `overview/materialReserves` |
| 5. 力量预置 | 复用 3+4+`risk_segments.json` | 组合模式 |
| 6. 地震排查 | `cenc_earthquake_latest.json` + `luwang_roads_sample.json` | 模仿 `weather/earthquake/latest` + 小样本路段 |
| 7. 防御提示 | `alert_publish_level_stats.json` | 模仿 `alert/publishLevelStats` |

Demo 模式下所有 `WeatherAdapter` 接口返回结构与真实平台 100% 一致，前端和 db 主脑不感知差异。UI 顶部显示 "**数据源：演示样例**" 徽章明示。
