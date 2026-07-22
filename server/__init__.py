"""INFERO db backend server package.

Modules:
    config           - environment variables, constants, mutable adapter state
    http_utils       - request/response helpers shared by handlers
    weather_adapter  - WeatherAdapter: luwang HTTP client + demo fallback
    demo_data        - offline sample data loader for Demo Mode
    knowledge_base   - /api/kb read-only doc lookup
    skill_hub        - local skill hub file storage + built-ins
    glm_proxy        - GLM/Vision payload sanitization + upstream chat proxy
    handler          - HTTP request handler wiring all endpoints
    main             - server entry point (called by root start_glm.py shim)
"""

__all__ = [
    'config',
    'http_utils',
    'weather_adapter',
    'demo_data',
    'knowledge_base',
    'skill_hub',
    'glm_proxy',
    'handler',
    'main',
]
