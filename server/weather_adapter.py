"""WeatherAdapter — luwang platform data proxy for the GLM agent.

Responsibilities:
    1. Talk to the luwang backend over HTTP with a shared token/base_url.
    2. Normalize incoming params (time window, province code).
    3. Compact large responses and classify data quality per source.
    4. Aggregate multiple luwang endpoints into per-scenario bundles.
    5. Fall back to demo samples when WEATHER_MODE=demo or a live call fails
       under WEATHER_MODE=auto, so the demo path always yields a real-shape bundle.
    6. Tag each bundle with a `phase` field aligned to the competition's
       forecast → analyze → decide → act → review closed loop.
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from . import config, demo_data


# ---------------------------------------------------------------------------
# Token / base URL resolution
# ---------------------------------------------------------------------------

def get_luwang_token(handler=None, body: Optional[Dict[str, Any]] = None) -> str:
    """Resolve token in priority order: body -> X-Luwang-Token -> Authorization -> adapter state -> env."""
    if body and isinstance(body, dict):
        token = str(body.get('token') or '').strip()
        if token:
            return token
    if handler is not None:
        token = (handler.headers.get('X-Luwang-Token') or '').strip()
        if token:
            return token
        auth = (handler.headers.get('Authorization') or '').strip()
        if auth.lower().startswith('bearer '):
            return auth[7:].strip()
    import os as _os
    return (config.LUWANG_ADAPTER_STATE.get('token') or _os.environ.get('LUWANG_TOKEN', '').strip())


def get_luwang_base(body: Optional[Dict[str, Any]] = None) -> str:
    if body and isinstance(body, dict):
        base = str(body.get('base_url') or body.get('baseUrl') or '').strip()
        if base:
            return base.rstrip('/')
    return (config.LUWANG_ADAPTER_STATE.get('base_url') or config.LUWANG_DEFAULT_BASE).rstrip('/')


# ---------------------------------------------------------------------------
# Param normalization + time window
# ---------------------------------------------------------------------------

def parse_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ''):
            return default
        return int(float(value))
    except Exception:
        return default


def normalize_weather_params(params: Optional[Dict[str, Any]] = None, default_hours: int = 2) -> Dict[str, Any]:
    """Inject `startTime`/`endTime` (unix seconds) and resolve `provinceCode`.

    luwang short-term endpoints expect explicit unix timestamps. Frontend/agent
    often only supply `forecastHours`, so we compute a window aligned to `now`.
    Province names get mapped to adcodes via PROVINCE_CODE_MAP.
    """
    clean = dict(params or {})
    hours = parse_int(clean.get('forecastHours') or clean.get('hours'), default_hours)
    if hours <= 0:
        hours = default_hours
    now_ts = int(time.time())
    start_ts = parse_int(clean.get('startTime'), now_ts)
    end_ts = parse_int(clean.get('endTime'), start_ts + hours * 3600)
    if end_ts <= start_ts:
        end_ts = start_ts + hours * 3600
    clean['startTime'] = start_ts
    clean['endTime'] = end_ts
    clean['hours'] = hours

    province_text = str(
        clean.get('provinceCode')
        or clean.get('provinceName')
        or clean.get('province')
        or ''
    ).strip()
    if not clean.get('provinceCode') and province_text in config.PROVINCE_CODE_MAP:
        clean['provinceCode'] = config.PROVINCE_CODE_MAP[province_text]
    return clean


def format_local_ts(ts: Any) -> str:
    try:
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(ts)))
    except Exception:
        return ''


def time_window_meta(params: Dict[str, Any]) -> Dict[str, Any]:
    start_ts = params.get('startTime')
    end_ts = params.get('endTime')
    return {
        'startTime': start_ts,
        'endTime': end_ts,
        'hours': params.get('hours'),
        'startText': format_local_ts(start_ts),
        'endText': format_local_ts(end_ts),
    }


# ---------------------------------------------------------------------------
# Response shaping
# ---------------------------------------------------------------------------

def compact_json(value: Any, max_list: int = 20, max_string: int = 1200, depth: int = 0) -> Any:
    if depth > 5:
        return '[truncated-depth]'
    if isinstance(value, list):
        items = [compact_json(v, max_list, max_string, depth + 1) for v in value[:max_list]]
        if len(value) > max_list:
            items.append({'_truncated': len(value) - max_list})
        return items
    if isinstance(value, dict):
        return {str(k): compact_json(v, max_list, max_string, depth + 1) for k, v in value.items()}
    if isinstance(value, str) and len(value) > max_string:
        return value[:max_string] + f'...[truncated {len(value) - max_string} chars]'
    return value


def payload_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        if isinstance(value.get('list'), list):
            return len(value['list'])
        if isinstance(value.get('data'), list):
            return len(value['data'])
        if isinstance(value.get('items'), list):
            return len(value['items'])
        return len(value) if value else 0
    if value in (None, '', []):
        return 0
    return 1


def luwang_payload(data: Any) -> Any:
    if isinstance(data, dict) and 'data' in data:
        return data.get('data')
    return data


def data_state_from_count(count: int) -> str:
    return 'empty' if count == 0 else 'success'


def summarize_adapter_bundle(data: Dict[str, Any], errors: Dict[str, Any]) -> Dict[str, Any]:
    success: List[str] = []
    empty: List[str] = []
    failed: List[str] = list((errors or {}).keys())
    for key, value in (data or {}).items():
        meta = value.get('meta') if isinstance(value, dict) else None
        state = (meta or {}).get('state')
        if state == 'empty':
            empty.append(key)
        else:
            success.append(key)
    if failed and (success or empty):
        overall = 'partial'
    elif failed:
        overall = 'failed'
    elif empty and not success:
        overall = 'empty'
    else:
        overall = 'success'
    return {
        'overall': overall,
        'success': success,
        'empty': empty,
        'failed': failed,
        'success_count': len(success),
        'empty_count': len(empty),
        'failed_count': len(failed),
    }


def data_summary_from_bundle(data: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for key, value in (data or {}).items():
        if not isinstance(value, dict):
            continue
        meta = value.get('meta') or {}
        summary[key] = {
            'state': meta.get('state', 'success'),
            'count': meta.get('count'),
            'message': meta.get('message', ''),
            'url': value.get('url', ''),
            'source': value.get('source', 'live'),
        }
    return summary


# Competition closed-loop phase per scenario. Frontend renders a timeline badge.
SCENARIO_PHASE: Dict[str, str] = {
    'weather_risk_summary': 'analyze',
    'short_term_forecast': 'forecast',
    'segment_risk': 'analyze',
    'emergency_resources': 'decide',
    'emergency_response': 'decide',
    'rescue_dispatch': 'act',
    'material_dispatch': 'act',
    'force_prepositioning': 'decide',
    'earthquake_assessment': 'act',
    'defense_advisory': 'review',
    'duty_brief': 'review',
}


def adapter_response(
    scenario: str,
    params: Dict[str, Any],
    data: Dict[str, Any],
    errors: Dict[str, Any],
    next_actions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    quality = summarize_adapter_bundle(data, errors)
    out: Dict[str, Any] = {
        'scenario': scenario,
        'phase': SCENARIO_PHASE.get(scenario, 'analyze'),
        'mode': config.RUNTIME_STATE.get('weather_mode', config.WEATHER_MODE),
        'params': params,
        'time_window': time_window_meta(params),
        'data_quality': quality,
        'data_summary': data_summary_from_bundle(data),
        'sources': list((data or {}).keys()),
        'data': data,
        'errors': errors,
    }
    if next_actions:
        out['next_actions'] = next_actions
    return out


def collect_quality_from_summary(value: Any) -> Dict[str, List[str]]:
    quality: Dict[str, List[str]] = {'success': [], 'empty': [], 'failed': []}

    def visit(obj: Any) -> None:
        if not isinstance(obj, dict):
            return
        dq = obj.get('data_quality')
        if isinstance(dq, dict):
            quality['success'].extend(dq.get('success') or [])
            quality['empty'].extend(dq.get('empty') or [])
            quality['failed'].extend(dq.get('failed') or [])
        errors = obj.get('errors')
        if isinstance(errors, dict):
            quality['failed'].extend(errors.keys())
        for v in obj.values():
            if isinstance(v, dict):
                visit(v)
            elif isinstance(v, list):
                for item in v:
                    visit(item)

    visit(value)
    return {k: sorted(set(v)) for k, v in quality.items()}


# ---------------------------------------------------------------------------
# HTTP client — live luwang + demo fallback
# ---------------------------------------------------------------------------

def _demo_result_for(sample_key: str, source_url: str = '') -> Optional[Dict[str, Any]]:
    payload = demo_data.load_sample(sample_key)
    if payload is None:
        return None
    inner = luwang_payload(payload) if isinstance(payload, dict) else payload
    count = payload_count(inner)
    return {
        'url': source_url or f'demo://{sample_key}',
        'status': 200,
        'meta': {
            'state': data_state_from_count(count),
            'count': count,
            'message': 'demo sample',
        },
        'data': compact_json(payload if isinstance(payload, dict) else {'data': payload}),
        'source': 'demo',
    }


def _live_luwang_request(path: str, params: Dict[str, Any], token: str, base_url: str) -> Dict[str, Any]:
    base = (base_url or config.LUWANG_ADAPTER_STATE.get('base_url') or config.LUWANG_DEFAULT_BASE).rstrip('/')
    query = urllib.parse.urlencode(
        {k: v for k, v in (params or {}).items() if v not in (None, '')},
        doseq=True,
    )
    url = base + path + (('?' + query) if query else '')
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'INFERO-DB-WeatherAdapter/1.0',
    }
    if token:
        headers['x-token'] = token
    req = urllib.request.Request(url, headers=headers, method='GET')
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
        text = resp.read().decode('utf-8', errors='replace')
        try:
            data = json.loads(text)
        except Exception:
            data = {'raw': text}
        if isinstance(data, dict):
            code = data.get('code')
            if code not in (None, 0, '0', 200, '200'):
                msg = data.get('msg') or data.get('message') or data.get('error') or 'business error'
                raise RuntimeError(f'luwang code {code}: {msg}')
        payload = luwang_payload(data)
        count = payload_count(payload)
        msg = data.get('msg') if isinstance(data, dict) else ''
        return {
            'url': url,
            'status': resp.status,
            'meta': {
                'state': data_state_from_count(count),
                'count': count,
                'message': msg or '',
            },
            'data': compact_json(data),
            'source': 'live',
        }


def luwang_request(
    path: str,
    params: Optional[Dict[str, Any]] = None,
    token: str = '',
    base_url: str = '',
    demo_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch one luwang endpoint, honoring the WEATHER_MODE switch.

    - demo:  never touches network; returns demo sample or raises if missing.
    - live:  raises on any failure — caller catches into `errors` bundle.
    - auto:  no token -> demo samples; token present -> strict live.
             This avoids mixing real luwang data with demo samples during
             operator testing while still giving judges a no-token quick start.
    """
    mode = config.RUNTIME_STATE.get('weather_mode', config.WEATHER_MODE)
    effective_mode = 'live' if mode == 'auto' and token else mode
    if effective_mode == 'demo':
        result = _demo_result_for(demo_key or _default_demo_key(path), base_url + path)
        if result is None:
            raise RuntimeError(f'demo sample missing for {demo_key or path}')
        return result

    try:
        live = _live_luwang_request(path, params or {}, token, base_url)
        return live
    except Exception as live_err:
        if effective_mode == 'live':
            raise
        result = _demo_result_for(demo_key or _default_demo_key(path), base_url + path)
        if result is None:
            raise
        result['meta']['message'] = f'live failed ({live_err.__class__.__name__}), demo fallback'
        return result


