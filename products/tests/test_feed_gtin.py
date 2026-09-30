from django.test import SimpleTestCase

from products.feed_utils import _looks_like_internal_code, normalize_gtin


class NormalizeGtinTests(SimpleTestCase):
    def test_valid_ean13_and_isbn13(self):
        self.assertEqual(normalize_gtin('4006381333931'), '4006381333931')
        self.assertEqual(normalize_gtin('978-617-12-3456-7'), '9786171234567')

    def test_valid_isbn10_with_x(self):
        self.assertEqual(normalize_gtin('0-8044-2957-X'), '080442957X')
        self.assertEqual(normalize_gtin('0306406152'), '0306406152')

    def test_internal_codes_are_rejected(self):
        # Внутрішні коди: правильна довжина, хибна контрольна сума.
        for code in ('0302008064', '0303004041', '0302002152', '4006381333930'):
            self.assertIsNone(normalize_gtin(code), code)

    def test_internal_code_matching_sku_is_detected(self):
        # Проходить mod 11, але закінчується на SKU — внутрішній код.
        self.assertTrue(_looks_like_internal_code('0302008071', '8071'))
        self.assertTrue(_looks_like_internal_code('0305003003', 'SKU-3003'))
        self.assertFalse(_looks_like_internal_code('0306406152', '8071'))
        self.assertFalse(_looks_like_internal_code('9786171234567', '4567'))
        self.assertFalse(_looks_like_internal_code('0302008071', '71'))

    def test_garbage_is_rejected(self):
        for code in ('', None, 'abc', '12345', '123456789012'):
            self.assertIsNone(normalize_gtin(code), code)
