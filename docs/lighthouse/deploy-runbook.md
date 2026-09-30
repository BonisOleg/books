# Безпечний деплой Lighthouse v2

Живий `/etc/nginx/sites-available/ofion` (Certbot) і каталог `media/` не перезаписуються.
`collectstatic --clear` чистить лише `staticfiles/`.

Порядок:

1. Nginx (можна до коду). На Droplet від кореня проєкту:

```bash
sudo bash deploy/digitalocean/apply_performance.sh
curl -sI --http2 https://ofion.com.ua/ | head -1
curl -sI -H 'Accept-Encoding: gzip' https://ofion.com.ua/static/css/site.css | grep -i content-encoding
```

Очікування: `HTTP/2` і `content-encoding: gzip`. Якщо `nginx -t` падає, скрипт сам повертає копію з `/var/backups/bookshop-nginx-*` і не робить reload.

2. Код на сервер (`deploy/digitalocean/deploy.sh` або звичайний pull + collectstatic). Не копіювати `nginx-ofion.conf` поверх наявного vhost.

3. Варіанти зображень. Оригінали не змінюються, з'являються лише сусідні `.w480.webp` / `.w800.webp` / `.w1280.webp`:

```bash
python manage.py build_image_variants --dry-run
python manage.py build_image_variants
```

4. Перевірка одного файлу (підставте реальний шлях банера):

```bash
curl -sI -o /dev/null -w '%{http_code}\n' https://ofion.com.ua/media/banners/ІМ'Я.png.w480.webp
```

Очікування: `200`.

5. Замір після деплою, три прогони, медіана:

```bash
python3 scripts/lighthouse_median.py
```

Результат: `docs/lighthouse/after.json`.

Нотатка: окремий gtag GA4 лишається поруч із GTM. Контейнер не звіряли, дубль page_view можливий.