def _default_demo_key(path: str) -> str:
    """Convert /api/road/rank/shortTerm → api_road_rank_short_term-style sample key."""
    slug = path.strip('/').replace('/', '_').replace('-', '_')
    # camelCase → snake_case for endpoint-derived names
    import re
    slug = re.sub(r'(?<!^)(?=[A-Z])', '_', slug).lower()
    return slug


def call_luwang_bundle(
    calls: List[Tuple[str, str, Dict[str, Any]]],
    params: Dict[str, Any],
    token: str,
    base_url: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    out: Dict[str, Any] = {}
    errors: Dict[str, Any] = {}
    for entry in calls:
        # Tuple layouts:
        #   (bundle_key, path, extra)                 -> demo_key derived from path
        #   (bundle_key, path, extra, demo_key)       -> explicit override
        if len(entry) == 4:
            key, path, extra, demo_key = entry  # type: ignore[misc]
        else:
            key, path, extra = entry  # type: ignore[misc]
            demo_key = _default_demo_key(path)
        merged = dict(params or {})
        merged.update(extra or {})
        try:
            out[key] = luwang_request(path, merged, token, base_url, demo_key=demo_key)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace') if hasattr(e, 'read') else ''
            errors[key] = {'status': e.code, 'error': body[:1000]}
        except Exception as e:
            errors[key] = {'error': str(e)}
    return out, errors


# ---------------------------------------------------------------------------
# Scenario bundles
# ---------------------------------------------------------------------------

def weather_summary(params: Dict[str, Any], token: str, base_url: str) -> Dict[str, Any]:
    params = normalize_weather_params(params, default_hours=2)
    calls = [
        ('publishLevelStats', '/api/weather/alert/publishLevelStats', {}),
        ('riskWarningLatest', '/api/weather/riskWarning/latest', {}),
        ('shortTermRank', '/api/road/rank/shortTerm', {'limit': params.get('limit', 10)}),
        ('affectedTop10', '/api/road/segment/affectedTop10', {'limit': params.get('limit', 10)}),
        ('riskZoneClass1', '/api/road/riskZone/class1', {}),
        ('riskZoneClass2', '/api/road/riskZone/class2', {}),
    ]
    data, errors = call_luwang_bundle(calls, params, token, base_url)
    return adapter_response(
        'weather_risk_summary', params, data, errors,
        [
            '用 shortTermRank + affectedTop10 挑出重点路段。',
            '用 riskZoneClass1/class2 说明连续降雨背景风险。',
            '用 riskWarningLatest 补充地震、河洪、地质、山洪信息。',
        ],
    )


def weather_short_term(params: Dict[str, Any], token: str, base_url: str) -> Dict[str, Any]:
    params = normalize_weather_params(params, default_hours=2)
    calls = [
        ('shortTermRank', '/api/road/rank/shortTerm', {'limit': params.get('limit', 20)}),
        ('affectedTop10Rain', '/api/road/segment/affectedTop10', {'type': 'rain', 'limit': params.get('limit', 10)}),
        ('affectedSegmentCounts', '/api/rainfallWarning/affectedSegmentCounts', {}),
        ('highImpactSegments', '/api/rainfallWarning/highImpactSegments',
         {'page': 1, 'pageSize': params.get('limit', 20), 'weatherType': 'heavy_rain'}),
        ('dataUpdateTimes', '/api/rainfallWarning/dataUpdateTimes', {}),
    ]
    data, errors = call_luwang_bundle(calls, params, token, base_url)
    return adapter_response('short_term_forecast', params, data, errors)


def weather_segment_risk(params: Dict[str, Any], token: str, base_url: str) -> Dict[str, Any]:
    params = normalize_weather_params(params, default_hours=2)
    calls = [
        ('riskSegments', '/api/overview/riskSegments', {}),
        ('hazardPoints', '/api/overview/hazardPoints', {}),
        ('affectedTop10', '/api/road/segment/affectedTop10', {'limit': params.get('limit', 20)}),
        ('continuousRainClass1', '/api/road/riskZone/class1', {}),
        ('continuousRainClass2', '/api/road/riskZone/class2', {}),
    ]
    data, errors = call_luwang_bundle(calls, params, token, base_url)
    return adapter_response('segment_risk', params, data, errors)


def weather_resources(params: Dict[str, Any], token: str, base_url: str) -> Dict[str, Any]:
    params = normalize_weather_params(params, default_hours=2)
    calls = [
        ('vehicleRescuePoints', '/api/overview/vehicleRescuePoints', {}),
        ('materialReserves', '/api/overview/materialReserves', {}),
        ('riskSegments', '/api/overview/riskSegments', {}),
        ('hazardPoints', '/api/overview/hazardPoints', {}),
    ]
    data, errors = call_luwang_bundle(calls, params, token, base_url)
    return adapter_response('emergency_resources', params, data, errors)


def weather_earthquake(params: Dict[str, Any], token: str, base_url: str) -> Dict[str, Any]:
    """Earthquake bundle: latest cenc report + segment/hazard context for damage assessment."""
    params = normalize_weather_params(params, default_hours=6)
    calls = [
        ('earthquakeLatest', '/api/weather/earthquake/latest', {}),
        ('riskSegments', '/api/overview/riskSegments', {}),
        ('hazardPoints', '/api/overview/hazardPoints', {}),
        ('vehicleRescuePoints', '/api/overview/vehicleRescuePoints', {}),
    ]
    data, errors = call_luwang_bundle(calls, params, token, base_url)
    return adapter_response(
        'earthquake_assessment', params, data, errors,
        [
            '按烈度 6/7/8 度圈定影响路段。',
            '优先派发桥梁、隧道、边坡三类隐患点巡查任务。',
            '匹配就近救援点做初步资源预置。',
        ],
    )


def weather_defense_advisory(params: Dict[str, Any], token: str, base_url: str) -> Dict[str, Any]:
    """Defense advisory: whole-country alert level breakdown + latest risk warnings."""
    params = normalize_weather_params(params, default_hours=24)
    calls = [
        ('publishLevelStats', '/api/weather/alert/publishLevelStats', {}),
        ('typeStats', '/api/weather/alert/typeStats', {}),
        ('provinceStats', '/api/weather/alert/provinceStats', {}),
        ('weeklyTrend', '/api/weather/alert/weeklyTrend', {}),
        ('riskWarningLatest', '/api/weather/riskWarning/latest', {}),
    ]
    data, errors = call_luwang_bundle(calls, params, token, base_url)
    return adapter_response(
        'defense_advisory', params, data, errors,
        [
            '按省份分级响应，红/橙/黄/蓝差异化提示。',
            '输出面向各省的防御提示文本。',
        ],
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

REPORT_TYPES = {
    'duty_brief': '公路气象风险值班简报',
    'emergency_response': '应急处置方案',
    'rescue_dispatch': '救援资源调配表',
    'material_dispatch': '物资调配建议',
    'earthquake_assessment': '地震灾损排查任务表',
    'defense_advisory': '公路气象预警防御提示',
    'risk_alert': '短临降雨风险预警',
    'incident_report': '隐患点排查报告',
    'daily_summary': '应急资源调配简报',
    'decision_memo': '防御决策备忘',
    'after_action': '地震灾损排查评估',
}


# ---------------------------------------------------------------------------
# Fact extraction — 从 summary bundle 里挖出可写进报告的具体数字/名单
# ---------------------------------------------------------------------------

def _iter_dicts(node):
    """深度遍历所有 dict 节点，用于 fact 抽取。"""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _iter_dicts(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_dicts(v)


def _first_list(node, keys):
    """在嵌套结构里找第一个匹配 keys 之一且值为 list 的字段。"""
    for d in _iter_dicts(node):
        for k in keys:
            v = d.get(k)
            if isinstance(v, list) and v:
                return v
    return []


def _num(v):
    try:
        if v in (None, ''):
            return 0.0
        return float(v)
    except Exception:
        return 0.0


def extract_data_facts(summary: Dict[str, Any]) -> Dict[str, Any]:
    """从 summary bundle 挖出可以直接写进报告的事实。

    典型字段：
      alert_total / alert_by_level      —— 预警总数 + 分级
      top_rain_rows                     —— 短临降雨 TOP N（含高速/桩号/mm）
      severe_row                        —— 最严重那条（rainfall 或 alertLevel 最高）
      rescue_points_total               —— 全网救援点数（从 vehicleRescuePoints 数）
      rescue_points_in_scope            —— 目标省的救援点数
      material_reserves_total           —— 全网物资库数
      hazard_points_total               —— 全网隐患点数
      hazard_points_in_scope            —— 目标省的隐患点数
      nearest_rescue                    —— 前端 smartQuery 派生进来的最近救援点
      severe_row_from_smart             —— 前端派生的最严重路段
    """
    facts: Dict[str, Any] = {}
    if not isinstance(summary, dict):
        return facts

    # 前端派生 (smartQuery.nearestRescue)
    nr = summary.get('nearestRescue') or {}
    if isinstance(nr, dict) and isinstance(nr.get('data'), dict):
        d = nr['data']
        if isinstance(d.get('nearest'), list):
            facts['nearest_rescue'] = d['nearest']
        if isinstance(d.get('severeRow'), dict):
            facts['severe_row_from_smart'] = d['severeRow']

    # 预警分级统计 (publishLevelStats)
    pls = _first_list(summary, ['publishLevelStats'])
    if pls:
        by_level = {'red': 0, 'orange': 0, 'yellow': 0, 'blue': 0}
        for item in pls:
            if not isinstance(item, dict):
                continue
            for k in ('redCount', 'orangeCount', 'yellowCount', 'blueCount'):
                by_level[k.replace('Count', '')] += int(_num(item.get(k)))
        facts['alert_by_level'] = by_level
        facts['alert_total'] = sum(by_level.values())

    # 短临降雨排行（shortTermRank / affectedTop10 / topRainfall / highImpactSegments）
    ranks = _first_list(summary, ['shortTermRank', 'affectedTop10Rain', 'affectedTop10', 'topRainfall', 'highImpactSegments'])
    top_rows = []
    for r in ranks[:10]:
        if not isinstance(r, dict):
            continue
        val = _num(r.get('forecast2HRainfall') or r.get('forecast1HRainfall') or r.get('maxRainfall') or r.get('history1HRainfall') or r.get('rainfall'))
        top_rows.append({
            'highway': r.get('highwayName') or r.get('routeName') or r.get('roadName') or r.get('lxmc') or '',
            'province': r.get('provinceName') or r.get('province') or '',
            'segment': (r.get('segmentLabel') or r.get('stakeRange')
                        or (str(r.get('startStake') or '') + '-' + str(r.get('endStake') or '') if r.get('startStake') else '')),
            'rainfall_mm': val,
            'level': r.get('riskLevel') or r.get('alertLevelName') or r.get('levelName') or '',
        })
    facts['top_rain_rows'] = top_rows
    if top_rows:
        facts['severe_row'] = max(top_rows, key=lambda x: x['rainfall_mm'])
        facts['top_rain_max_mm'] = facts['severe_row']['rainfall_mm']

    # 资源类计数（vehicleRescuePoints / materialReserves / hazardPoints）
    for src_key in ('vehicleRescuePoints', 'materialReserves', 'hazardPoints'):
        lst = _first_list(summary, [src_key])
        if lst:
            facts[src_key + '_total'] = len(lst)
            # 按 params.provinceName 过滤
            prov = str((summary.get('query_meta') or {}).get('province') or '').replace('省', '').replace('市', '')
            if prov:
                facts[src_key + '_in_scope'] = sum(
                    1 for x in lst if isinstance(x, dict) and prov in str(x.get('provinceName') or x.get('province') or '')
                )

    return facts


# ---------------------------------------------------------------------------
# Section builders — 根据 facts + report_type 生成有针对性的文字段落
# ---------------------------------------------------------------------------

def _fmt_alert_line(by_level: Dict[str, int]) -> str:
    parts = []
    for k, cn in [('red', '红色'), ('orange', '橙色'), ('yellow', '黄色'), ('blue', '蓝色')]:
        if by_level.get(k):
            parts.append(f'{cn} {by_level[k]} 条')
    return '、'.join(parts) if parts else '暂无分级预警'


def _fmt_severe(row: Dict[str, Any]) -> str:
    if not row:
        return '（无可挖出的最严重路段）'
    parts = []
    if row.get('highway'):
        parts.append(str(row['highway']))
    if row.get('segment'):
        parts.append(str(row['segment']))
    if row.get('rainfall_mm') or row.get('rainfall'):
        parts.append(f'{row.get("rainfall_mm") or row.get("rainfall")} mm')
    if row.get('level'):
        parts.append(str(row['level']))
    if row.get('province'):
        parts.append('（' + str(row['province']) + '）')
    return ' '.join(parts)


def _fmt_nearest(items) -> str:
    if not items:
        return '（未挖到最近救援点数据）'
    lines = []
    for i, p in enumerate(items[:5], 1):
        lines.append(f'  {i}. {p.get("unitName") or "救援点"}（{p.get("provinceName") or ""}） 距离约 {p.get("distance_km", "?")} km')
    return '\n'.join(lines)


def _build_common_sources(quality: Dict[str, List[str]], mode: str, metrics: Dict[str, str]) -> str:
    ok = '、'.join(quality.get('success') or []) or '无'
    empty = '、'.join(quality.get('empty') or []) or '无'
    failed = '、'.join(quality.get('failed') or []) or '无'
    return (
        f'成功接口：{ok}。\n空数据接口：{empty}。\n失败接口：{failed}。\n'
        f'内部数据源：{metrics["internal_sources"]}。\n'
        f'外部数据源：{metrics["external_sources"]}。\n'
        f'数据由本地 WeatherAdapter 代理聚合 luwang 后端接口生成（当前模式：{mode}）。'
    )


def _build_sections_by_type(report_type: str, facts: Dict[str, Any], params: Dict[str, Any],
                            tw: Dict[str, Any], quality: Dict[str, List[str]],
                            metrics: Dict[str, str], mode: str) -> List[Dict[str, str]]:
    """按 report_type 走不同 builder；每个 builder 都返回 5 段（态势/风险/建议/来源/不确定）。"""
    prov = params.get('provinceName') or params.get('province') or '目标区域'
    hours = params.get('hours', 2)
    win = f'{tw.get("startText")} — {tw.get("endText")}'

    # 通用摘要
    alert_line = _fmt_alert_line(facts.get('alert_by_level') or {})
    severe_row = facts.get('severe_row_from_smart') or facts.get('severe_row')
    top_rows = facts.get('top_rain_rows') or []

    # ============ resource / daily_summary（应急资源调配） ============
    if report_type in ('daily_summary', 'rescue_dispatch', 'material_dispatch', 'emergency_response'):
        rescue_total = facts.get('vehicleRescuePoints_total')
        rescue_scope = facts.get('vehicleRescuePoints_in_scope')
        material_total = facts.get('materialReserves_total')
        hazard_total = facts.get('hazardPoints_total')
        hazard_scope = facts.get('hazardPoints_in_scope')
        nearest = facts.get('nearest_rescue') or []

        summary_bits = [f'时间窗口 {win}，聚焦 {prov}。']
        if rescue_scope is not None and rescue_total is not None:
            summary_bits.append(f'全网救援点 {rescue_total} 个，其中 {prov} 落点约 {rescue_scope} 个。')
        elif rescue_total is not None:
            summary_bits.append(f'全网救援点 {rescue_total} 个（未按省份细分）。')
        if material_total is not None:
            summary_bits.append(f'全网国家物资储备中心 {material_total} 个。')
        if hazard_scope is not None:
            summary_bits.append(f'{prov} 隐患点 {hazard_scope} 个（全网 {hazard_total}）。')
        if severe_row:
            summary_bits.append('当前最严重路段：' + _fmt_severe(severe_row) + '。')
        summary_text = ' '.join(summary_bits)

        risk_text_lines = []
        if nearest:
            risk_text_lines.append('已锁定"最严重路段"周边最近 {} 个救援点：'.format(len(nearest)))
            risk_text_lines.append(_fmt_nearest(nearest))
        elif rescue_scope == 0:
            risk_text_lines.append(f'{prov} 区域接口未返回救援点，需人工核实 luwang 数据库是否录入该省应急资源。')
        elif rescue_total == 0:
            risk_text_lines.append('全网救援点接口空数据，建议检查 /api/overview/vehicleRescuePoints 是否正常。')
        else:
            risk_text_lines.append(f'当前区域已铺设 {rescue_scope or rescue_total or 0} 个救援点，重点关注最严重路段（见上方）沿线。')
        if hazard_scope:
            risk_text_lines.append(f'另有 {hazard_scope} 个隐患点分布在 {prov}，需并行巡查。')
        risk_text = '\n'.join(risk_text_lines)

        action_lines = []
        if nearest:
            top = nearest[0]
            action_lines.append(
                f'一、指定"{top.get("unitName")}"为主责单位（距最严重路段约 {top.get("distance_km", "?")} km），另派 2 备勤队伍前置到二三名点位。')
        if severe_row and severe_row.get('rainfall_mm', severe_row.get('rainfall', 0)) >= 30:
            action_lines.append('二、最严重路段短临降雨已达强降雨阈值，建议在该桩号提前布设限速/警示牌，必要时启动分级管控。')
        if material_total:
            action_lines.append(f'三、从最近 1-2 个国家物资库预置沙袋、警示灯、破胎板等应急物资，直调时效 < 4h。')
        if hazard_scope:
            action_lines.append(f'四、对 {prov} 的 {hazard_scope} 个隐患点开展一次专项复查，重点排查桥梁下方、陡坡边坡、易积水匝道。')
        if not action_lines:
            action_lines.append('接口数据不足以生成具体调配方案，建议值班人员先核对接口状态再进一步研判。')
        action_text = '\n'.join(action_lines)

        return [
            {'title': '一、当前态势', 'content': summary_text},
            {'title': '二、资源匹配', 'content': risk_text},
            {'title': '三、调配建议', 'content': action_text},
            {'title': '四、数据来源', 'content': _build_common_sources(quality, mode, metrics)},
            {'title': '五、不确定点', 'content': '救援点/物资库/隐患点接口均为全国无参接口，按 provinceName 过滤后可能因数据未录入本省而落空；调度前请与省中心值班室电话复核。'},
        ]

    # ============ risk_alert / rainfall（短临降雨） ============
    if report_type == 'risk_alert':
        summary_bits = [f'{prov} 未来 {hours} 小时短临降雨研判（{win}）。']
        if facts.get('top_rain_max_mm'):
            summary_bits.append(f'当前最大 2 小时预报 {facts["top_rain_max_mm"]} mm，落点：{_fmt_severe(severe_row)}。')
        if alert_line != '暂无分级预警':
            summary_bits.append(f'现行预警：{alert_line}。')
        summary_text = ' '.join(summary_bits)

        risk_lines = []
        if top_rows:
            risk_lines.append(f'受降雨影响的重点路段 TOP {min(len(top_rows), 5)}：')
            for i, r in enumerate(top_rows[:5], 1):
                risk_lines.append(f'  {i}. {r["highway"]} {r["segment"]} — 预报 {r["rainfall_mm"]} mm（{r["province"]}）')
        else:
            risk_lines.append('本次拉取未挖到可表格化的重点路段，可能是接口空数据或省份过滤过严。')
        risk_text = '\n'.join(risk_lines)

        max_mm = facts.get('top_rain_max_mm') or 0
        if max_mm >= 50:
            level_hint = '暴雨级（≥50 mm），建议启动Ⅱ级响应，重点路段限速 60 km/h 并布置警示。'
        elif max_mm >= 30:
            level_hint = '强降雨级（30-50 mm），建议启动Ⅲ级响应，桥梁 / 山区路段加强巡查。'
        elif max_mm >= 10:
            level_hint = '中雨级（10-30 mm），建议维持常态化值守 + 山区路段动态观察。'
        else:
            level_hint = '雨量偏小，维持常规值班即可，重点关注雨强突增。'
        action_text = (
            f'一、按最大预报 {max_mm} mm 判定：{level_hint}\n'
            f'二、优先向"重点路段 TOP"沿线电子情报板推送短临预警文字。\n'
            f'三、跨市界路段与上下游高速联合值守，避免管控信息断层。\n'
            f'四、如出现新增红/橙色预警，自动升级到应急处置流程。'
        )
        return [
            {'title': '一、态势摘要', 'content': summary_text},
            {'title': '二、重点路段', 'content': risk_text},
            {'title': '三、处置建议', 'content': action_text},
            {'title': '四、数据来源', 'content': _build_common_sources(quality, mode, metrics)},
            {'title': '五、不确定点', 'content': '短临预报每 5 min 更新一次，桩号级降雨落区实际以雷达最新拼图为准；桥梁隧道等特殊结构应额外考虑历史积水/结冰纪录。'},
        ]

    # ============ duty_brief（预警值班简报） ============
    if report_type == 'duty_brief':
        summary_bits = [f'{prov} · {win} · 预警值班态势。']
        if facts.get('alert_total'):
            summary_bits.append(f'现行公路气象预警共 {facts["alert_total"]} 条（{alert_line}）。')
        if severe_row:
            summary_bits.append('最严重路段：' + _fmt_severe(severe_row) + '。')
        if not summary_bits[1:]:
            summary_bits.append('接口未返回明确的预警数字，建议人工在 luwang 大屏上复核。')
        summary_text = ' '.join(summary_bits)

        risk_lines = []
        if top_rows:
            risk_lines.append(f'受影响 TOP {min(len(top_rows), 5)} 路段：')
            for i, r in enumerate(top_rows[:5], 1):
                risk_lines.append(f'  {i}. {r["highway"]} {r["segment"]} — {r["rainfall_mm"]} mm / {r["level"] or "未分级"}（{r["province"]}）')
        else:
            risk_lines.append('本次拉取未能挖出显式路段清单。')
        risk_text = '\n'.join(risk_lines)

        action_text = (
            '一、按现行预警分级下发桩号级临灾提示。\n'
            '二、重点路段（见上方）配套动态巡查频次 + 电子情报板。\n'
            '三、跨部门信息同步：气象/交管/养护/救援四方每 30 分钟共享一次态势。\n'
            '四、发现新增红/橙色预警需 15 分钟内向省交通厅报告。'
        )
        return [
            {'title': '一、值班摘要', 'content': summary_text},
            {'title': '二、重点路段', 'content': risk_text},
            {'title': '三、值班动作', 'content': action_text},
            {'title': '四、数据来源', 'content': _build_common_sources(quality, mode, metrics)},
            {'title': '五、不确定点', 'content': '预警接口 5 min 刷新一次，桩号级信息以最新一版为准。若失败接口非空，请人工复核平台 token 或后端服务。'},
        ]

    # ============ incident_report（隐患） ============
    if report_type == 'incident_report':
        hazard_scope = facts.get('hazardPoints_in_scope')
        hazard_total = facts.get('hazardPoints_total')
        summary_text = f'{prov} 隐患点排查（{win}）。当前区域隐患点 {hazard_scope or 0} 个（全网 {hazard_total or 0}）。'
        risk_text = '优先排查滑坡、边坡失稳、桥梁下沉、路面塌陷四类；结合最严重路段：' + _fmt_severe(severe_row)
        action_text = (
            '一、当日出勤班组按隐患点距离升序访检，逐点核对现场状况 vs 系统记录。\n'
            '二、发现新增隐患的立即打卡上报，附现场照片 + 桩号 + 处置建议。\n'
            '三、雨中作业注意人身安全，禁止单人上边坡；夜间需带反光衣 + 警示灯。'
        )
        return [
            {'title': '一、排查目标', 'content': summary_text},
            {'title': '二、重点排查方向', 'content': risk_text},
            {'title': '三、作业规程', 'content': action_text},
            {'title': '四、数据来源', 'content': _build_common_sources(quality, mode, metrics)},
            {'title': '五、不确定点', 'content': '/api/overview/hazardPoints 为全国接口，某些新增隐患可能未及时录入，现场发现新增点后请及时补录。'},
        ]

    # ============ decision_memo（防御建议） ============
    if report_type == 'decision_memo':
        summary_text = f'{prov} · {win} · 防御建议决策备忘。现行预警：{alert_line}。'
        risk_text = ('本次防御建议基于三条线索：\n'
                     f'  · 分级预警条数：{alert_line}\n'
                     f'  · 最严重路段：{_fmt_severe(severe_row)}\n'
                     f'  · 重点路段清单：共 {len(top_rows)} 条纳入统计')
        action_text = (
            '一、按预警等级差异化下发防御短信（红→值班经理、橙→路段队长、黄→巡查员）。\n'
            '二、协调气象部门滚动预报，每 30 分钟评估一次预警升降级。\n'
            '三、启动跨省"预置跟着风险走"机制，将备勤车辆预置到最严重路段就近点位。\n'
            '四、若下一时段出现新增红色预警，自动切换到应急处置流程并召开视频调度会。'
        )
        return [
            {'title': '一、决策摘要', 'content': summary_text},
            {'title': '二、判据梳理', 'content': risk_text},
            {'title': '三、防御建议', 'content': action_text},
            {'title': '四、数据来源', 'content': _build_common_sources(quality, mode, metrics)},
            {'title': '五、不确定点', 'content': '本备忘为智能体基于当前接口数据的初步建议，正式下发需值班领导签发并留档。'},
        ]

    # ============ after_action / earthquake_assessment（地震灾损排查） ============
    if report_type in ('after_action', 'earthquake_assessment'):
        rescue_scope = facts.get('vehicleRescuePoints_in_scope') or 0
        hazard_scope = facts.get('hazardPoints_in_scope') or 0
        summary_text = f'{prov} 地震灾损排查（{win}）。区域内 {rescue_scope} 个救援点、{hazard_scope} 个已知隐患点。'
        risk_text = ('按烈度圈 6/7/8 度差异化处置：\n'
                     '  · 8 度：桥梁、隧道、边坡全数临时封闭 + 排查\n'
                     '  · 7 度：重点结构物 24 小时内完成初检\n'
                     '  · 6 度：路面沉降、护栏变形按需巡查\n'
                     f'最严重路段结合气象叠加：{_fmt_severe(severe_row)}')
        action_text = (
            '一、启用震区最近救援点，前置抢通装备、水/电应急设备。\n'
            '二、桥梁隧道优先派专业检测队，按"外观-构件-支座-伸缩缝"四步流程。\n'
            '三、次生灾害警戒：山洪、崩塌、堰塞湖24-72h监控。\n'
            '四、每 4 小时向部路网中心报告一次排查进度。'
        )
        return [
            {'title': '一、震损态势', 'content': summary_text},
            {'title': '二、烈度圈分级处置', 'content': risk_text},
            {'title': '三、排查作业', 'content': action_text},
            {'title': '四、数据来源', 'content': _build_common_sources(quality, mode, metrics)},
            {'title': '五、不确定点', 'content': '烈度圈由 CENC 快速报告初判，实际现场破坏程度需现场专业队复核，本报告不能替代专业震损评估。'},
        ]

    # ============ 默认兜底 ============
    return [
        {'title': '一、态势摘要', 'content': f'{prov} · {win}。' + (severe_row and '最严重路段：' + _fmt_severe(severe_row) + '。' or '当前接口未挖出重点路段。')},
        {'title': '二、重点风险', 'content': '\n'.join(f'  {i}. {r["highway"]} {r["segment"]} — {r["rainfall_mm"]} mm' for i, r in enumerate(top_rows[:5], 1)) or '无'},
        {'title': '三、处置建议', 'content': '结合成功返回的数据开展重点路段巡查、临灾预警提示、交通管控研判、救援资源预置和物资调拨准备。'},
        {'title': '四、数据来源', 'content': _build_common_sources(quality, mode, metrics)},
        {'title': '五、不确定点', 'content': '短临预报、地图图层、外部预警和路段数据可能存在延迟、缺测或接口异常；涉及管制、调度和应急资源调用的建议均需值班人员确认。'},
    ]


def report_draft(body: Dict[str, Any], token: str, base_url: str) -> Dict[str, Any]:
    """Generate a report draft.

    body:
        params        - normalized weather params (province, hours, ...)
        summary       - optional pre-fetched bundle; if absent we fetch weather_summary
        title         - override title
        report_type   - one of REPORT_TYPES keys (default duty_brief)
        facts         - optional pre-extracted facts (前端 smartQuery 可直接传进来)
    """
    params = body.get('params') if isinstance(body.get('params'), dict) else {}
    params = normalize_weather_params(params, default_hours=2)
    report_type = body.get('report_type') or 'duty_brief'
    summary = body.get('summary') or weather_summary(params, token, base_url)
    title = body.get('title') or REPORT_TYPES.get(report_type, REPORT_TYPES['duty_brief'])
    tw = time_window_meta(params)
    quality = collect_quality_from_summary(summary)
    mode = config.RUNTIME_STATE.get('weather_mode', config.WEATHER_MODE)

    metrics = {
        'spatial_resolution': '1km',
        'update_frequency': '5min',
        'forecast_horizon': f'{params.get("hours", 2)}h',
        'internal_sources': '公路基础信息、承灾体普查、汛冬风险隐患排查、车辆救援、物资储备、灾毁阻断（共6类）',
        'external_sources': '气象数值预报+雷达拼图、地理信息、全国地震预警、山洪地质灾害预警（共4类）',
    }

    # 提取事实（优先用前端传入的 facts，否则自己算）
    facts = body.get('facts') if isinstance(body.get('facts'), dict) else {}
    auto_facts = extract_data_facts(summary)
    for k, v in auto_facts.items():
        facts.setdefault(k, v)

    sections = _build_sections_by_type(report_type, facts, params, tw, quality, metrics, mode)

    return {
        'title': title,
        'report_type': report_type,
        'phase': SCENARIO_PHASE.get(report_type, 'review'),
        'mode': mode,
        'generated_at': format_local_ts(int(time.time())),
        'time_window': tw,
        'metrics': metrics,
        'data_quality': quality,
        'facts': facts,
        'sections': sections,
        'source_summary': summary,
    }
