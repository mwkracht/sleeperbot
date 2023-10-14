import functools

import structlog

from sleeperbot import config
from sleeperbot.clients import sleeper
from sleeperbot.league import League
from sleeperbot.utils import setup_logging

log = structlog.get_logger()


def log_unhandled_errors(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            log.exception("Unhandled exception during manage")

    return inner


@log_unhandled_errors
def manage():
    setup_logging()

    log.info("running sleeperbot manager")
    league = League()

    league.me.roster = league.optimize_roster(league.me.roster)

    if config.MANAGE_STARTERS:
        sleeper.update_starters(league, league.me.roster)
    if config.MANAGE_TAXI:
        sleeper.update_taxi(league, league.me.roster)
    if config.MANAGE_INJURED_RESERVE:
        sleeper.update_injured_reserve(league, league.me.roster)

    log.info("sleeperbot manager complete")


def main():
    return manage()


if __name__ == "__main__":
    main()
