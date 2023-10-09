from collections import defaultdict

from sleeperbot.clients.session import Session
from sleeperbot.config import Config
from sleeperbot.models import (
    LeagueSettings,
    Matchup,
    Owner,
    Player,
    Roster,
    Team,
)
from sleeperbot.utils import memoize

_config = Config()

_graphql = Session()
_graphql.headers.update(
    {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Authorization": _config.SLEEPER_TOKEN,
    }
)

_rest = Session()


@memoize()
def get_my_user_id() -> str:
    """Use the provided token to figure out the corresponding user ID"""
    resp = _graphql.post(
        "https://sleeper.com/graphql",
        json={
            "operationName": "initialize_app",
            "variables": {},
            "query": """
                query initialize_app {
                    me {
                        user_id
                    }
                }
            """,
        },
    )

    body = resp.json()

    if "errors" in body:
        raise RuntimeError(body["errors"])

    return body["data"]["me"]["user_id"]


@memoize()
def get_league_settings() -> LeagueSettings:
    nfl_state = _rest.get("https://api.sleeper.app/v1/state/nfl").json()
    league_state = _rest.get(f"https://api.sleeper.app/v1/league/{_config.SLEEPER_LEAGUE_ID}").json()

    return LeagueSettings(
        guid=_config.SLEEPER_LEAGUE_ID,
        name=league_state["name"],
        status=league_state["status"],
        week=int(nfl_state["leg"]),
        season=int(nfl_state["season"]),
        total_teams=int(league_state["total_rosters"]),
        roster_positions=league_state["roster_positions"],
        taxi_slots=league_state["settings"]["taxi_slots"],
        reserve_slots=league_state["settings"]["reserve_slots"],
        ppr=league_state["scoring_settings"]["rec"],
    )


@memoize()
def get_owners() -> list[Owner]:
    def map_owner(user) -> Owner:
        return Owner(
            guid=user["user_id"],
            display_name=user["display_name"],
            avatar=user["avatar"],
        )

    _users = _rest.get(f"https://api.sleeper.app/v1/league/{_config.SLEEPER_LEAGUE_ID}/users").json()

    return [map_owner(user) for user in _users]


@memoize()
def get_rosters() -> list[Roster]:
    def map_roster(roster) -> Roster:
        bench_ids = (
            set(roster["players"])
            - set(roster["starters"] or [])
            - set(roster["reserve"] or [])
            - set(roster["taxi"] or [])
        )

        return Roster(
            guid=str(roster["roster_id"]),
            owners=[roster["owner_id"]] + (roster["co_owners"] or []),
            starters=roster["starters"],
            reserve=roster["reserve"],
            taxi=roster["taxi"],
            bench=list(bench_ids),
            player_ids=roster["players"],
        )

    _rosters = _rest.get(f"https://api.sleeper.app/v1/league/{_config.SLEEPER_LEAGUE_ID}/rosters").json()

    return [map_roster(roster) for roster in _rosters]


@memoize()
def get_matchups(week: int) -> list[Matchup]:
    matchups = _rest.get(f"https://api.sleeper.app/v1/league/{_config.SLEEPER_LEAGUE_ID}/matchups/{str(week)}").json()

    # matchups are singular by matchup_id can be used to group the pairs
    _matchups: dict[str, list] = defaultdict(list)

    for matchup in matchups:
        _matchups[matchup["matchup_id"]] += [matchup]

    def map_matchup(guid, matchups) -> Matchup:
        return Matchup(
            guid=guid,
            home_roster=str(matchups[0]["roster_id"]),
            away_roster=str(matchups[1]["roster_id"]),
        )

    return [map_matchup(guid, matchups) for guid, matchups in _matchups.items()]


@memoize(ttl=24 * 3600)  # api docs ask to not hit this API more than once a day :shrug:
def get_player_map() -> dict[str, Player]:
    def map_player(player) -> Player:
        return Player(
            guid=player["player_id"],
            status=player.get("status"),
            injury_status=player["injury_status"],
            position=player["position"],
            number=player.get("number"),
            first_name=player["first_name"],
            last_name=player["last_name"],
            team=player["team"],
        )

    return {
        player_id: map_player(player)
        for player_id, player in _rest.get("https://api.sleeper.app/v1/players/nfl").json().items()
        if player.get("active")
    }


@memoize()
def get_teams() -> list[Team]:
    resp = _graphql.post(
        "https://sleeper.com/graphql",
        json={
            "operationName": "teams",
            "variables": {},
            "query": """
                query teams {
                    teams(sport: "nfl") {
                        active
                        aliases
                        metadata
                        name
                        sport
                        team
                    }
                }
            """,
        },
    )

    body = resp.json()

    if "errors" in body:
        raise RuntimeError(body["errors"])

    def map_team(team) -> Team:
        return Team(guid=team["team"], name=team["name"], bye_week=int(team["metadata"]["bye_week"]))

    return [map_team(team) for team in body["data"]["teams"]]
