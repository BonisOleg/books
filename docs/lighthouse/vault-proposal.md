# Пропозиція дописок у Prometey vault

Записано в канонічні скіли 2026-09-30. Новий скіл не створювався.

1. Горизонтальна карусель і `loading="lazy"`. Chrome підвантажує слайди в межах ~1250–2500 px від в'юпорта, тож сусідні слайди в flex-треку вантажаться одразу. Для слайдів 2+ не ставити `src`, а `data-src` / `data-srcset`, і підставляти їх скриптом на показ наступного слайда. Перший слайд і `<noscript>` лишаються з `src`. Куди: `shop_design6` або `gallery_patterns`.

2. `loading="eager"` і `fetchpriority="high"` — різні рішення. Eager на перший ряд (~4). High лише на один LCP (герой або перша картка, якщо героя немає). Логотип eager без high. Куди: `shop_design6`.

3. Nginx на Droplet віддає `/static/` сам, без gzip, якщо в `gzip_types` немає `text/css` і `application/javascript`. `expires` плюс другий `add_header Cache-Control` дає два заголовки. `Vary: Accept` не потрібен, коли WebP має окремий URL. Куди: `django-digitalocean-deploy` і `django-docker-nginx`. Не копіювати HTTP-шаблон поверх vhost Certbot.

4. Best Practices «third-party cookies» не зникає, якщо GTM/Pixel/чат стартують по `load` або через кілька секунд: лабораторний прогін їх усе одно бачить. Щоб аудит пройшов, теги лише після першої взаємодії (scroll/pointer/key), а `purchase` — одразу на сторінці успіху, push у `dataLayer` до `gtm.js`. Куди: `gtm_conversion_events_skill`.

5. `alt=""` прибирає Lighthouse `image-redundant-alt`, але суперечить `seo_skill` (порожній alt лише для декору). Описовий alt, який не дорівнює тексту того самого посилання (`Фото категорії: …`), закриває обидва правила. Куди: `seo_skill` / SEO checklist.
