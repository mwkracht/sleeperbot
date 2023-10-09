import json
import re

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
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Host": "keeptradecut.com",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0"
            " Safari/537.36"
        ),
    }
)

MAX_VALUE = 10000

NAME_FIXES = {
    # ktc -> sleeper
    "Mitchell Trubisky": "Mitch Trubisky",
    "Jeffery Wilson": "Jeff Wilson",
    "D.J. Chark": "DJ Chark",
    "D.J. Moore": "DJ Moore",
    "Gabriel Davis": "Gabe Davis",
    "Josh Palmer": "Joshua Palmer",
    "Scotty Miller": "Scott Miller",
    "D'Wayne Eskridge": "Dee Eskridge",
}

TEAM_MAPPING = {
    # ktc -> sleeper
    "GBP": "GB",
    "LVR": "LV",
    "SFO": "SF",
    "KCC": "KC",
    "NOS": "NO",
    "FA": None,
    "JAC": "JAX",
    "NEP": "NE",
    "TBB": "TB",
}


def _normalize_name(name: str) -> tuple[str, str]:
    # key off playerName because we have no way to link IDs between sleeper and ktc -
    # player names are not exact matches either so we have to clean up names here

    name = NAME_FIXES.get(name, name)

    names = name.split()

    if names[-1] in ("Jr.", "Sr."):  # drop any suffixes
        names = names[:-1]
    elif not names[-1].replace("I", "").replace("V", ""):  # drop any roman numerals
        names = names[:-1]

    return names[0], " ".join(names[1:])


def _normalize_value(value: int) -> float:
    return value / MAX_VALUE


def _get_players(url) -> list[dict]:
    response = _session.get(url, timeout=10)

    matches = list(re.finditer(r"var playersArray = (.*);", response.text, re.MULTILINE))

    if len(matches) != 1:
        raise RuntimeError(f"Found {len(matches)} regex matches for keeptradecut source!")

    return json.loads(matches[0].groups()[0])


@memoize(ttl=24 * 3600)
def get_players(dynasty: bool, settings: LeagueSettings) -> list[Player]:
    url = f'https://keeptradecut.com/{"dynasty" if dynasty else "fantasy"}-rankings'

    def map_player(player) -> Player:
        first, last = _normalize_name(player["playerName"])

        _player = Player(
            guid=str(player["playerID"]),  # ktc has no mapping back to sleeper IDs...
            first_name=first,
            last_name=last,
            position=player["position"],
            number=player["number"],  # ktc also seems to hav esome wrong player numbers...
            team=TEAM_MAPPING.get(player["team"], player["team"]),  # and some teams wrong...
            bye_week=int(player["byeWeek"] or -1),
        )

        values = player.get("superflexValues") if settings.superflex else player.get("oneQBValues")
        values = values or {}

        player_value = PlayerValue(
            values={"ktc": _normalize_value(values["value"])},
            trends={"ktc": _normalize_value(values["overall7DayTrend"])},
        )

        if dynasty:
            _player.dynasty = player_value
        else:
            _player.redraft = player_value

        return _player

    return [map_player(player) for player in _get_players(url)]
