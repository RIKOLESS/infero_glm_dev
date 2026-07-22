"""Local Skill Hub — file-backed CRUD + a built-in receptionist skill.

The agent may call `hubInstall(name)` on first boot to pull curated skills
into its IndexedDB. When the public hub is unreachable (offline demo, judge
review), this local hub keeps the boot flow working. Directory:
    `local_hub/skills/<name>.json`

`BUILTIN_LOCAL_SKILLS` is a compiled-in map that always overrides on-disk
copies of the same name so a fresh checkout is functional immediately.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional

from . import config


BUILTIN_LOCAL_SKILLS: Dict[str, Dict[str, Any]] = {
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


_SAFE_NAME = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def local_hub_safe_name(name: Any) -> str:
    """Sanitize a skill name to be usable as a filename. Raises on invalid input."""
    name = urllib.parse.unquote(str(name or '')).strip()
    if not _SAFE_NAME.match(name):
        raise ValueError('invalid skill name')
    return name


def local_hub_path(name: str) -> str:
    return os.path.join(config.LOCAL_HUB_DIR, local_hub_safe_name(name) + '.json')


def read_local_skill(name: str) -> Optional[Dict[str, Any]]:
    safe_name = local_hub_safe_name(name)
    if safe_name in BUILTIN_LOCAL_SKILLS:
        return BUILTIN_LOCAL_SKILLS[safe_name]
    path = local_hub_path(name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _match(query: str, skill: Dict[str, Any]) -> bool:
    if not query:
        return True
    haystack = ' '.join([
        str(skill.get('name', '')),
        str(skill.get('instruction', '')),
        ' '.join(map(str, skill.get('tags', []) or [])),
    ]).lower()
    return query in haystack


def list_local_skills(query: str = '', limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    os.makedirs(config.LOCAL_HUB_DIR, exist_ok=True)
    q = (query or '').lower().strip()
    skills: List[Dict[str, Any]] = [s for s in BUILTIN_LOCAL_SKILLS.values() if _match(q, s)]
    for fn in sorted(os.listdir(config.LOCAL_HUB_DIR)):
        if not fn.endswith('.json'):
            continue
        try:
            with open(os.path.join(config.LOCAL_HUB_DIR, fn), 'r', encoding='utf-8') as f:
                s = json.load(f)
        except Exception as e:
            print('Local hub skip:', fn, e)
            continue
        if _match(q, s):
            skills.append(s)
    return skills[offset:offset + limit]


def normalize_local_skill(body: Dict[str, Any]) -> Dict[str, Any]:
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


def save_local_skill(skill: Dict[str, Any]) -> None:
    os.makedirs(config.LOCAL_HUB_DIR, exist_ok=True)
    with open(local_hub_path(skill['name']), 'w', encoding='utf-8') as f:
        json.dump(skill, f, ensure_ascii=False, indent=2)


def delete_local_skill(name: str) -> None:
    path = local_hub_path(name)
    if os.path.exists(path):
        os.remove(path)
