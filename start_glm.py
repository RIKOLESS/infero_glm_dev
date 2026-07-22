"""INFERO db backend launcher (backwards-compat entry point).

The actual server lives in the `server/` package. This file exists so that
`py start_glm.py` and `start.bat` continue to work exactly as before.

See:
    - README.md for the 5-minute quick start
    - docs/platform_inventory.md for platform capability mapping
    - .env.example for all environment variables
"""
from __future__ import annotations

import os
import pathlib


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from .env into os.environ (if not already set).

    Only reads lines that look like KEY=VALUE; skips comments (#) and blanks.
    Values in .env always override inherited shell environment variables so that
    the file is the single source of truth for project configuration.
    """
    env_file = pathlib.Path(__file__).parent / '.env'
    if not env_file.exists():
        return
    with env_file.open(encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            if key:
                os.environ[key] = value
    print('[env] Loaded .env')


_load_dotenv()

from server.main import run  # noqa: E402  (must come after env load)


if __name__ == '__main__':
    run()
