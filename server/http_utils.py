"""Shared HTTP helpers used by the request handler."""
from __future__ import annotations

import json
from typing import Any, Dict


def parse_json_body(handler) -> Dict[str, Any]:
    """Read and parse the JSON body of an HTTP request. Empty/invalid → `{}`."""
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
    except (TypeError, ValueError):
        return {}
    if content_length <= 0:
        return {}
    try:
        raw = handler.rfile.read(content_length)
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return {}


def send_json(handler, status: int, data: Any) -> None:
    """Serialize `data` as JSON and write it as an HTTP response body."""
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
