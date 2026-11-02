"""План синхронізації без прив'язки до відкритого фіду."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class PriceChange:
    product_id: int
    name: str
    code: str
    old: Decimal
    new: Decimal


@dataclass
class MissingInFeed:
    product_id: int
    name: str
    code: str
    sku: str


@dataclass
class MissingInCatalog:
    code: str
    title: str
    price: Decimal


@dataclass
class SyncPlan:
    items_in_feed: int = 0
    matched: int = 0
    price_changes: list[PriceChange] = field(default_factory=list)
    not_in_feed: list[MissingInFeed] = field(default_factory=list)
    not_in_catalog: list[MissingInCatalog] = field(default_factory=list)
    mark_out_ids: list[int] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)
    error_count: int = 0

    @property
    def price_changed(self) -> int:
        return len(self.price_changes)

    @property
    def marked_out(self) -> int:
        return len(self.mark_out_ids)
