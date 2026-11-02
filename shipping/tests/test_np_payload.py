from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from shipping.models import NPTTNSettings, ShipmentOrigin
from shipping.np_ttn import build_internet_document_payload
from shipping.tests.factories import order, origin, ttn_settings


@override_settings(NOVAPOSHTA_API_KEY='')
class InternetDocumentPayloadTests(TestCase):
    def setUp(self):
        self.origin = origin()
        self.settings = ttn_settings()
        self.order = order(shipment_origin=self.origin)

    def _payload(self, **order_kwargs):
        if order_kwargs:
            for key, value in order_kwargs.items():
                setattr(self.order, key, value)
            self.order.save()
        with patch('shipping.np_ttn.requests.post') as post:
            payload = build_internet_document_payload(self.order, self.settings)
        post.assert_not_called()
        return payload

    def test_warehouse_and_postomat_payload(self):
        payload = self._payload()
        self.assertEqual(payload['ServiceType'], 'WarehouseWarehouse')
        self.assertEqual(payload['SeatsAmount'], '1')
        self.assertEqual(payload['Cost'], '150.00')
        self.assertEqual(payload['Weight'], '0.5')
        self.assertEqual(payload['CargoType'], 'Parcel')
        self.assertEqual(payload['PayerType'], 'Recipient')
        self.assertEqual(payload['PaymentMethod'], 'Cash')
        self.assertEqual(payload['Description'], 'Книги')
        self.assertEqual(payload['DateTime'], timezone.localdate().strftime('%d.%m.%Y'))
        self.assertEqual(payload['CitySender'], 'city-ref')
        self.assertEqual(payload['Sender'], 'sender-ref')
        self.assertEqual(payload['SenderAddress'], 'sender-wh')
        self.assertEqual(payload['ContactSender'], 'contact-ref')
        self.assertEqual(payload['SendersPhone'], '380671112233')
        self.assertEqual(payload['RecipientName'], 'Петренко Іван Іванович')
        self.assertEqual(payload['RecipientType'], 'PrivatePerson')
        self.assertEqual(payload['RecipientsPhone'], '380501112233')
        self.assertEqual(payload['RecipientCityName'], 'Київ')
        self.assertEqual(payload['RecipientAddressName'], '12')
        self.assertEqual(payload['RecipientWarehouseIndex'], 'recip-wh')
        self.assertEqual(payload['RecipientAddress'], 'recip-wh')
        self.assertEqual(payload['AfterpaymentOnGoodsCost'], '150.00')
        self.assertNotIn('BackwardDeliveryData', payload)
        self.assertEqual(payload['OptionsSeat'], [{
            'volumetricWidth': '15',
            'volumetricLength': '20',
            'volumetricHeight': '10',
            'weight': '0.5',
        }])

    def test_recipient_address_payload(self):
        self.order.warehouse = ''
        self.order.warehouse_ref = ''
        self.order.recipient_area = 'Київська'
        self.order.recipient_street = 'Хрещатик'
        self.order.recipient_house = '1'
        self.order.recipient_flat = '10'
        self.order.payment_method = 'liqpay'
        self.order.payment_status = 'paid'
        self.order.save()
        payload = self._payload()
        self.assertEqual(payload['ServiceType'], 'WarehouseDoors')
        self.assertEqual(payload['NewAddress'], '1')
        self.assertEqual(payload['RecipientArea'], 'Київська')
        self.assertEqual(payload['RecipientCityName'], 'Київ')
        self.assertEqual(payload['RecipientAddressName'], 'Хрещатик')
        self.assertEqual(payload['RecipientHouse'], '1')
        self.assertEqual(payload['RecipientFlat'], '10')
        self.assertNotIn('RecipientWarehouseIndex', payload)
        self.assertNotIn('RecipientAddress', payload)
        self.assertNotIn('AfterpaymentOnGoodsCost', payload)
        self.assertNotIn('BackwardDeliveryData', payload)
        self.assertEqual(payload['SenderAddress'], 'sender-wh')

    def test_address_pickup_payload(self):
        self.origin.kind = ShipmentOrigin.KIND_ADDRESS
        self.origin.street_ref = 'street-ref'
        self.origin.street_name = 'Золотоустівська'
        self.origin.building = '10-12'
        self.origin.warehouse_ref = ''
        self.origin.save()
        payload = self._payload()
        self.assertEqual(payload['ServiceType'], 'DoorsWarehouse')
        self.assertEqual(payload['SenderAddress'], 'street-ref')
        self.assertEqual(payload['CitySender'], 'city-ref')
        self.assertEqual(payload['RecipientWarehouseIndex'], 'recip-wh')

    def test_doors_to_doors(self):
        self.origin.kind = ShipmentOrigin.KIND_ADDRESS
        self.origin.street_ref = 'street-ref'
        self.origin.warehouse_ref = ''
        self.origin.save()
        self.order.warehouse = ''
        self.order.warehouse_ref = ''
        self.order.recipient_street = 'Хрещатик'
        self.order.recipient_house = '2'
        self.order.payment_method = 'manager'
        self.order.save()
        payload = self._payload()
        self.assertEqual(payload['ServiceType'], 'DoorsDoors')
        self.assertEqual(payload['SenderAddress'], 'street-ref')
        self.assertNotIn('AfterpaymentOnGoodsCost', payload)
        self.assertNotIn('BackwardDeliveryData', payload)

    def test_backward_cod_uses_cod_payer(self):
        self.settings.cod_mode = NPTTNSettings.COD_BACKWARD
        self.settings.cod_payer_type = 'Sender'
        self.settings.payer_type = 'Recipient'
        self.settings.save()
        payload = self._payload()
        self.assertEqual(payload['PayerType'], 'Recipient')
        self.assertEqual(payload['BackwardDeliveryData'], [{
            'PayerType': 'Sender',
            'CargoType': 'Money',
            'RedeliveryString': '150.00',
        }])
        self.assertNotIn('AfterpaymentOnGoodsCost', payload)

    def test_order_dimensions_override_defaults(self):
        self.order.parcel_weight = Decimal('2.250')
        self.order.parcel_length = 30
        self.order.parcel_width = 25
        self.order.parcel_height = 8
        self.order.payment_method = 'liqpay'
        self.order.payment_status = 'paid'
        self.order.save()
        payload = self._payload()
        self.assertEqual(payload['Weight'], '2.25')
        self.assertEqual(payload['OptionsSeat'][0]['volumetricLength'], '30')
        self.assertEqual(payload['OptionsSeat'][0]['volumetricWidth'], '25')
        self.assertEqual(payload['OptionsSeat'][0]['volumetricHeight'], '8')
        self.assertEqual(payload['OptionsSeat'][0]['weight'], '2.25')
        self.assertNotIn('AfterpaymentOnGoodsCost', payload)
