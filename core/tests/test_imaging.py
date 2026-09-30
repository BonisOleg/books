import tempfile
from io import BytesIO, StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.utils import translation
from PIL import Image

from core.imaging.variants import build_variants, cap_original, process_stored_file
from core.templatetags.image_tags import image_variant, responsive_img
from products.models import Product, ProductImage

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'imaging-tests',
    }
}


def _png(width, height, color=(180, 20, 20, 255)) -> bytes:
    buffer = BytesIO()
    Image.new('RGBA', (width, height), color).save(buffer, format='PNG')
    return buffer.getvalue()


class VariantBuildTests(TestCase):
    def test_webp_widths_exif_and_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wide = root / 'wide.png'
            wide.write_bytes(_png(2400, 800))
            self.assertTrue(cap_original(wide))
            with Image.open(wide) as image:
                self.assertLessEqual(max(image.size), 2000)

            meta = build_variants(wide)
            self.assertIsNotNone(meta)
            widths = [item['width'] for item in meta['variants']]
            self.assertEqual(widths, [480, 800, 1280])
            variant = wide.with_name(f'{wide.name}.w480.webp')
            with Image.open(variant) as webp:
                self.assertEqual(webp.format, 'WEBP')
                self.assertIn(webp.mode, ('RGB', 'RGBA'))

            again = build_variants(wide)
            self.assertEqual(again['width'], meta['width'])

            oriented = root / 'oriented.jpg'
            portrait = Image.new('RGB', (80, 30), (10, 20, 30))
            exif = Image.Exif()
            exif[274] = 6
            portrait.save(oriented, format='JPEG', exif=exif)
            before = oriented.read_bytes()
            processed = process_stored_file(oriented)
            self.assertEqual(oriented.read_bytes(), before)
            self.assertEqual(processed['width'], 30)
            self.assertEqual(processed['height'], 80)


@override_settings(CACHES=LOC_MEM)
class ResponsiveImgTests(TestCase):
    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self._override = override_settings(
            MEDIA_ROOT=self._media.name,
            STORAGES={
                'default': {
                    'BACKEND': 'django.core.files.storage.FileSystemStorage',
                    'OPTIONS': {'location': self._media.name},
                },
                'staticfiles': {
                    'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
                },
            },
        )
        self._override.enable()

    def tearDown(self):
        self._override.disable()
        self._media.cleanup()

    def _product_image(self):
        product = Product.objects.create(
            name='Книга',
            slug='knyga-test',
            sku='SKU-IMG-1',
            description='Опис',
            price='100.00',
        )
        upload = SimpleUploadedFile('cover.png', _png(1000, 500), content_type='image/png')
        return ProductImage.objects.create(product=product, image=upload, alt_text='Обкладинка')

    def test_tag_renders_srcset_and_dimensions(self):
        image = self._product_image()
        html = responsive_img(
            image.image,
            alt='Обкладинка',
            css_class='product-card__img',
            sizes='280px',
            eager=True,
        )
        self.assertIn('type="image/webp"', html)
        self.assertIn('480w', html)
        self.assertIn('width="1000"', html)
        self.assertIn('height="500"', html)
        self.assertNotIn('fetchpriority', html)
        self.assertIn('loading="eager"', html)
        self.assertIn('alt="Обкладинка"', html)
        prioritized = responsive_img(image.image, alt='Обкладинка', priority=True)
        self.assertIn('fetchpriority="high"', prioritized)
        first = responsive_img(image.image, eager=1, priority=1)
        self.assertIn('loading="eager"', first)
        self.assertIn('fetchpriority="high"', first)
        fourth = responsive_img(image.image, eager=4, priority=4)
        self.assertIn('loading="eager"', fourth)
        self.assertNotIn('fetchpriority', fourth)
        later = responsive_img(image.image, eager=5, priority=5)
        self.assertIn('loading="lazy"', later)
        held = responsive_img(image.image, alt='Слайд', hold=True, css_class='banner__img')
        live, _, noscript = held.partition('<noscript>')
        self.assertIn('data-src=', live)
        self.assertNotIn(' src=', live)
        self.assertIn('src=', noscript)
        self.assertEqual(image_variant(image.image, 700), image_variant(image.image, 800))

    def test_product_card_template(self):
        # Інші тести ходять на /ru/ і /en/ через client — мова не має протікати
        # ні в modeltranslation при створенні, ні в рендер.
        with translation.override('uk'):
            image = self._product_image()
            image.product.refresh_from_db()
            html = render_to_string('includes/product_card.html', {
                'product': image.product,
                'PHONE_NUMBERS': [],
            })
        self.assertIn('image/webp', html)
        self.assertIn('Купити: Книга', html)
        self.assertIn('type="button"', html)
        output = StringIO()
        call_command('build_image_variants', '--dry-run', stdout=output)
        self.assertIn('would process', output.getvalue())


@override_settings(CACHES=LOC_MEM)
class StorefrontAssetTests(TestCase):
    def test_home_uses_local_assets_and_deferred_analytics(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('/static/css/site.css', html)
        self.assertIn('/static/vendor/htmx-2.0.4.min.js', html)
        self.assertNotIn('unpkg.com/htmx', html)
        self.assertNotIn('gtag/js?id=', html)
        self.assertIn('analytics-loader.js', html)
        self.assertIn('aria-label="Пошук товарів"', html)
        self.assertIn('aria-controls="mobile-menu"', html)
        banners = (ROOT / 'templates/includes/banners.html').read_text(encoding='utf-8')
        self.assertIn("position == 'home_hero'", banners)
        self.assertIn('hold=True', banners)
        loader = (ROOT / 'static/js/analytics-loader.js').read_text(encoding='utf-8')
        self.assertNotIn('requestIdleCallback', loader)
        self.assertNotIn('setTimeout(load', loader)
        self.assertIn('touchstart', loader)
        self.assertIn('purchase-datalayer', loader)
        carousel = (ROOT / 'static/js/carousel.js').read_text(encoding='utf-8')
        self.assertIn('img[data-src]', carousel)
        nginx = (ROOT / 'deploy/digitalocean/nginx-ofion.conf').read_text(encoding='utf-8')
        apply_script = (ROOT / 'deploy/digitalocean/apply_performance.sh').read_text(encoding='utf-8')
        self.assertNotIn('Vary', nginx)
        self.assertNotIn('Vary', apply_script)

    def test_product_page_renders(self):
        product = Product.objects.create(
            name='Сторінка',
            slug='storinka-test',
            sku='SKU-PAGE-1',
            description='<p>Опис</p>',
            price='10.00',
        )
        response = self.client.get(product.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn('Сторінка', response.content.decode())


CREDIT_URL = 'https://www.prometeylabs.com/internet-shop-v2/'


@override_settings(CACHES=LOC_MEM)
class FooterDeveloperLinkTests(TestCase):
    def test_home_has_nofollow_credit_link(self):
        response = self.client.get('/')
        self.assertContains(response, CREDIT_URL)
        self.assertContains(response, 'nofollow')
        self.assertContains(response, '>PrometeyLabs</a>')

    def test_localized_home_keeps_credit_link(self):
        for path in ('/en/', '/ru/'):
            response = self.client.get(path)
            self.assertContains(response, CREDIT_URL)

    def test_inner_page_has_credit_without_link(self):
        response = self.client.get('/catalog/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn(CREDIT_URL, html)
        self.assertNotIn('prometeylabs.com', html)
        self.assertIn('PrometeyLabs', html)
