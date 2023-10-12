from sleeperbot.clients import sleeper
from sleeperbot.config import Config
from sleeperbot.league import League


def manager():
    config = Config()
    league = League()

    if config.MANAGE_ROSTER:
        optimal_roster = league.optimize_roster(league.me.roster)
        league.me.roster = sleeper.update_roster(league, optimal_roster)


def main():
    return manager()


if __name__ == "__main__":
    main()
