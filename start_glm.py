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
        if self.path == '/api/chat':
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
                if m['role'] == 'system':
                    merged.append(m)
                    continue
                if not merged:
                    merged.append(m)
                else:
                    if merged[-1]['role'] == m['role']:
                        if isinstance(merged[-1]['content'], str) and isinstance(m['content'], str):
                            merged[-1]['content'] += '\n\n' + m['content']
                        else:
                            merged.append(m)
                    else:
                        merged.append(m)
            req_json['messages'] = merged
            
            # 2. 动态注入思考引擎 (不再硬编码模型名)
            model_name = str(req_json.get('model', '')).lower()
            if 'glm' in model_name or 'qwen' in model_name or 'deepseek' in model_name:
                req_json['thinking'] = {'type': 'enabled'}
                req_json['reasoning_effort'] = 'high'

            print(f"Forwarding to Aliyun... Model: {req_json.get('model')}")

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
            except urllib.error.HTTPError as e:
                # 捕获阿里云真实的报错并返回给前端
                err_body = e.read().decode('utf-8')
                print("Aliyun API Error:", e.code, err_body)
                self.send_response(e.code)
                self.end_headers()
                self.wfile.write(err_body.encode('utf-8'))
            except Exception as e:
                print("Local Proxy Error:", e)
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), GLMProxyHandler) as httpd:
    print(f"GLM Proxy Server running on http://127.0.0.1:{PORT}")
    httpd.serve_forever()
