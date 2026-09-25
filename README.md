# Магазин книжок

Інтернет-магазин елітних подарунків на Django 5 + HTMX.

## Швидкий старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Адмін-панель: http://localhost:8000/admin/

## Структура

| App | Опис |
|-----|------|
| core | Налаштування сайту, головна сторінка, SEO шаблони |
| products | Товари, категорії, фото/відео, фільтри, Google Merchant Feed |
| cart | Кошик (session-based), HTMX оновлення |
| orders | Замовлення, LiqPay/Monobank/COD оплата |
| accounts | Реєстрація, авторизація, профіль |
| reviews | Відгуки з рейтингом та модерацією |
| blog | Статті та новини |
| promotions | Акції з таймером, upsell, підбір подарунка |
| shipping | Нова Пошта API (пошук відділень) |
| import_export_app | Імпорт/експорт товарів (CSV, Excel, XML) |

## Env-змінні (.env)

```
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True
LIQPAY_PUBLIC_KEY=
LIQPAY_PRIVATE_KEY=
MONOBANK_TOKEN=
NOVAPOSHTA_API_KEY=
TELEGRAM_BOT_USERNAME=
VIBER_BOT_URI=
SITE_DOMAIN=localhost:8000
SITE_PROTOCOL=http
```

## Google Merchant

XML фід: `/feeds/google-merchant.xml` (без категорії «Ікони» / `ikoni` і підкатегорій).
JSON-LD structured data на кожній сторінці товару.
