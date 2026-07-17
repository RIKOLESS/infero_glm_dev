import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import ssl
import re
import os

PORT = 8000
UPSTREAM_CHAT_COMPLETIONS = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions'
DEFAULT_MAIN_MODEL = 'glm-5.2'
VISION_MODEL = 'qwen3.7-plus'
LOCAL_HUB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_hub', 'skills')
BUILTIN_LOCAL_SKILLS = {
    'infero_receptionist': {
        'name': 'infero_receptionist',
        'instruction': (
            '# infero_receptionist\n\n'
            'You are the local receptionist for this db build. On first boot, help the Being orient itself and render a concise welcome panel on the right-side living UI.\n\n'
            'Important local facts:\n'
            '- This build uses a local Skill Hub at `/api/local-hub`.\n'
            '- The local Hub may intentionally start empty. This is normal, not a failure.\n'
            '- Do not try to reach the public Infero Hub unless the human explicitly asks.\n'
            '- Users can create, enable, disable, delete, upload, and install skills locally through the existing skill mechanism.\n\n'
            'Suggested first action: draw a welcome card in `#html-div` that says db is online, GLM-5.2 is the main brain, the local Hub is available but empty, and the human can give a task or create skills. Keep it brief and avoid repeatedly debugging Hub availability.'
        ),
        'code': {
            'js': """
window.renderLocalReceptionist = function() {
    const div = document.getElementById('html-div');
    if (!div) return false;
    div.innerHTML = `
      <div style="position:absolute;inset:24px;display:flex;align-items:center;justify-content:center;pointer-events:none;font-family:system-ui,-apple-system,Segoe UI,sans-serif;">
        <div style="max-width:620px;padding:28px 32px;border:1px solid rgba(0,212,170,.45);border-radius:18px;background:rgba(2,12,18,.72);box-shadow:0 20px 80px rgba(0,212,170,.12);backdrop-filter:blur(12px);color:#d7fff5;line-height:1.65;pointer-events:auto;">
          <div style="font-family:monospace;letter-spacing:.35em;color:#00d4aa;font-size:12px;margin-bottom:12px;">INFERO DB</div>
          <h2 style="margin:0 0 10px;font-size:28px;color:#fff;">本地 db 已启动</h2>
          <p style="margin:0 0 14px;color:#a9c9c0;">GLM-5.2 是主脑；视觉由本地代理路由到视觉副脑。Skill Hub 当前为本地模式，可为空，这是正常状态。</p>
          <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:18px;font-size:13px;">
            <div style="border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:10px;background:rgba(255,255,255,.04);"><b>对话</b><br><span style="color:#8aa">直接给任务</span></div>
            <div style="border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:10px;background:rgba(255,255,255,.04);"><b>视觉</b><br><span style="color:#8aa">粘贴图片分析</span></div>
            <div style="border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:10px;background:rgba(255,255,255,.04);"><b>Skills</b><br><span style="color:#8aa">本地创作/安装</span></div>
          </div>
        </div>
      </div>`;
    return true;
};
window.renderLocalReceptionist();
"""
        },
        'code_readme': 'Call `window.renderLocalReceptionist()` to render the local welcome card in #html-div.',
        'contact': '',
        'note': 'Built into the local db hub so first-run reception works without public Hub access.',
        'tags': ['local', 'receptionist', 'onboarding'],
        'being_name': 'Local',
        'companion_name': 'Local',
        'author_hash_short': 'builtin',
        'severity': 'local',
        'score': 0,
        'review': 'Built-in local receptionist. No network required.',
        'installs': 0,
        'created_at': 0,
    }
}

OPENAI_COMPAT_KEYS = {
    'model', 'messages', 'stream', 'stream_options', 'max_tokens',
    'temperature', 'top_p', 'stop', 'tools', 'tool_choice',
    'response_format', 'thinking', 'reasoning_effort'
}

def normalize_model_name(name):
    model = str(name or '').strip()
    if not model or model.lower().startswith('gemini'):
        return DEFAULT_MAIN_MODEL
    return model

