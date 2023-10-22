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

        if tipe == bool:
            if value.lower() in ("false", "f"):
                return False
            elif value.lower() in ("true", "t"):
                return True

            return default

        return tipe(value)

    return field(default_factory=loader)


@dataclass
class Config:
    SLEEPER_TOKEN: str = load_from_env("SLEEPER_TOKEN", required=True)
    SLEEPER_LEAGUE_ID: str = load_from_env("SLEEPER_LEAGUE_ID", required=True)

    REDIS_HOST: str = load_from_env("REDIS_HOST", tipe=str, default="")
    REDIS_PORT: int = load_from_env("REDIS_PORT", tipe=int, default=6379)
    REDIS_DB: int = load_from_env("REDIS_DB", tipe=int, default=0)
    REDIS_SSL: bool = load_from_env("REDIS_ENABLE_SSL", tipe=bool, default=False)

    WEIGHT_KTC: float = load_from_env("WEIGHT_KTC", tipe=float, default=1.0)
    WEIGHT_FANTASY_CALC: float = load_from_env("WEIGHT_FANTASY_CALC", tipe=float, default=1.0)

    MANAGE_ROSTER: bool = load_from_env("MANAGE_ROSTER", tipe=bool, default=False)
    MANAGE_TAXI: bool = load_from_env("MANAGE_TAXI", tipe=bool, default=False)

    LOG_LEVEL: str = load_from_env("LOG_LEVEL", tipe=str, default="INFO")
    LOG_CONSOLE: bool = load_from_env("LOG_CONSOLE", tipe=bool, default=False)

    @property
    def redis(self) -> redis.Redis | None:
        if not self.REDIS_HOST:
            return None

        if not hasattr(self, "_redis"):
            self._redis = redis.Redis(
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                db=self.REDIS_DB,
                ssl=self.REDIS_SSL,
                ssl_cert_reqs=None,
            )

        return self._redis
