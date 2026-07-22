"""Static configuration + mutable adapter state shared by server modules.

Everything env-driven lives here so downstream modules can be imported without
touching os.environ. Sensitive credentials (GLM_API_KEY, LUWANG_TOKEN) are
read once at import time and never logged in full.
"""
from __future__ import annotations

import os
from typing import Dict, Set


REPO_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_HUB_DIR: str = os.path.join(REPO_ROOT, 'local_hub', 'skills')
DOCS_DIR: str = os.path.join(REPO_ROOT, 'docs')
SAMPLES_DIR: str = os.path.join(REPO_ROOT, 'data', 'samples')

PORT: int = int(os.environ.get('INFERO_PORT', '8000'))

UPSTREAM_CHAT_COMPLETIONS: str = os.environ.get(
    'GLM_UPSTREAM',
    'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions',
)
DEFAULT_MAIN_MODEL: str = os.environ.get('GLM_MODEL', 'glm-5.2')
VISION_MODEL: str = os.environ.get('VISION_MODEL', 'qwen3.7-plus')

LUWANG_DEFAULT_BASE: str = os.environ.get(
    'LUWANG_BASE_URL', 'http://118.121.196.98:8888'
).rstrip('/')

LUWANG_ADAPTER_STATE: Dict[str, str] = {
    'base_url': LUWANG_DEFAULT_BASE,
    'token': os.environ.get('LUWANG_TOKEN', '').strip(),
}

# WeatherAdapter operating mode:
#   auto - try live luwang, fall back to demo samples on any failure (default)
#   live - only real luwang API; failures propagate as errors
#   demo - never call luwang, always return preloaded sample data
_WEATHER_MODE_RAW = os.environ.get('WEATHER_MODE', 'auto').strip().lower()
WEATHER_MODE: str = _WEATHER_MODE_RAW if _WEATHER_MODE_RAW in ('auto', 'live', 'demo') else 'auto'

# Runtime-mutable state (can be changed via POST /api/weather-adapter/config)
RUNTIME_STATE: Dict[str, str] = {
    'weather_mode': WEATHER_MODE,
}

# Chinese province -> adcode. Covers rain/flood/earthquake-prone provinces that
# regularly appear in traffic-weather scenarios.
PROVINCE_CODE_MAP: Dict[str, str] = {
    '四川': '510000', '四川省': '510000',
    '云南': '530000', '云南省': '530000',
    '贵州': '520000', '贵州省': '520000',
    '广西': '450000', '广西壮族自治区': '450000',
    '广东': '440000', '广东省': '440000',
    '重庆': '500000', '重庆市': '500000',
    '湖南': '430000', '湖南省': '430000',
    '湖北': '420000', '湖北省': '420000',
    '江西': '360000', '江西省': '360000',
    '福建': '350000', '福建省': '350000',
    '浙江': '330000', '浙江省': '330000',
    '海南': '460000', '海南省': '460000',
    '西藏': '540000', '西藏自治区': '540000',
    '甘肃': '620000', '甘肃省': '620000',
    '青海': '630000', '青海省': '630000',
}

OPENAI_COMPAT_KEYS: Set[str] = {
    'model', 'messages', 'stream', 'stream_options', 'max_tokens',
    'temperature', 'top_p', 'stop', 'tools', 'tool_choice',
    'response_format', 'thinking', 'reasoning_effort',
}


def normalize_model_name(name: str) -> str:
    """Force GLM as the main brain unless caller explicitly picks another model.

    Legacy frontend snapshots sometimes send `gemini-*`; those get rewritten to
    the configured GLM default so a stale IndexedDB record cannot silently swap
    the brain.
    """
    model = str(name or '').strip()
    if not model or model.lower().startswith('gemini'):
        return DEFAULT_MAIN_MODEL
    return model


def get_default_auth_header() -> str:
    """Return an `Authorization` header value for the upstream GLM endpoint.

    Priority: `GLM_AUTH_HEADER` (raw, may include `Bearer `) > `GLM_API_KEY`
    (auto-prefixed with `Bearer `). Empty string means no credentials configured;
    the proxy will 401 in that case.
    """
    raw = os.environ.get('GLM_AUTH_HEADER', '').strip()
    if raw:
        return raw
    api_key = os.environ.get('GLM_API_KEY', '').strip()
    if api_key:
        return api_key if api_key.lower().startswith('bearer ') else f'Bearer {api_key}'
    return ''
