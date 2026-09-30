# Lighthouse v2 — стан заміру

Код v2 зібраний локально і на ofion.com.ua ще не викладений. Повторний прогін проді зараз повторив би baseline (HTTP/1.1, CSS без gzip, WebP 404), тому три прогони після деплою не запускались.

Baseline лишається в `docs/lighthouse/baseline.json`.

Після кроків з `docs/lighthouse/deploy-runbook.md`:

```bash
python3 scripts/lighthouse_median.py
```

Скрипт пише медіану трьох мобільних прогонів у `docs/lighthouse/after.json`.
