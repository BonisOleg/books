"""Google Merchant RSS: g:id, title, g:price, g:availability."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Iterator

from suppliers.constants import FEED_GOOGLE_MERCHANT_RSS, GOOGLE_MERCHANT_NS
from suppliers.exceptions import FeedParseError, PriceParseError
from suppliers.parsers.base import BaseFeedParser, FeedItem
from suppliers.parsers.prices import parse_feed_price
from suppliers.parsers.registry import register_parser
from suppliers.parsers.xmlstream import guarded_xml_stream

_OUT = {'out of stock', 'oos', 'sold out'}


def _local(tag) -> str:
    if not isinstance(tag, str):
        return ''
    return tag.rpartition('}')[2]


def _available(raw: str) -> bool:
    value = ' '.join((raw or '').replace('_', ' ').split()).casefold()
    return value not in _OUT


def _read_item(elem) -> tuple[str, str, str, str]:
    item_id = ''
    title = ''
    g_title = ''
    price = ''
    availability = ''
    ns_prefix = '{' + GOOGLE_MERCHANT_NS + '}'
    for child in list(elem):
        tag = child.tag
        if not isinstance(tag, str):
            continue
        local = _local(tag)
        text = (child.text or '').strip()
        namespaced = tag.startswith(ns_prefix)
        if local == 'id' and namespaced and text and not item_id:
            item_id = text
        elif local == 'title' and text:
            if tag == 'title' and not title:
                title = text
            elif namespaced and not g_title:
                g_title = text
        elif local == 'price' and namespaced and text and not price:
            price = text
        elif local == 'availability' and namespaced and text and not availability:
            availability = text
    return item_id, title or g_title, price, availability


@register_parser(FEED_GOOGLE_MERCHANT_RSS)
class GoogleMerchantRSSParser(BaseFeedParser):
    def parse(self, stream) -> Iterator[FeedItem]:
        try:
            safe = guarded_xml_stream(stream)
            for event, elem in ET.iterparse(safe, events=('end',)):
                if _local(elem.tag) != 'item':
                    continue
                try:
                    item = self._item(elem)
                finally:
                    elem.clear()
                if item is not None:
                    yield item
        except FeedParseError:
            raise
        except ET.ParseError as exc:
            raise FeedParseError(f'Не вдалося розібрати XML: {exc}') from exc
        finally:
            if self.skipped_empty:
                self.add_error(f'Пропущено позицій без коду: {self.skipped_empty}.')

    def _item(self, elem) -> FeedItem | None:
        item_id, title, price_raw, availability = _read_item(elem)
        label = item_id or title or 'позиція'
        if not price_raw:
            self.add_error(f'{label}: немає g:price')
            return None
        try:
            amount, currency = parse_feed_price(price_raw)
        except PriceParseError as exc:
            self.add_error(f'{label}: {exc}')
            return None
        if not item_id.strip():
            self.skipped_empty += 1
            return None
        return FeedItem(
            id=item_id.strip(),
            title=title,
            price=amount,
            currency=currency,
            available=_available(availability),
        )
