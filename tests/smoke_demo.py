"""Smoke test: WeatherAdapter runs end-to-end in demo mode without network.

Run: `set WEATHER_MODE=demo && py tests/smoke_demo.py`
Or:  `py tests/smoke_demo.py --mode demo`
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default=os.environ.get('WEATHER_MODE', 'demo'),
                        choices=['demo', 'auto', 'live'])
    args = parser.parse_args()
    os.environ['WEATHER_MODE'] = args.mode

    # Import AFTER setting env so config.WEATHER_MODE picks it up.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from server import weather_adapter as wa, config

    print(f'== smoke test WEATHER_MODE={config.WEATHER_MODE} ==\n')

    scenarios = [
        ('summary',       wa.weather_summary),
        ('short_term',    wa.weather_short_term),
        ('segment_risk',  wa.weather_segment_risk),
        ('resources',     wa.weather_resources),
        ('earthquake',    wa.weather_earthquake),
        ('defense',       wa.weather_defense_advisory),
    ]

    ok = True
    for name, fn in scenarios:
        try:
            r = fn({'provinceName': '四川'}, '', '')
        except Exception as e:
            print(f'[FAIL] {name}: raised {e.__class__.__name__}: {e}')
            ok = False
            continue
        q = r['data_quality']
        marker = 'OK ' if q['failed_count'] == 0 and q['success_count'] > 0 else 'WARN'
        print(f'[{marker}] {name:14} phase={r["phase"]:9} '
              f'success={q["success_count"]} empty={q["empty_count"]} failed={q["failed_count"]}')
        if q['failed_count'] > 0:
            print(f'       failed sources: {q["failed"]}')

    print()
    try:
        rd = wa.report_draft(
            {'params': {'provinceName': '四川'}, 'report_type': 'duty_brief'}, '', '',
        )
        print(f'[OK ] report_draft   phase={rd["phase"]} title={rd["title"]}')
        print(f'       metrics: {json.dumps(rd["metrics"], ensure_ascii=False)}')
        print(f'       sections: {[s["title"] for s in rd["sections"]]}')
    except Exception as e:
        print(f'[FAIL] report_draft: {e}')
        ok = False

    print()
    print('== all green ==' if ok else '== FAILURES ==')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
