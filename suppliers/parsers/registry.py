"""Реєстр парсерів за кодом feed_format."""

from __future__ import annotations

from suppliers.exceptions import UnsupportedFeedFormat
from suppliers.parsers.base import BaseFeedParser

PARSERS: dict[str, type[BaseFeedParser]] = {}
_LOADED = False


def register_parser(feed_format: str):
    def decorator(cls):
        PARSERS[feed_format] = cls
        return cls
    return decorator


def ensure_parsers_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    from suppliers.parsers import google_merchant  # noqa: F401


def get_parser(feed_format: str) -> BaseFeedParser:
    ensure_parsers_loaded()
    try:
        cls = PARSERS[feed_format]
    except KeyError as exc:
        raise UnsupportedFeedFormat(f'Невідомий формат фіду: {feed_format}') from exc
    return cls()
