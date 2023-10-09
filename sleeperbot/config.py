import os
from dataclasses import (
    dataclass,
    field,
)

import redis


def load_from_env(name, tipe=str, required=False, default=None):
    def loader():
        if name not in os.environ:
            if required:
                raise RuntimeError(f"Environment variable {name} is required!")
            else:
                return default

        value = os.environ[name]

        return tipe(value)

    return field(default_factory=loader)


@dataclass
class Config:
    SLEEPER_TOKEN: str = load_from_env("SLEEPER_TOKEN", required=True)
    SLEEPER_LEAGUE_ID: str = load_from_env("SLEEPER_LEAGUE_ID", required=True)

    REDIS_HOST: str = load_from_env("REDIS_HOST", required=True)
    REDIS_PORT: int = load_from_env("REDIS_PORT", required=True, tipe=int)
    REDIS_DB: int = load_from_env("REDIS_DB", tipe=int, default=0)

    WEIGHT_KTC: float = load_from_env("WEIGHT_KTC", tipe=float, default=1.0)
    WEIGHT_FANTASY_CALC: float = load_from_env("WEIGHT_FANTASY_CALC", tipe=float, default=1.0)

    @property
    def redis(self):
        if not hasattr(self, "_redis"):
            self._redis = redis.Redis(host=self.REDIS_HOST, port=self.REDIS_PORT, db=self.REDIS_DB)

        return self._redis
