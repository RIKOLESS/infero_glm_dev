import http.server
import socketserver
import urllib.request
import json

PORT = 8000

class GLMProxyHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        # ==========================================
        # 通道 1: 文本聊天与思考引擎代理 (无熔断版)
        # ==========================================
        if self.path == '/api/chat':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                req_json = json.loads(post_data.decode('utf-8'))
            except:
                req_json = {}

            # 1. 角色缝合
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
                        if isinstance(merged[-1].get('content'), str) and isinstance(m.get('content'), str):
                            merged[-1]['content'] += '\n\n' + m['content']
                        else:
                            merged.append(m)
                    else:
                        merged.append(m)
            req_json['messages'] = merged
            
            # 2. 智能路由
            has_image = False
            for m in merged:
                if isinstance(m.get('content'), list):
                    for block in m['content']:
                        if block.get('type') == 'image_url':
                            has_image = True
                            break
                if has_image: break

            if has_image:
                print("🖼️ Image detected. Routing to Vision Copilot (qwen3.7-plus)...")
                req_json['model'] = 'qwen3.7-plus'
                vision_sys = "你是一个专业的视觉数据提取模块。你的任务是极其精准、简短地提取画面中的核心数据。\n【绝对禁令】：严禁描述与问题无关的背景元素（如浏览器标签、Windows任务栏、聊天框、滚动条等）。\n【输出规范】：直接给出关键数据或结论，不要寒暄，越短越好。"
                
                sys_found = False
                for m in req_json['messages']:
                    if m.get('role') == 'system':
                        m['content'] = vision_sys
                        sys_found = True
                        break
                if not sys_found:
                    req_json['messages'].insert(0, {'role': 'system', 'content': vision_sys})
            else:
                model_name = str(req_json.get('model', '')).lower()
                print(f"📝 Text only. Routing to Main Brain ({model_name})...")
                if 'glm' in model_name or 'qwen' in model_name or 'deepseek' in model_name:
                    req_json['thinking'] = {'type': 'enabled'}
                    req_json['reasoning_effort'] = 'high'
                    # 🛡️ 仅保留防复读惩罚，彻底拆除物理熔断器！让 AI 自由狂奔！
                    req_json['presence_penalty'] = 0.5
                    req_json['frequency_penalty'] = 0.5

            # 3. 转发至阿里云政企专线
            req = urllib.request.Request(
                'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions',
                data=json.dumps(req_json).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer sk-sp-D.LLPDE.vIp6.MEYCIQDKdl1EK3TiuWazwhQT9FgbTvl7g+5+IeWECxL1o5ZjoAIhAJERgmhs4zdUiqtMjmlxkXljROJRUS1Moal61bsKrJ6N',
                    'Accept': 'text/event-stream'
                },
                method='POST'
            )
            
            try:
                with urllib.request.urlopen(req) as response:
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
            except Exception as e:
                print("Chat Proxy Error:", e)
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))

        # ==========================================
        # 通道 2: 独立视觉副脑 API
        # ==========================================
        elif self.path == '/api/vision':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            print("Forwarding direct Vision request to Aliyun...")
            req = urllib.request.Request(
                'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions',
                data=post_data,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer sk-sp-D.LLPDE.vIp6.MEYCIQDKdl1EK3TiuWazwhQT9FgbTvl7g+5+IeWECxL1o5ZjoAIhAJERgmhs4zdUiqtMjmlxkXljROJRUS1Moal61bsKrJ6N',
                    'Accept': 'application/json'
                },
                method='POST'
            )
            try:
                with urllib.request.urlopen(req) as response:
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
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), GLMProxyHandler) as httpd:
    print(f"INFERO Smart Router running on http://127.0.0.1:{PORT}")
    httpd.serve_forever()
