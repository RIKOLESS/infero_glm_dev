"""Demo Mode sample data loader.

When `WEATHER_MODE=demo` or a live luwang call fails under `auto`, the
WeatherAdapter falls back to on-disk sample JSON so the whole product path
(query -> report -> big screen) works without a token or backend network.

Samples live in `data/samples/*.json` and mirror the real luwang response
shape 1:1 so the frontend and main-brain cannot tell live and demo apart.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from . import config


_CACHE: Dict[str, Any] = {}


def _sample_path(name: str) -> str:
    safe = ''.join(ch for ch in name if ch.isalnum() or ch in ('_', '-'))
    return os.path.join(config.SAMPLES_DIR, f'{safe}.json')


def load_sample(name: str) -> Optional[Any]:
    """Load a named sample. Returns `None` when the file is missing."""
    if not name:
        return None
    if name in _CACHE:
        return _CACHE[name]
    path = _sample_path(name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _CACHE[name] = data
        return data
    except Exception:
        return None


def list_samples() -> Dict[str, str]:
    """Return `{sample_name: relative_path}` for every JSON file in the samples dir."""
    if not os.path.isdir(config.SAMPLES_DIR):
        return {}
    out: Dict[str, str] = {}
    for fn in sorted(os.listdir(config.SAMPLES_DIR)):
        if fn.endswith('.json'):
            key = fn[:-5]
            out[key] = os.path.relpath(os.path.join(config.SAMPLES_DIR, fn), config.REPO_ROOT)
    return out


def clear_cache() -> None:
    _CACHE.clear()
