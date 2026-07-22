"""Server entry point. Called by the root `start_glm.py` shim."""
from __future__ import annotations

import socketserver

from . import config
from .handler import GLMProxyHandler


def run() -> None:
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', config.PORT), GLMProxyHandler) as httpd:
        print(f'INFERO db backend running on http://127.0.0.1:{config.PORT}')
        print(f'  weather mode : {config.WEATHER_MODE}')
        print(f'  luwang base  : {config.LUWANG_ADAPTER_STATE.get("base_url")}')
        print(f'  glm model    : {config.DEFAULT_MAIN_MODEL}')
        print(f'  vision model : {config.VISION_MODEL}')
        httpd.serve_forever()


if __name__ == '__main__':
    run()
