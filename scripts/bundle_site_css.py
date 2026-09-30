#!/usr/bin/env python3
"""Збирає базові CSS у static/css/site.css і мінімізує. Сторінкові файли лишаються окремо."""
from pathlib import Path

import rcssmin

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / 'static' / 'css'
SOURCES = (
    'base.css',
    'components.css',
    'header.css',
    'footer.css',
    'product-card.css',
    'dropdowns.css',
)
OUTPUT = CSS / 'site.css'


def main() -> None:
    parts = []
    for name in SOURCES:
        parts.append(f'/* {name} */\n')
        parts.append((CSS / name).read_text(encoding='utf-8'))
        if not parts[-1].endswith('\n'):
            parts.append('\n')
    bundled = rcssmin.cssmin(''.join(parts))
    header = '/* Згенеровано scripts/bundle_site_css.py. Не редагувати вручну. */\n'
    OUTPUT.write_text(header + bundled, encoding='utf-8')
    print(f'wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
