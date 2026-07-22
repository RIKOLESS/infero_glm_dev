"""GLM chat + vision proxy: role stitching, image routing, upstream forwarding.

Contract kept identical to the original `start_glm.py`:
    - POST /api/chat    -> stream text-mode GLM
    - POST /api/vision  -> non-stream vision call

Behavior:
    1. Stitch consecutive same-role messages (avoids GLM API rejection).
    2. Extract base64 images from the *last* user message; strip images from
       history to protect the token budget.
    3. Route: image present → Qwen vision copilot with a strict extraction
       prompt (no /self_continue etc.); text only → GLM main brain.
    4. Sanitize the payload down to OpenAI-compatible keys with our tuned
       max_tokens/temperature/top_p/thinking defaults for the main brain.
    5. Forward with a Chrome User-Agent to satisfy the WAF and stream chunks
       straight back to the client.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List

from . import config
from .http_utils import send_json


IMG_PATTERN = re.compile(r'<img[^>]+src="(data:image/[^;]+;base64,[^"]+)"[^>]*>')

VISION_SYSTEM_PROMPT = (
    '你是视觉信息提取模块，不是主智能体，也不是行动规划者。\n'
    '你的唯一任务是把图片中可见的信息转成结构化文字，供主脑(GLM)参考。\n'
    '严格禁止：输出 /self_continue、/call_for_trigger、/call_for_human；'
    '禁止写行动计划、下一步计划、工具调用、代码块；禁止替主脑做最终业务决策。\n'
    '如果图片是界面截图，可以描述与用户问题相关的界面内容；忽略无关的浏览器边框、任务栏和装饰元素。\n'
    '输出格式必须简洁：\n'
    '1. 图片类型\n'
    '2. 可见文字/OCR\n'
    '3. 关键对象/数据\n'
    '4. 与用户问题相关的观察\n'
    '5. 不确定点\n'
)


def sanitize_openai_compat_payload(payload: Dict[str, Any], has_image: bool = False) -> Dict[str, Any]:
    """Drop non-OpenAI keys and pin sane defaults per routing mode."""
    clean: Dict[str, Any] = {k: v for k, v in payload.items() if k in config.OPENAI_COMPAT_KEYS}
    clean['model'] = config.VISION_MODEL if has_image else config.normalize_model_name(clean.get('model'))
    clean['messages'] = payload.get('messages', [])
    clean['stream'] = bool(payload.get('stream', False))
    if not has_image:
        # Main brain: max thinking budget, low temperature, high reasoning.
        clean['max_tokens'] = 32768
        clean['temperature'] = 0.1
        clean['top_p'] = 0.7
        clean['thinking'] = {'type': 'enabled'}
        clean['reasoning_effort'] = 'high'
        clean['stream_options'] = {'include_usage': True}
    else:
        # Vision copilot: short output, stable but not deterministic.
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


def _stitch_same_role(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for m in messages:
        if m.get('role') == 'system':
            merged.append(m)
            continue
        if not merged:
            merged.append(m)
            continue
        if merged[-1].get('role') == m.get('role'):
            prev_c = merged[-1]['content']
            curr_c = m['content']
            if isinstance(prev_c, str) and isinstance(curr_c, str):
                merged[-1]['content'] = prev_c + '\n\n' + curr_c
            else:
                if isinstance(prev_c, str):
                    prev_c = [{'type': 'text', 'text': prev_c}]
                if isinstance(curr_c, str):
                    curr_c = [{'type': 'text', 'text': curr_c}]
                merged[-1]['content'] = prev_c + curr_c
        else:
            merged.append(m)
    return merged


def _extract_images_and_sanitize(messages: List[Dict[str, Any]]) -> bool:
    """Mutate `messages` in place: split base64 images from the last user turn
    into `image_url` blocks; strip images from historical turns to save tokens.
    Returns True if the last user turn actually carries any image."""
    last_user_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get('role') == 'user':
            last_user_idx = i
            break

    has_image = False
    for i, m in enumerate(messages):
        content_val = m.get('content', '')

        if isinstance(content_val, list):
            new_content: List[Dict[str, Any]] = []
            for block in content_val:
                if block.get('type') == 'text' and isinstance(block.get('text'), str):
                    images = IMG_PATTERN.findall(block['text'])
                    if images:
                        if i == last_user_idx:
                            has_image = True
                            clean_text = IMG_PATTERN.sub('', block['text']).strip()
                            new_content.append({'type': 'text', 'text': clean_text or '请分析图片。'})
                            for b64 in images:
                                new_content.append({'type': 'image_url', 'image_url': {'url': b64}})
                        else:
                            clean_text = IMG_PATTERN.sub('\n[历史图片已降维清理, 保护Token]\n', block['text']).strip()
                            new_content.append({'type': 'text', 'text': clean_text})
                    else:
                        new_content.append(block)
                elif block.get('type') == 'image_url':
                    if i == last_user_idx:
                        has_image = True
                        new_content.append(block)
                    else:
                        new_content.append({'type': 'text', 'text': '[历史原生图片已降维清理]'})
                else:
                    new_content.append(block)
            m['content'] = new_content

        elif isinstance(content_val, str):
            images = IMG_PATTERN.findall(content_val)
            if images:
                if i == last_user_idx:
                    has_image = True
                    clean_text = IMG_PATTERN.sub('', content_val).strip()
                    new_content = [{'type': 'text', 'text': clean_text or '请分析图片。'}]
                    for b64 in images:
                        new_content.append({'type': 'image_url', 'image_url': {'url': b64}})
                    m['content'] = new_content
                else:
                    m['content'] = IMG_PATTERN.sub('\n[历史图片已降维清理, 保护Token]\n', content_val).strip()

    return has_image


def _ensure_vision_system(req_json: Dict[str, Any]) -> None:
    for m in req_json['messages']:
        if m.get('role') == 'system':
            m['content'] = VISION_SYSTEM_PROMPT
            return
    req_json['messages'].insert(0, {'role': 'system', 'content': VISION_SYSTEM_PROMPT})


def _lenient_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
    except AttributeError:
        pass
    return ctx


def handle_chat_or_vision(handler, path: str) -> None:
    """Wire the request handler's /api/chat and /api/vision routes."""
    content_length = int(handler.headers.get('Content-Length', 0))
    post_data = handler.rfile.read(content_length) if content_length > 0 else b''
    try:
        req_json = json.loads(post_data.decode('utf-8'))
    except Exception:
        req_json = {}

    messages = req_json.get('messages', [])
    req_json['messages'] = _stitch_same_role(messages)
    has_image = _extract_images_and_sanitize(req_json['messages'])

    if has_image:
        print(f'Image detected. Routing to Vision Copilot ({config.VISION_MODEL})...')
        req_json = sanitize_openai_compat_payload(req_json, has_image=True)
        _ensure_vision_system(req_json)
    else:
        req_json = sanitize_openai_compat_payload(req_json, has_image=False)
        print(f"Text only. Routing to Main Brain ({req_json.get('model')})...")

    auth_header = (handler.headers.get('Authorization') or '').strip()
    if len(auth_header) < 15:
        auth_header = config.get_default_auth_header()
    if len(auth_header) < 15:
        send_json(handler, 401, {
            'error': 'missing GLM auth',
            'message': 'Set GLM_API_KEY or GLM_AUTH_HEADER before starting the server.',
        })
        return

    req = urllib.request.Request(
        config.UPSTREAM_CHAT_COMPLETIONS,
        data=json.dumps(req_json).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': auth_header,
            'Accept': 'text/event-stream' if path == '/api/chat' else 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Connection': 'keep-alive',
        },
        method='POST',
    )

    ctx = _lenient_ssl_ctx()
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            handler.send_response(200)
            for k, v in response.headers.items():
                if k.lower() not in ('transfer-encoding', 'content-length', 'connection', 'content-encoding'):
                    handler.send_header(k, v)
            handler.end_headers()
            while True:
                chunk = response.read(1024)
                if not chunk:
                    break
                handler.wfile.write(chunk)
                handler.wfile.flush()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        print('Aliyun API Error:', e.code, err_body)
        handler.send_response(e.code)
        handler.end_headers()
        handler.wfile.write(err_body.encode('utf-8'))
    except Exception as e:
        print('Proxy Error:', e)
        handler.send_response(500)
        handler.end_headers()
        handler.wfile.write(str(e).encode('utf-8'))
