"""Knowledge base — read-only markdown docs served under /api/kb/*.

The KB replaces the old anti-pattern of stuffing scenario SOPs and report
templates into skill instructions (which live permanently in the agent's core
memory). Docs stay on disk; the agent explicitly `kb.read()` them when needed
and only that one doc enters the current turn's consciousness.

Layout under `docs/`:
    playbooks/<scenario>.md   - 7 scenario SOPs
    reports/<template>.md     - 6 report templates
    api/<name>.md             - platform reference docs
    platform_inventory.md     - the platform-vs-competition mapping table

`list()` returns the full tree; `read(name)` fetches one file (name is the
relative POSIX-style path without the .md suffix, or with it — both accepted);
`search(query)` does a case-insensitive substring match against file names and
first ~1 KB of each file's content.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from . import config


ALLOWED_SUBDIRS = ('playbooks', 'reports', 'api')
_SUMMARY_MAX_CHARS = 1024


def _safe_name(name: str) -> str:
    """Reject traversal / absolute paths; normalize slashes."""
    name = (name or '').strip().lstrip('/')
    if not name or '..' in name.split('/'):
        raise ValueError('invalid doc name')
    if not name.endswith('.md'):
        name = name + '.md'
    return name.replace('\\', '/')


def _abs_path(name: str) -> str:
    safe = _safe_name(name)
    abs_path = os.path.abspath(os.path.join(config.DOCS_DIR, safe))
    if not abs_path.startswith(os.path.abspath(config.DOCS_DIR)):
        raise ValueError('invalid doc path')
    return abs_path


def _first_line_summary(path: str) -> str:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            head = f.read(_SUMMARY_MAX_CHARS)
    except Exception:
        return ''
    for line in head.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            return line.lstrip('#').strip()
        if line.startswith('>'):
            continue
        return line[:120]
    return ''


def list_docs() -> Dict[str, Any]:
    """Return `{group: [{name, path, title}, ...]}` for every doc under docs/."""
    out: Dict[str, List[Dict[str, str]]] = {}
    if not os.path.isdir(config.DOCS_DIR):
        return {'docs': [], 'root': config.DOCS_DIR}
    for root, dirs, files in os.walk(config.DOCS_DIR):
        dirs.sort()
        rel = os.path.relpath(root, config.DOCS_DIR).replace('\\', '/')
        group = rel if rel != '.' else 'root'
        entries: List[Dict[str, str]] = []
        for fn in sorted(files):
            if not fn.endswith('.md'):
                continue
            full = os.path.join(root, fn)
            rel_name = os.path.relpath(full, config.DOCS_DIR).replace('\\', '/')
            entries.append({
                'name': rel_name[:-3],  # strip .md
                'path': rel_name,
                'title': _first_line_summary(full),
            })
        if entries:
            out[group] = entries
    return {'docs': out, 'root': os.path.relpath(config.DOCS_DIR, config.REPO_ROOT)}


def read_doc(name: str) -> Optional[Dict[str, Any]]:
    try:
        path = _abs_path(name)
    except ValueError:
        return None
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception:
        return None
    return {
        'name': os.path.relpath(path, config.DOCS_DIR).replace('\\', '/')[:-3],
        'path': os.path.relpath(path, config.DOCS_DIR).replace('\\', '/'),
        'title': _first_line_summary(path),
        'content': text,
        'chars': len(text),
    }


def search_docs(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    q = (query or '').strip().lower()
    if not q:
        return []
    hits: List[Dict[str, Any]] = []
    if not os.path.isdir(config.DOCS_DIR):
        return hits
    for root, _dirs, files in os.walk(config.DOCS_DIR):
        for fn in files:
            if not fn.endswith('.md'):
                continue
            full = os.path.join(root, fn)
            try:
                with open(full, 'r', encoding='utf-8') as f:
                    head = f.read(_SUMMARY_MAX_CHARS)
            except Exception:
                continue
            name = os.path.relpath(full, config.DOCS_DIR).replace('\\', '/')[:-3]
            if q in name.lower() or q in head.lower():
                hits.append({
                    'name': name,
                    'title': _first_line_summary(full),
                    'excerpt': head[:200],
                })
                if len(hits) >= limit:
                    return hits
    return hits
