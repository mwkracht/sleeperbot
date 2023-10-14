import functools
import hashlib
import logging
import sys

import structlog

from sleeperbot import config
from sleeperbot.models import (
    deserialize,
    serialize,
)

DEFAULT_TTL = 3600


def setup_logging():
    logging.basicConfig(
        level=config.LOG_LEVEL.upper(),
        format="%(message)s",
        stream=sys.stdout,
    )

    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if config.LOG_CONSOLE:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


class InMemoryCache:
    def __init__(self):
        self._cache = {}

    def exists(self, key: str) -> bool:
        return key in self._cache

    def set(self, key: str, value: str):
        self._cache[key] = value.encode()

    def expire(self, key: str, ttl: int):
        ...

    def get(self, key: str) -> bytes:
        return self._cache[key]


def memoize(ttl=DEFAULT_TTL):
    _cache = config.redis or InMemoryCache()

    def outer(func):
        def hash_args(args, kwargs):
            raw_bytes = serialize([args, kwargs], sort_keys=True).encode()

            unsecure_hash = hashlib.new("md5", usedforsecurity=False)
            unsecure_hash.update(raw_bytes)

            return unsecure_hash.hexdigest()

        @functools.wraps(func)
        def inner(*args, **kwargs):
            cache_key = f"memoize_{func.__module__}_{func.__name__}_{hash_args(args, kwargs)}"

            if _cache.exists(cache_key):
                return deserialize(_cache.get(cache_key).decode())

            result = func(*args, **kwargs)

            _cache.set(cache_key, serialize(result))
            _cache.expire(cache_key, ttl)

            return result

        return inner

    return outer