def get_default_auth_header():
    auth_header = os.environ.get('GLM_AUTH_HEADER', '').strip()
    if auth_header:
        return auth_header
    api_key = os.environ.get('GLM_API_KEY', '').strip()
    if api_key:
        return api_key if api_key.lower().startswith('bearer ') else f'Bearer {api_key}'
    return ''

def sanitize_openai_compat_payload(payload, has_image=False):
    clean = {k: v for k, v in payload.items() if k in OPENAI_COMPAT_KEYS}
    clean['model'] = VISION_MODEL if has_image else normalize_model_name(clean.get('model'))
    clean['messages'] = payload.get('messages', [])
    clean['stream'] = bool(payload.get('stream', False))
    if not has_image:
        clean['max_tokens'] = 32768
        clean['temperature'] = 0.1
        clean['top_p'] = 0.7
        clean['thinking'] = {'type': 'enabled'}
        clean['reasoning_effort'] = 'high'
        clean['stream_options'] = {'include_usage': True}
    else:
        clean['max_tokens'] = min(int(clean.get('max_tokens') or 2048), 2048)
        clean['temperature'] = 0.2
        clean['top_p'] = 0.7
        if clean.get('stream'):
            clean['stream_options'] = {'include_usage': True}

    thinking = clean.get('thinking')
    if isinstance(thinking, dict) and thinking.get('type') in ('enabled', 'adaptive'):
        clean['reasoning_effort'] = clean.get('reasoning_effort') or 'medium'
    else:
        clean.pop('thinking', None)
        clean.pop('reasoning_effort', None)
    return clean

def local_hub_safe_name(name):
    name = urllib.parse.unquote(str(name or '')).strip()
    if not re.match(r'^[A-Za-z0-9_-]{1,64}$', name):
        raise ValueError('invalid skill name')
    return name

def local_hub_path(name):
    return os.path.join(LOCAL_HUB_DIR, local_hub_safe_name(name) + '.json')

def read_local_skill(name):
    safe_name = local_hub_safe_name(name)
    if safe_name in BUILTIN_LOCAL_SKILLS:
        return BUILTIN_LOCAL_SKILLS[safe_name]
    path = local_hub_path(name)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def list_local_skills(query='', limit=20, offset=0):
    os.makedirs(LOCAL_HUB_DIR, exist_ok=True)
    skills = []
    q = (query or '').lower().strip()
    for s in BUILTIN_LOCAL_SKILLS.values():
        haystack = ' '.join([
            str(s.get('name', '')),
            str(s.get('instruction', '')),
            ' '.join(map(str, s.get('tags', []) or [])),
        ]).lower()
        if not q or q in haystack:
            skills.append(s)
    for fn in sorted(os.listdir(LOCAL_HUB_DIR)):
        if not fn.endswith('.json'):
            continue
        try:
            with open(os.path.join(LOCAL_HUB_DIR, fn), 'r', encoding='utf-8') as f:
                s = json.load(f)
            haystack = ' '.join([
                str(s.get('name', '')),
                str(s.get('instruction', '')),
                ' '.join(map(str, s.get('tags', []) or [])),
            ]).lower()
            if q and q not in haystack:
                continue
            skills.append(s)
        except Exception as e:
            print('Local hub skip:', fn, e)
    return skills[offset:offset + limit]

def normalize_local_skill(body):
    name = local_hub_safe_name(body.get('name'))
    return {
        'name': name,
        'instruction': str(body.get('instruction') or ''),
        'code': body.get('code') or None,
        'code_readme': body.get('code_readme') or None,
        'contact': str(body.get('contact') or ''),
        'note': str(body.get('note') or ''),
        'tags': body.get('tags') if isinstance(body.get('tags'), list) else [],
        'being_name': str(body.get('being_name') or 'Local'),
        'companion_name': str(body.get('companion_name') or 'Local'),
        'author_hash_short': 'local',
        'severity': 'local',
        'score': 0,
        'review': 'Local hub skill. Not externally reviewed.',
        'installs': 0,
        'created_at': body.get('created_at') or 0,
    }

class GLMProxyHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def _send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/local-hub/list':
            params = urllib.parse.parse_qs(parsed.query)
            q = params.get('q', [''])[0]
            try:
                limit = max(1, min(100, int(params.get('limit', ['20'])[0])))
                offset = max(0, int(params.get('offset', ['0'])[0]))
            except ValueError:
                limit, offset = 20, 0
            self._send_json(200, {'skills': list_local_skills(q, limit, offset), 'local': True})
            return
        if parsed.path.startswith('/api/local-hub/skill/'):
            try:
                name = parsed.path.rsplit('/', 1)[-1]
                skill = read_local_skill(name)
                if not skill:
                    self._send_json(404, {'error': 'local skill not found', 'name': urllib.parse.unquote(name)})
                    return
                self._send_json(200, skill)
            except ValueError as e:
                self._send_json(400, {'error': str(e)})
            return
        return super().do_GET()

    def do_POST(self):
        if self.path == '/api/local-hub/submit':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                body = json.loads(post_data.decode('utf-8'))
                skill = normalize_local_skill(body)
                os.makedirs(LOCAL_HUB_DIR, exist_ok=True)
                with open(local_hub_path(skill['name']), 'w', encoding='utf-8') as f:
                    json.dump(skill, f, ensure_ascii=False, indent=2)
                self._send_json(200, {
                    'decision': 'approved',
                    'severity': 'local',
                    'score': 0,
                    'review': 'Saved to local hub.',
                    'skill': skill,
                })
            except Exception as e:
                self._send_json(400, {'error': str(e)})
            return
        if self.path in ['/api/chat', '/api/vision']:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                req_json = json.loads(post_data.decode('utf-8'))
            except:
                req_json = {}

            # 1. 角色缝合 (Role Merging)
            messages = req_json.get('messages', [])
            merged = []
            for m in messages:
                if m.get('role') == 'system':
                    merged.append(m)
                    continue
                if not merged:
                    merged.append(m)
                else:
                    if merged[-1].get('role') == m.get('role'):
                        prev_c = merged[-1]['content']
                        curr_c = m['content']
                        # 🚀 强力缝合：无论里面是字符串还是数组，同角色必须合并！
                        if isinstance(prev_c, str) and isinstance(curr_c, str):
                            merged[-1]['content'] += '\n\n' + curr_c
                        else:
                            if isinstance(prev_c, str): prev_c = [{"type": "text", "text": prev_c}]
                            if isinstance(curr_c, str): curr_c = [{"type": "text", "text": curr_c}]
                            merged[-1]['content'] = prev_c + curr_c
                    else:
                        merged.append(m)
            req_json['messages'] = merged
            
            # 2. 提取图片并净化历史 (Image Extraction & Sanitization)
            last_user_idx = -1
            for i in range(len(merged)-1, -1, -1):
                if merged[i].get('role') == 'user':
                    last_user_idx = i
                    break

            has_image = False
            img_pattern = re.compile(r'<img[^>]+src="(data:image/[^;]+;base64,[^"]+)"[^>]*>')
            
            for i, m in enumerate(merged):
                content_val = m.get('content', '')
                
                # 🚀 核心修复：深入解析前端传来的 List 数组
                if isinstance(content_val, list):
                    new_content = []
                    for block in content_val:
                        if block.get('type') == 'text' and isinstance(block.get('text'), str):
                            images = img_pattern.findall(block['text'])
                            if images:
                                if i == last_user_idx:
                                    has_image = True
                                    clean_text = img_pattern.sub('', block['text']).strip()
                                    if clean_text:
                                        new_content.append({"type": "text", "text": clean_text})
                                    else:
                                        new_content.append({"type": "text", "text": "请分析图片。"})
                                    for b64 in images:
                                        new_content.append({"type": "image_url", "image_url": {"url": b64}})
                                else:
                                    clean_text = img_pattern.sub('\n[历史图片已降维清理, 保护Token]\n', block['text']).strip()
                                    new_content.append({"type": "text", "text": clean_text})
                            else:
                                new_content.append(block)
                        elif block.get('type') == 'image_url':
                            if i == last_user_idx:
                                has_image = True
                                new_content.append(block)
                            else:
                                new_content.append({"type": "text", "text": "[历史原生图片已降维清理]"})
                        else:
                            new_content.append(block)
                    m['content'] = new_content
                    
                # 兼容历史纯字符串格式
                elif isinstance(content_val, str):
                    images = img_pattern.findall(content_val)
                    if images:
                        if i == last_user_idx:
                            has_image = True
                            clean_text = img_pattern.sub('', content_val).strip()
                            new_content = []
                            if clean_text:
                                new_content.append({"type": "text", "text": clean_text})
                            else:
                                new_content.append({"type": "text", "text": "请分析图片。"})
                            for b64 in images:
                                new_content.append({"type": "image_url", "image_url": {"url": b64}})
                            m['content'] = new_content
                        else:
                            clean_text = img_pattern.sub('\n[历史图片已降维清理, 保护Token]\n', content_val).strip()
                            m['content'] = clean_text

            # 3. 智能路由
            if has_image:
                print(f"Image detected in chat history. Routing to Vision Copilot ({VISION_MODEL})...")
                req_json = sanitize_openai_compat_payload(req_json, has_image=True)
                vision_sys = (
                    "你是视觉信息提取模块，不是主智能体，也不是行动规划者。\n"
                    "你的唯一任务是把图片中可见的信息转成结构化文字，供主脑(GLM)参考。\n"
                    "严格禁止：输出 /self_continue、/call_for_trigger、/call_for_human；禁止写行动计划、下一步计划、工具调用、代码块；禁止替主脑做最终业务决策。\n"
                    "如果图片是界面截图，可以描述与用户问题相关的界面内容；忽略无关的浏览器边框、任务栏和装饰元素。\n"
                    "输出格式必须简洁：\n"
                    "1. 图片类型\n"
                    "2. 可见文字/OCR\n"
                    "3. 关键对象/数据\n"
                    "4. 与用户问题相关的观察\n"
                    "5. 不确定点\n"
                )
                sys_found = False
                for m in req_json['messages']:
                    if m.get('role') == 'system':
                        m['content'] = vision_sys
                        sys_found = True
                        break
                if not sys_found:
                    req_json['messages'].insert(0, {'role': 'system', 'content': vision_sys})
            else:
                req_json = sanitize_openai_compat_payload(req_json, has_image=False)
                print(f"Text only. Routing to Main Brain ({req_json.get('model')})...")

            # 4. 动态提取前端传来的 Authorization Header
            auth_header = self.headers.get('Authorization', '').strip()
            if len(auth_header) < 15:
                auth_header = get_default_auth_header()
            if len(auth_header) < 15:
                self._send_json(401, {
                    'error': 'missing GLM auth',
                    'message': 'Set GLM_API_KEY or GLM_AUTH_HEADER before starting start_glm.py.'
                })
                return

            # 4. 🛡️ 宽容型 SSL 上下文
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
            except AttributeError:
                pass

            # 5. 🚀 核心修复：伪装成 Chrome 浏览器，绕过阿里云 WAF 防火墙拦截
            req = urllib.request.Request(
                UPSTREAM_CHAT_COMPLETIONS,
                data=json.dumps(req_json).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': auth_header,
                    'Accept': 'text/event-stream' if self.path == '/api/chat' else 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Connection': 'keep-alive'
                },
                method='POST'
            )
            
            try:
                with urllib.request.urlopen(req, context=ctx) as response:
                    self.send_response(200)
                    for k, v in response.headers.items():
                        if k.lower() not in ['transfer-encoding', 'content-length', 'connection', 'content-encoding']:
                            self.send_header(k, v)
                    self.end_headers()
                    while True:
                        chunk = response.read(1024)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8')
                print("Aliyun API Error:", e.code, err_body)
                self.send_response(e.code)
                self.end_headers()
                self.wfile.write(err_body.encode('utf-8'))
            except Exception as e:
                print("Proxy Error:", e)
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith('/api/local-hub/skill/'):
            try:
                path = local_hub_path(parsed.path.rsplit('/', 1)[-1])
                if os.path.exists(path):
                    os.remove(path)
                self._send_json(200, {'ok': True})
            except Exception as e:
                self._send_json(400, {'error': str(e)})
            return
        self.send_response(404)
        self.end_headers()

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), GLMProxyHandler) as httpd:
    print(f"INFERO Bulletproof Router running on http://127.0.0.1:{PORT}")
    httpd.serve_forever()
