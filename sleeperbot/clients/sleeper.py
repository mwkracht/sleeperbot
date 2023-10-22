import json
from collections import defaultdict

from sleeperbot import config
from sleeperbot.clients.session import Session
from sleeperbot.models import (
    Game,
    LeagueSettings,
    Matchup,
    Owner,
    Player,
    Roster,
    Team,
)
from sleeperbot.utils import memoize

_graphql = Session()
_graphql.headers.update(
    {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Authorization": config.SLEEPER_TOKEN,
    }
)

_rest = Session()


def _check_graphql_errors(response) -> dict:
    body = response.json()

    if "errors" in body:
        raise RuntimeError(body["errors"])

    return body


@memoize()
def get_my_user_id() -> str:
    """Use the provided token to figure out the corresponding user ID"""
    body = _check_graphql_errors(
        _graphql.post(
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
    )

    return body["data"]["me"]["user_id"]


@memoize()
def get_league_settings() -> LeagueSettings:
    nfl_state = _rest.get("https://api.sleeper.app/v1/state/nfl").json()
    league_state = _rest.get(f"https://api.sleeper.app/v1/league/{config.SLEEPER_LEAGUE_ID}").json()

    ppr = league_state["scoring_settings"]["rec"]
    te_ppr = ppr + (league_state["scoring_settings"].get("bonus_rec_te") or 0)

    return LeagueSettings(
        guid=config.SLEEPER_LEAGUE_ID,
        name=league_state["name"],
        status=league_state["status"],
        week=int(nfl_state["leg"]),
        season=int(nfl_state["season"]),
        total_teams=int(league_state["total_rosters"]),
        roster_positions=league_state["roster_positions"],
        taxi_slots=league_state["settings"]["taxi_slots"],
        reserve_slots=league_state["settings"]["reserve_slots"],
        ppr=ppr,
        te_ppr=te_ppr,
    )


@memoize()
def get_owners() -> list[Owner]:
    def map_owner(user) -> Owner:
        return Owner(
            guid=user["user_id"],
            display_name=user["display_name"],
            avatar=user["avatar"],
        )

    _users = _rest.get(f"https://api.sleeper.app/v1/league/{config.SLEEPER_LEAGUE_ID}/users").json()

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

    _rosters = _rest.get(f"https://api.sleeper.app/v1/league/{config.SLEEPER_LEAGUE_ID}/rosters").json()

    return [map_roster(roster) for roster in _rosters]


def drop_players(league: LeagueSettings, roster: Roster, player_ids: list[str]):
    _check_graphql_errors(
        _graphql.post(
            "https://sleeper.com/graphql",
            json={
                "operationName": "league_create_transaction",
                "variables": {
                    "k_adds": [],
                    "v_adds": [],
                    "k_drops": player_ids,
                    "v_drops": [int(roster.guid)],
                },
                "query": """
            mutation league_create_transaction($k_adds: [String], $v_adds: [Int], $k_drops: [String], $v_drops: [Int]) {{
                league_create_transaction(league_id: "{LEAGUE_ID}", type: "free_agent", k_adds: $k_adds, v_adds: $v_adds, k_drops: $k_drops, v_drops: $v_drops){{
                    adds
                    consenter_ids
                    created
                    creator
                    drops
                    league_id
                    leg
                    metadata
                    roster_ids
                    settings
                    status
                    status_updated
                    transaction_id
                    type
                    player_map
                }}
            }}
            """.format(
                    LEAGUE_ID=league.guid,
                ),
            },
        )
    )


def update_taxi(league: LeagueSettings, roster: Roster):
    _check_graphql_errors(
        _graphql.post(
            "https://sleeper.com/graphql",
            json={
                "operationName": "roster_update_taxi",
                "variables": {},
                "query": """
                mutation roster_update_taxi {{
                    roster_update_taxi(league_id: "{LEAGUE_ID}",roster_id: {ROSTER_ID},taxi: {TAXI}){{
                        league_id
                    }}
                }}
            """.format(
                    LEAGUE_ID=league.guid,
                    ROSTER_ID=roster.guid,
                    TAXI=json.dumps(roster.taxi),
                ),
            },
        )
    )


def update_injured_reserve(league: LeagueSettings, roster: Roster):
    _check_graphql_errors(
        _graphql.post(
            "https://sleeper.com/graphql",
            json={
                "operationName": "roster_update_reserve",
                "variables": {},
                "query": """
                mutation roster_update_reserve {{
                    roster_update_reserve(league_id: "{LEAGUE_ID}",roster_id: {ROSTER_ID},reserve: {RESERVES}){{
                        league_id
                    }}
                }}
            """.format(
                    LEAGUE_ID=league.guid,
                    ROSTER_ID=roster.guid,
                    RESERVES=json.dumps(roster.reserve),
                ),
            },
        )
    )


def update_starters(league: LeagueSettings, roster: Roster) -> Roster:
    _check_graphql_errors(
        _graphql.post(
            "https://sleeper.com/graphql",
            json={
                "operationName": "update_matchup_leg",
                "variables": {},
                "query": """
                mutation update_matchup_leg($starters_games: Map) {{
                    update_matchup_leg(league_id: "{LEAGUE_ID}",roster_id: {ROSTER_ID},leg: {WEEK},round: {WEEK},starters: {STARTERS},starters_games: $starters_games){{
                        league_id
                    }}
                }}
            """.format(
                    LEAGUE_ID=league.guid,
                    ROSTER_ID=roster.guid,
                    WEEK=league.week,
                    STARTERS=json.dumps(roster.starters),
                ),
            },
        )
    )

    return roster


@memoize()
def get_matchups(week: int) -> list[Matchup]:
    matchups = _rest.get(f"https://api.sleeper.app/v1/league/{config.SLEEPER_LEAGUE_ID}/matchups/{str(week)}").json()

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
def get_games() -> dict[str, Game]:
    league_settings = get_league_settings()

    body = _check_graphql_errors(
        _graphql.post(
            "https://sleeper.com/graphql",
            json={
                "operationName": "batch_scores",
                "variables": {},
                "query": """
                    query batch_scores {{
                        scores(sport: "nfl",season_type: "regular",season: "{SEASON}",week: {WEEK}){{
                            date
                            game_id
                            metadata
                            status
                            start_time
                        }}
                    }}
                """.format(SEASON=league_settings.season, WEEK=league_settings.week),
            },
        )
    )

    def map_game(game) -> Game:
        return Game(
            guid=game["game_id"],
            start_time=game["start_time"],
            teams=[game["metadata"]["home_team"], game["metadata"]["away_team"]],
            status=game["status"],
        )

    games = [map_game(game) for game in body["data"]["scores"]]

    return {team: game for game in games for team in game.teams}


@memoize()
def get_teams() -> list[Team]:
    body = _check_graphql_errors(
        _graphql.post(
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
    )

    games = get_games()

    def map_team(team) -> Team:
        return Team(
            guid=team["team"],
            name=team["name"],
            bye_week=int(team["metadata"]["bye_week"]),
            game=games.get(team["team"]),
        )

    return [map_team(team) for team in body["data"]["teams"]]
