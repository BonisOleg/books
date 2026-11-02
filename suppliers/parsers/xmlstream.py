"""Потік XML без DTD: захист від entity-бомб на початку документа."""

from __future__ import annotations

from suppliers.exceptions import FeedParseError


class PrefixStream:
    def __init__(self, prefix, stream):
        self._prefix = prefix
        self._stream = stream
        self._offset = 0

    def read(self, size=-1):
        remaining = self._prefix[self._offset:]
        if size is None or size < 0:
            self._offset = len(self._prefix)
            return remaining + self._stream.read()
        if self._offset < len(self._prefix):
            take = remaining[:size]
            self._offset += len(take)
            if len(take) < size:
                take += self._stream.read(size - len(take))
            return take
        return self._stream.read(size)


def guarded_xml_stream(stream):
    prefix = stream.read(2048)
    if prefix is None:
        prefix = b''
    if isinstance(prefix, str):
        dangerous = '<!doctype' in prefix.lower() or '<!entity' in prefix.lower()
    else:
        lowered = prefix.lower()
        dangerous = b'<!doctype' in lowered or b'<!entity' in lowered
    if dangerous:
        raise FeedParseError('Небезпечний XML: DTD заборонено.')
    return PrefixStream(prefix, stream)
