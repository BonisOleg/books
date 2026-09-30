#!/usr/bin/env python3
"""Три прогони Lighthouse і медіана. Запускати після деплою на прод."""
import json
import statistics
import subprocess
from pathlib import Path

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
URLS = [
    ('home', 'https://ofion.com.ua/'),
    ('catalog', 'https://ofion.com.ua/catalog/'),
    ('category', 'https://ofion.com.ua/catalog/knigi/'),
    (
        'product',
        'https://ofion.com.ua/catalog/product/podarunkova-kniga-trilogiya-bazhannya-'
        'finansist-titan-stoyik-teodor-drajzer-u-shkiryanij-paliturci/',
    ),
]
RUNS = 3
OUT = Path(__file__).resolve().parents[1] / 'docs' / 'lighthouse' / 'after.json'


def scores(url: str, dest: Path) -> dict:
    cmd = [
        'npx', '--yes', 'lighthouse@12.6.1', url,
        '--quiet',
        '--chrome-path', CHROME,
        '--chrome-flags=--headless=new --no-sandbox',
        '--only-categories=performance,accessibility,best-practices,seo',
        '--form-factor=mobile',
        '--output=json',
        f'--output-path={dest}',
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr[-500:] or result.stdout[-500:])
    data = json.loads(dest.read_text(encoding='utf-8'))
    return {
        name: round((cat.get('score') or 0) * 100)
        for name, cat in data.get('categories', {}).items()
    }


def main() -> None:
    summary = {}
    tmp = Path('/tmp/lh-after')
    tmp.mkdir(exist_ok=True)
    for key, url in URLS:
        series = []
        for run in range(1, RUNS + 1):
            print(f'{key} run {run}', flush=True)
            series.append(scores(url, tmp / f'{key}-{run}.json'))
        summary[key] = {
            'url': url,
            'runs': series,
            'median': {
                name: int(statistics.median([item[name] for item in series]))
                for name in series[0]
            },
        }
        print(key, summary[key]['median'], flush=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'wrote {OUT}')


if __name__ == '__main__':
    main()
