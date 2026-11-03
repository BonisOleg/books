"""sameAs головної: Instagram OFION і без плейсхолдера Telegram."""
from __future__ import annotations

import importlib
import json
import re

from django.apps import apps
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import SiteSettings

_migration = importlib.import_module(
    'core.migrations.0018_sitesettings_instagram_and_telegram',
)
INSTAGRAM_URL = _migration.INSTAGRAM_URL
noop_reverse = _migration.noop_reverse
set_ofion_social_urls = _migration.set_ofion_social_urls
from core.seo import get_home_json_ld, is_placeholder_social_url

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'home-sameas',
    }
}


def _same_as_from_html(html: str) -> list[str]:
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>',
        html,
        re.S,
    )
    if match is None:
        return []
    data = json.loads(match.group(1))
    graph = data.get('@graph') or []
    for node in graph:
        if node.get('@type') == 'Organization':
            return list(node.get('sameAs') or [])
    return []


class PlaceholderSocialUrlTests(TestCase):
    def test_telegram_roots_are_placeholders_profiles_are_not(self):
        self.assertTrue(is_placeholder_social_url('https://telegram.org'))
        self.assertTrue(is_placeholder_social_url('https://www.telegram.org/'))
        self.assertTrue(is_placeholder_social_url('https://t.me'))
        self.assertTrue(is_placeholder_social_url('https://t.me/'))
        self.assertTrue(is_placeholder_social_url('http://www.t.me'))
        self.assertFalse(is_placeholder_social_url('https://t.me/ofion'))
        self.assertFalse(is_placeholder_social_url(INSTAGRAM_URL))
        self.assertFalse(is_placeholder_social_url(''))
        self.assertTrue(is_placeholder_social_url('https://instagram.com'))
        self.assertFalse(is_placeholder_social_url('https://facebook.com/ofion'))

    def test_json_ld_skips_placeholder_even_without_migration(self):
        site = SiteSettings(
            site_name='OFION',
            telegram_url='https://telegram.org/',
            instagram_url=INSTAGRAM_URL,
            facebook_url='https://facebook.com',
            youtube_url='https://www.youtube.com/@ofion',
        )
        same_as = get_home_json_ld(site)['@graph'][0]['sameAs']
        self.assertIn(INSTAGRAM_URL, same_as)
        self.assertIn('https://www.youtube.com/@ofion', same_as)
        self.assertFalse(any('telegram.org' in url for url in same_as))
        self.assertNotIn('https://facebook.com', same_as)

        site.telegram_url = 'https://t.me'
        same_as = get_home_json_ld(site)['@graph'][0]['sameAs']
        self.assertFalse(any(url.rstrip('/') == 'https://t.me' for url in same_as))

        site.telegram_url = 'https://t.me/ofion'
        same_as = get_home_json_ld(site)['@graph'][0]['sameAs']
        self.assertIn('https://t.me/ofion', same_as)


@override_settings(CACHES=LOC_MEM, SITE_DOMAIN='example.test', SITE_PROTOCOL='https')
class SocialUrlMigrationTests(TestCase):
    def test_sets_instagram_clears_placeholder_and_home_sameas(self):
        SiteSettings.objects.create(
            site_name='OFION',
            telegram_url='https://telegram.org',
            instagram_url='https://instagram.com/old',
            facebook_url='https://facebook.com/ofion',
        )
        set_ofion_social_urls(apps, None)
        site = SiteSettings.objects.get()
        self.assertEqual(site.instagram_url, INSTAGRAM_URL)
        self.assertEqual(site.telegram_url, '')

        same_as = get_home_json_ld(site)['@graph'][0]['sameAs']
        self.assertIn(INSTAGRAM_URL, same_as)
        self.assertIn('https://facebook.com/ofion', same_as)
        self.assertFalse(any('telegram.org' in url for url in same_as))

        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        page_same_as = _same_as_from_html(response.content.decode())
        self.assertIn(INSTAGRAM_URL, page_same_as)
        self.assertFalse(any('telegram.org' in url for url in page_same_as))

        before = SiteSettings.objects.values_list('instagram_url', 'telegram_url').get()
        noop_reverse(apps, None)
        after = SiteSettings.objects.values_list('instagram_url', 'telegram_url').get()
        self.assertEqual(before, after)

    def test_keeps_telegram_profile_and_missing_settings(self):
        set_ofion_social_urls(apps, None)
        self.assertFalse(SiteSettings.objects.exists())

        SiteSettings.objects.create(
            site_name='OFION',
            telegram_url='https://t.me/ofion_channel',
            instagram_url='',
        )
        set_ofion_social_urls(apps, None)
        site = SiteSettings.objects.get()
        self.assertEqual(site.telegram_url, 'https://t.me/ofion_channel')
        self.assertEqual(site.instagram_url, INSTAGRAM_URL)
        same_as = get_home_json_ld(site)['@graph'][0]['sameAs']
        self.assertIn(INSTAGRAM_URL, same_as)
        self.assertIn('https://t.me/ofion_channel', same_as)
        self.assertFalse(any('telegram.org' in url for url in same_as))
