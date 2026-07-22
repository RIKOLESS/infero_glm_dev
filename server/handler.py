"""HTTP request handler wiring all server endpoints.

Routes:
    GET  /api/weather-adapter/config           - inspect base_url + token flag
    GET  /api/weather-adapter/summary          - aggregated risk overview
    GET  /api/weather-adapter/short-term       - short-term rainfall bundle
    GET  /api/weather-adapter/segment-risk     - risk segments + hazard points
    GET  /api/weather-adapter/resources        - rescue + material + segments
    GET  /api/weather-adapter/earthquake       - cenc + segment/hazard context
    GET  /api/weather-adapter/defense          - alert level breakdown
    POST /api/weather-adapter/config           - set base_url/token in memory
    POST /api/weather-adapter/report-draft     - build a report from a bundle
    GET  /api/kb/list                          - list knowledge base docs
    GET  /api/kb/read?name=...                 - read one doc
    GET  /api/kb/search?q=...                  - substring search
    GET  /api/local-hub/list                   - browse local skills
    GET  /api/local-hub/skill/:name            - read one local skill
    POST /api/local-hub/submit                 - upsert a local skill
    DEL  /api/local-hub/skill/:name            - delete a local skill
    POST /api/chat | /api/vision               - GLM/Vision upstream proxy
    OPTIONS *                                  - CORS preflight
    GET  everything else                       - static file (SimpleHTTPRequestHandler)
"""
from __future__ import annotations

import http.server
import urllib.parse

from . import config, glm_proxy, knowledge_base, skill_hub, weather_adapter
from .http_utils import parse_json_body, send_json


