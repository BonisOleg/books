from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from suppliers.exceptions import PriceComputeError
from suppliers.pricing import compute_price


def rule(**kwargs):
    data = {
        'price_rule': 'as_is',
        'markup_percent': Decimal('0'),
        'rounding': 'none',
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


class ComputePriceTests(SimpleTestCase):
    def test_as_is_rounds_half_up_to_cents_and_ignores_markup(self):
        self.assertEqual(compute_price(Decimal('10.126'), rule()), Decimal('10.13'))
        self.assertEqual(compute_price(Decimal('10.124'), rule()), Decimal('10.12'))
        self.assertEqual(compute_price(Decimal('1.005'), rule()), Decimal('1.01'))
        kept = compute_price(Decimal('100'), rule(markup_percent=Decimal('50')))
        self.assertEqual(kept, Decimal('100.00'))

    def test_markup_and_rounding(self):
        self.assertEqual(
            compute_price(Decimal('100'), rule(price_rule='markup', markup_percent=Decimal('10'))),
            Decimal('110.00'),
        )
        self.assertEqual(
            compute_price(Decimal('100'), rule(
                price_rule='markup', markup_percent=Decimal('15'), rounding='10',
            )),
            Decimal('120.00'),
        )
        self.assertEqual(
            compute_price(Decimal('100'), rule(
                price_rule='markup', markup_percent=Decimal('14'), rounding='10',
            )),
            Decimal('110.00'),
        )
        self.assertEqual(compute_price(Decimal('100.50'), rule(rounding='1')), Decimal('101.00'))
        self.assertEqual(compute_price(Decimal('100.49'), rule(rounding='1')), Decimal('100.00'))
        self.assertEqual(compute_price(Decimal('25'), rule(rounding='10')), Decimal('30.00'))
        self.assertEqual(compute_price(Decimal('24.99'), rule(rounding='10')), Decimal('20.00'))

    def test_negative_result_is_an_error(self):
        with self.assertRaises(PriceComputeError):
            compute_price(Decimal('10'), rule(price_rule='markup', markup_percent=Decimal('-200')))
