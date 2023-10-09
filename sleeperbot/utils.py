import functools
import hashlib

from sleeperbot.config import Config
from sleeperbot.models import (
    deserialize,
    serialize,
)

DEFAULT_TTL = 3600

_config = Config()


def memoize(ttl=DEFAULT_TTL):
    def outer(func):
        def hash_args(args, kwargs):
            raw_bytes = serialize([args, kwargs], sort_keys=True).encode()

            unsecure_hash = hashlib.new("md5", usedforsecurity=False)
            unsecure_hash.update(raw_bytes)

            return unsecure_hash.hexdigest()

        @functools.wraps(func)
        def inner(*args, **kwargs):
            cache_key = f"memoize_{func.__module__}_{func.__name__}_{hash_args(args, kwargs)}"

            if _config.redis.exists(cache_key):
                return deserialize(_config.redis.get(cache_key).decode())

            result = func(*args, **kwargs)

            _config.redis.set(cache_key, serialize(result))
            _config.redis.expire(cache_key, ttl)

            return result

        return inner

    return outer
