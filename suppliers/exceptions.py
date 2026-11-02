"""Помилки синхронізації, після яких каталог не змінюється."""


class FeedSyncError(Exception):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = list(details or [])


class FeedFetchError(FeedSyncError):
    pass


class FeedParseError(FeedSyncError):
    pass


class UnsupportedFeedFormat(FeedSyncError):
    pass


class PriceParseError(FeedSyncError):
    pass


class PriceComputeError(FeedSyncError):
    pass