class GLMProxyHandler(http.server.SimpleHTTPRequestHandler):

    # ------------------------------------------------------------------ CORS

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Luwang-Token')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    # ------------------------------------------------------------------ GET

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith('/api/weather-adapter/'):
            return self._handle_weather_adapter_get(parsed)

        if path == '/api/kb/list':
            return send_json(self, 200, knowledge_base.list_docs())

        if path == '/api/kb/read':
            params = urllib.parse.parse_qs(parsed.query)
            name = params.get('name', [''])[0]
            doc = knowledge_base.read_doc(name)
            if doc is None:
                return send_json(self, 404, {'error': 'doc not found', 'name': name})
            return send_json(self, 200, doc)

        if path == '/api/kb/search':
            params = urllib.parse.parse_qs(parsed.query)
            q = params.get('q', [''])[0]
            try:
                limit = max(1, min(50, int(params.get('limit', ['20'])[0])))
            except ValueError:
                limit = 20
            return send_json(self, 200, {'query': q, 'hits': knowledge_base.search_docs(q, limit)})

        if path == '/api/local-hub/list':
            return self._handle_local_hub_list(parsed)

        if path.startswith('/api/local-hub/skill/'):
            return self._handle_local_hub_read(parsed)

        return super().do_GET()

    def _handle_weather_adapter_get(self, parsed):
        params = {k: v[-1] if len(v) == 1 else v
                  for k, v in urllib.parse.parse_qs(parsed.query).items()}
        token = weather_adapter.get_luwang_token(self)
        base_url = weather_adapter.get_luwang_base()
        endpoint = parsed.path.rsplit('/', 1)[-1]

        try:
            if endpoint == 'config':
                return send_json(self, 200, {
                    'base_url': base_url,
                    'has_token': bool(token),
                    'mode': config.RUNTIME_STATE.get('weather_mode', config.WEATHER_MODE),
                    'hint': 'Set LUWANG_TOKEN/LUWANG_BASE_URL/WEATHER_MODE or POST /api/weather-adapter/config.',
                })
            if endpoint == 'summary':
                return send_json(self, 200, weather_adapter.weather_summary(params, token, base_url))
            if endpoint == 'short-term':
                return send_json(self, 200, weather_adapter.weather_short_term(params, token, base_url))
            if endpoint == 'segment-risk':
                return send_json(self, 200, weather_adapter.weather_segment_risk(params, token, base_url))
            if endpoint == 'resources':
                return send_json(self, 200, weather_adapter.weather_resources(params, token, base_url))
            if endpoint == 'earthquake':
                return send_json(self, 200, weather_adapter.weather_earthquake(params, token, base_url))
            if endpoint == 'defense':
                return send_json(self, 200, weather_adapter.weather_defense_advisory(params, token, base_url))
            return send_json(self, 404, {'error': 'unknown weather adapter endpoint', 'endpoint': endpoint})
        except Exception as e:
            return send_json(self, 500, {'error': str(e), 'endpoint': endpoint})

    def _handle_local_hub_list(self, parsed):
        params = urllib.parse.parse_qs(parsed.query)
        q = params.get('q', [''])[0]
        try:
            limit = max(1, min(100, int(params.get('limit', ['20'])[0])))
            offset = max(0, int(params.get('offset', ['0'])[0]))
        except ValueError:
            limit, offset = 20, 0
        return send_json(self, 200, {'skills': skill_hub.list_local_skills(q, limit, offset), 'local': True})

    def _handle_local_hub_read(self, parsed):
        raw = parsed.path.rsplit('/', 1)[-1]
        try:
            skill = skill_hub.read_local_skill(raw)
        except ValueError as e:
            return send_json(self, 400, {'error': str(e)})
        if not skill:
            return send_json(self, 404, {'error': 'local skill not found', 'name': urllib.parse.unquote(raw)})
        return send_json(self, 200, skill)

    # ------------------------------------------------------------------ POST

    def do_POST(self):
        if self.path == '/api/weather-adapter/config':
            body = parse_json_body(self)
            base_url = weather_adapter.get_luwang_base(body)
            token = weather_adapter.get_luwang_token(self, body)
            config.LUWANG_ADAPTER_STATE['base_url'] = base_url
            if token:
                config.LUWANG_ADAPTER_STATE['token'] = token
            # Allow runtime mode override via POST body
            new_mode = str(body.get('mode', '')).strip().lower()
            if new_mode in ('auto', 'live', 'demo'):
                config.RUNTIME_STATE['weather_mode'] = new_mode
            return send_json(self, 200, {
                'ok': True,
                'base_url': base_url,
                'has_token': bool(config.LUWANG_ADAPTER_STATE.get('token')),
                'mode': config.RUNTIME_STATE.get('weather_mode', config.WEATHER_MODE),
            })

        if self.path == '/api/weather-adapter/report-draft':
            body = parse_json_body(self)
            token = weather_adapter.get_luwang_token(self, body)
            base_url = weather_adapter.get_luwang_base(body)
            try:
                return send_json(self, 200, weather_adapter.report_draft(body, token, base_url))
            except Exception as e:
                return send_json(self, 500, {'error': str(e)})

        if self.path == '/api/local-hub/submit':
            body = parse_json_body(self)
            try:
                skill = skill_hub.normalize_local_skill(body)
                skill_hub.save_local_skill(skill)
                return send_json(self, 200, {
                    'decision': 'approved',
                    'severity': 'local',
                    'score': 0,
                    'review': 'Saved to local hub.',
                    'skill': skill,
                })
            except Exception as e:
                return send_json(self, 400, {'error': str(e)})

        if self.path in ('/api/chat', '/api/vision'):
            return glm_proxy.handle_chat_or_vision(self, self.path)

        self.send_response(404)
        self.end_headers()

    # ------------------------------------------------------------------ DELETE

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith('/api/local-hub/skill/'):
            raw = parsed.path.rsplit('/', 1)[-1]
            try:
                skill_hub.delete_local_skill(raw)
                return send_json(self, 200, {'ok': True})
            except Exception as e:
                return send_json(self, 400, {'error': str(e)})
        self.send_response(404)
        self.end_headers()
