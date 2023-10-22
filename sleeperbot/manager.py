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

    if config.MANAGE_ROSTER:
        league.me.roster, drop_players = league.optimize_roster(league.me.roster)

        if drop_players:
            # sleeper requires all non-IR illegible players to be moved from IR and
            # roster size to be correct before starters can be adjusted
            sleeper.drop_players(league.settings, league.me.roster, drop_players)

        sleeper.update_injured_reserve(league, league.me.roster)

        sleeper.update_starters(league, league.me.roster)

        if config.MANAGE_TAXI:
            sleeper.update_taxi(league, league.me.roster)

    log.info("sleeperbot manager complete")


def main():
    return manage()


if __name__ == "__main__":
    main()
