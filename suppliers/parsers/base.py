"""Контракт парсера фіду."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterator

from suppliers.constants import MAX_STORED_ERRORS


@dataclass(frozen=True)
class FeedItem:
    id: str
    title: str
    price: Decimal
    currency: str
    available: bool


class BaseFeedParser:
    """parse(stream) віддає валідні позиції. Помилки рядків лишаються в errors."""

    def __init__(self):
        self.errors: list[str] = []
        self.error_count = 0
        self.skipped_empty = 0

    def add_error(self, message: str) -> None:
        self.error_count += 1
        if len(self.errors) < MAX_STORED_ERRORS:
            self.errors.append(message)

    def parse(self, stream) -> Iterator[FeedItem]:
        raise NotImplementedError
