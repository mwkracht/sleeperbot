from sleeperbot.clients.session import Session
from sleeperbot.models import (
    LeagueSettings,
    Player,
    PlayerValue,
)
from sleeperbot.utils import memoize

_session = Session()
_session.headers.update(
    {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
    }
)

# some values can be above 10k but not by much...
MAX_VALUE = 10000


def _normalize_value(value: int) -> float:
    return value / MAX_VALUE


@memoize(ttl=600)
def get_players(dynasty: bool, settings: LeagueSettings) -> list[Player]:
    def map_player(player) -> Player:
        first, last = player["player"]["name"].split(maxsplit=1)

        _player = Player(
            guid=player["player"]["sleeperId"],
            position=player["player"]["position"],
            first_name=first,
            last_name=last,
            team=player["player"]["maybeTeam"],
        )

        player_value = PlayerValue(
            values={"fantasy_calc": _normalize_value(player["value"])},
            trends={"fantasy_calc": _normalize_value(player["trend30Day"])},
        )

        if dynasty:
            _player.dynasty = player_value
        else:
            _player.redraft = player_value

        return _player

    resp = _session.get(
        "https://api.fantasycalc.com/values/current",
        params={
            "isDynasty": dynasty,
            "numQbs": 2 if settings.superflex else 1,
            "numTeams": settings.total_teams,
            "ppr": settings.ppr,
            "includeAdp": False,
        },
    )

    return [map_player(player) for player in resp.json()]
