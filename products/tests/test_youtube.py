from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from products.forms import ProductVideoForm
from products.models import Product, ProductVideo
from products.youtube import YOUTUBE_URL_ERROR, parse_youtube_url, youtube_embed_url

VIDEO_ID = 'dQw4w9WgXcQ'

YOUTUBE_CASES = (
    ('watch', f'https://www.youtube.com/watch?v={VIDEO_ID}', 0),
    ('watch-t-та-інші-параметри', f'https://www.youtube.com/watch?v={VIDEO_ID}&feature=share&t=90', 90),
    ('watch-без-www-90s', f'https://youtube.com/watch?v={VIDEO_ID}&t=90s', 90),
    ('watch-1m30s', f'http://www.youtube.com/watch?v={VIDEO_ID}&list=PLabcdefghijk123456789&t=1m30s', 90),
    ('watch-1h2m3s', f'https://www.youtube.com/watch?v={VIDEO_ID}&t=1h2m3s', 3723),
    ('m.youtube', f'https://m.youtube.com/watch?v={VIDEO_ID}&t=45', 45),
    ('youtu.be', f'https://youtu.be/{VIDEO_ID}', 0),
    ('youtu.be-t', f'https://youtu.be/{VIDEO_ID}?t=1m30s', 90),
    ('shorts', f'https://www.youtube.com/shorts/{VIDEO_ID}', 0),
    ('shorts-без-www', f'https://youtube.com/shorts/{VIDEO_ID}?t=12', 12),
    ('live', f'https://www.youtube.com/live/{VIDEO_ID}', 0),
    ('live-90s', f'https://m.youtube.com/live/{VIDEO_ID}?t=90s', 90),
    ('embed', f'https://www.youtube.com/embed/{VIDEO_ID}', 0),
    ('embed-start', f'https://www.youtube.com/embed/{VIDEO_ID}?start=90', 90),
    ('nocookie', f'https://www.youtube-nocookie.com/embed/{VIDEO_ID}?start=12', 12),
    ('nocookie-без-www', f'https://youtube-nocookie.com/embed/{VIDEO_ID}', 0),
)


class YoutubeParserTests(TestCase):
    def test_кожен_формат(self):
        for label, url, start in YOUTUBE_CASES:
            with self.subTest(label=label):
                video_id, parsed_start = parse_youtube_url(url)
                self.assertEqual(video_id, VIDEO_ID)
                self.assertEqual(parsed_start, start)
                embed = youtube_embed_url(url)
                self.assertIn(f'/embed/{VIDEO_ID}', embed)
                if start:
                    self.assertIn(f'start={start}', embed)
                else:
                    self.assertNotIn('start=', embed)

    def test_невалідне_посилання(self):
        for url in (
            'https://example.com/watch?v=dQw4w9WgXcQ',
            'https://vimeo.com/123456789',
            'https://www.youtube.com/watch?v=short',
            'https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw',
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    parse_youtube_url(url)


class ProductVideoValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Статуетка',
            slug='statuetka-youtube',
            sku='YT-1',
            description='Опис',
            price='100.00',
        )

    def _video(self, url='', file=None):
        return ProductVideo(
            product=self.product,
            video_url=url,
            video_file=file or '',
            order=0,
        )

    def test_модель_приймає_кожен_формат(self):
        for label, url, start in YOUTUBE_CASES:
            with self.subTest(label=label):
                video = self._video(url)
                video.full_clean()
                if start:
                    self.assertIn(f'?start={start}', video.embed_url)
                else:
                    self.assertNotIn('start=', video.embed_url)

    def test_невалідне_посилання_українською(self):
        video = self._video('https://example.com/video')
        with self.assertRaises(ValidationError) as caught:
            video.full_clean()
        self.assertIn(YOUTUBE_URL_ERROR, caught.exception.message_dict['video_url'])

    def test_форма_невалідне_посилання(self):
        form = ProductVideoForm(data={
            'product': self.product.pk,
            'video_url': 'https://example.com/video',
            'order': 0,
        })
        self.assertFalse(form.is_valid())
        self.assertIn(YOUTUBE_URL_ERROR, form.errors['video_url'])

    def test_форма_сирий_текст(self):
        form = ProductVideoForm(data={
            'product': self.product.pk,
            'video_url': 'це не посилання',
            'order': 0,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('Вкажіть коректне посилання на YouTube.', form.errors['video_url'])

    def test_файл_без_посилання(self):
        video = self._video(file=SimpleUploadedFile('clip.mp4', b'video', content_type='video/mp4'))
        video.full_clean()

    def test_embed_на_сторінці(self):
        ProductVideo.objects.create(
            product=self.product,
            video_url=f'https://www.youtube.com/watch?v={VIDEO_ID}&t=1m30s',
            order=0,
        )
        url = reverse('products:detail', kwargs={'slug': self.product.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'data-embed="https://www.youtube.com/embed/{VIDEO_ID}?start=90"',
        )

    def test_referrer_policy_для_youtube_embed(self):
        ProductVideo.objects.create(
            product=self.product,
            video_url=f'https://www.youtube.com/watch?v={VIDEO_ID}',
            order=0,
        )
        url = reverse('products:detail', kwargs={'slug': self.product.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get('Referrer-Policy'),
            'strict-origin-when-cross-origin',
        )

    def test_gallery_js_має_referrerpolicy_на_iframe(self):
        from pathlib import Path

        from django.conf import settings

        gallery_js = Path(settings.BASE_DIR) / 'static' / 'js' / 'gallery.js'
        content = gallery_js.read_text(encoding='utf-8')
        self.assertIn(
            "setAttribute('referrerpolicy', 'strict-origin-when-cross-origin')",
            content,
        )
