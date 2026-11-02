import io
from decimal import Decimal

from django.test import SimpleTestCase

from suppliers.exceptions import FeedParseError, PriceParseError
from suppliers.parsers.google_merchant import GoogleMerchantRSSParser
from suppliers.parsers.prices import parse_feed_price

from .utils import FIXTURE, feed_bytes


class PriceParseTests(SimpleTestCase):
    def test_merchant_price_formats(self):
        self.assertEqual(parse_feed_price('28630 UAH'), (Decimal('28630'), 'UAH'))
        self.assertEqual(parse_feed_price('28630.00 UAH'), (Decimal('28630.00'), 'UAH'))
        self.assertEqual(parse_feed_price('28 630,50 UAH'), (Decimal('28630.50'), 'UAH'))
        self.assertEqual(parse_feed_price('28\u00a0630,50 UAH'), (Decimal('28630.50'), 'UAH'))
        self.assertEqual(parse_feed_price('28630,50 uah'), (Decimal('28630.50'), 'UAH'))

    def test_rejects_non_uah_and_garbage(self):
        with self.assertRaises(PriceParseError):
            parse_feed_price('10 USD')
        with self.assertRaises(PriceParseError):
            parse_feed_price('немає UAH')
        with self.assertRaises(PriceParseError):
            parse_feed_price('')


class GoogleMerchantParserTests(SimpleTestCase):
    def test_kupola_fixture(self):
        parser = GoogleMerchantRSSParser()
        with FIXTURE.open('rb') as handle:
            items = list(parser.parse(handle))
        by_id = {item.id: item for item in items}
        self.assertEqual(len(items), 4)
        self.assertEqual(by_id['4812345001001'].price, Decimal('28630'))
        self.assertEqual(by_id['4812345001001'].title, 'Купол церковний малий')
        self.assertTrue(by_id['4812345001001'].available)
        self.assertEqual(by_id['4812345001001'].currency, 'UAH')
        self.assertEqual(by_id['4812345001002'].price, Decimal('28630.00'))
        self.assertTrue(by_id['4812345001002'].available)
        self.assertEqual(by_id['4812345001003'].price, Decimal('28630.50'))
        self.assertFalse(by_id['4812345001003'].available)
        self.assertEqual(by_id['4812345001004'].price, Decimal('999.49'))
        self.assertTrue(by_id['4812345001004'].available)
        self.assertEqual(parser.error_count, 0)

    def test_plain_title_wins_over_g_title(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel>
          <item>
            <g:id>A</g:id>
            <title>RSS назва</title>
            <g:title>G назва</g:title>
            <g:price>10 UAH</g:price>
          </item>
          <item>
            <g:id>B</g:id>
            <g:title>Лише G</g:title>
            <g:price>11 UAH</g:price>
          </item>
        </channel></rss>'''
        parser = GoogleMerchantRSSParser()
        items = list(parser.parse(io.BytesIO(xml.encode())))
        self.assertEqual([item.title for item in items], ['RSS назва', 'Лише G'])

    def test_invalid_rows_are_skipped(self):
        parser = GoogleMerchantRSSParser()
        items = list(parser.parse(feed_bytes([
            {'id': 'OK', 'price': '15 UAH'},
            {'id': 'USD', 'price': '15 USD'},
            {'id': 'BAD', 'price': 'багато UAH'},
            {'id': '   ', 'price': '9 UAH', 'title': 'Порожній код'},
        ])))
        self.assertEqual([item.id for item in items], ['OK'])
        self.assertGreaterEqual(parser.error_count, 2)
        self.assertTrue(any('USD' in message for message in parser.errors))
        self.assertTrue(any('без коду' in message for message in parser.errors))

    def test_doctype_is_rejected(self):
        xml = b'<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY x "y">]><rss></rss>'
        parser = GoogleMerchantRSSParser()
        with self.assertRaises(FeedParseError):
            list(parser.parse(io.BytesIO(xml)))

    def test_broken_xml_is_rejected(self):
        parser = GoogleMerchantRSSParser()
        with self.assertRaises(FeedParseError):
            list(parser.parse(io.BytesIO(b'<rss><channel><item></rss>')))
