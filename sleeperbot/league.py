from datetime import datetime

import structlog

from sleeperbot.clients import (
    fantasy_calc,
    ktc,
    sleeper,
)
from sleeperbot.models import (
    Player,
    Roster,
)

log = structlog.get_logger()

# keys are roster positions that can be included in a starting
# lineup mapped to the roster positions that can fill that slot
LINEUP_POSITION_MAP = {
    "QB": ["QB"],
    "RB": ["RB"],
    "WR": ["WR"],
    "TE": ["TE"],
    "FLEX": ["RB", "WR", "TE"],
}


class League:
    def __init__(self):
        self.owners = {owner.guid: owner for owner in sleeper.get_owners()}

        my_user_id = sleeper.get_my_user_id()
        self.me = self.owners[my_user_id]

        self.settings = sleeper.get_league_settings()
        self.teams = {team.guid: team for team in sleeper.get_teams()}

        self.players = {}
        for player in sleeper.get_player_map().values():
            if player.position in self.settings.roster_positions:
                self.players[player.guid] = player
                self.players[player.alternate_id] = player

                try:
                    player.bye_week = self.teams[player.team].bye_week
                except KeyError:
                    pass

        matchups = sleeper.get_matchups(week=self.settings.week)

        for roster in sleeper.get_rosters():
            roster.players = [self.players[player_id] for player_id in roster.player_ids]

            matchup = next(matchup for matchup in matchups if roster.guid in (matchup.away_roster, matchup.home_roster))

            for owner in self.owners.values():
                if owner.guid in roster.owners:
                    owner.roster = roster
                    owner.matchup = matchup

        self._load_player_value()

    def _load_player_value(self):
        for player in fantasy_calc.get_players(dynasty=True, settings=self.settings):
            if player.position not in ("PICK",):
                self.players[player.guid].update_value(player)

        for player in fantasy_calc.get_players(dynasty=False, settings=self.settings):
            if player.position not in ("PICK",):
                self.players[player.guid].update_value(player)

        d_players = {player.alternate_id: player for player in ktc.get_players(dynasty=True, settings=self.settings)}
        r_players = {player.alternate_id: player for player in ktc.get_players(dynasty=False, settings=self.settings)}

        for player in self.players.values():
            dynasty = d_players.pop(player.alternate_id, {})
            if dynasty:
                player.update_value(dynasty)

            redraft = r_players.pop(player.alternate_id, {})
            if redraft:
                player.update_value(redraft)

        d_players = [p for p in d_players.values() if not p.first_name.isdigit()]  # filter out draft picks
        if len(d_players) > 0:
            raise RuntimeError("Unable to map all ktc player values!")

    def optimize_roster(self, roster: Roster):
        # the order of the IDs matches the order of self.settings.roster_positions - so if QB
        # is the first position in roster_positions then the first ID in starters must be a QB
        # or "0" which represents an empty position
        starters: list[str] = ["0"] * self.settings.starter_slots
        bench: list[str] = []
        reserve: list[str] = []
        taxi: list[str] = roster.taxi.copy()  # don't touch the taxi squad for now...
        movable_players: dict[str, Player] = {}

        for player in roster.players:
            if player.guid in taxi:
                continue

            if player.team in self.teams and self.teams[player.team].game:
                if self.teams[player.team].game.kickoff > datetime.utcnow():
                    movable_players[player.guid] = player
                elif player.guid in roster.starters:
                    starters[roster.starters.index(player.guid)] = player.guid
                elif player.guid in roster.bench:
                    bench.append(player.guid)
                elif player.guid in roster.reserve:
                    reserve.append(player.guid)
            else:
                movable_players[player.guid] = player

        # move players to IR and bye week/out players to the bench
        for player in list(movable_players.values()):
            if player.on_reserve and len(reserve) < self.settings.reserve_slots:
                reserve.append(player.guid)
                movable_players.pop(player.guid)

            elif not player.will_play:  # player is out this week
                bench.append(player.guid)
                movable_players.pop(player.guid)

            elif player.bye_week == self.settings.week:  # player is on bye this week
                bench.append(player.guid)
                movable_players.pop(player.guid)

            elif not player.team:  # player is a free agent...
                bench.append(player.guid)
                movable_players.pop(player.guid)

        sorted_players = sorted(movable_players.values(), key=lambda player: player.redraft, reverse=True)

        # fill out open starter slots with most value player that fits that position
        for idx, slot in enumerate(starters):
            if slot != "0":
                continue

            position = self.settings.roster_positions[idx]
            available_fills = LINEUP_POSITION_MAP[position]

            player = next(player for player in sorted_players if player.position in available_fills)
            movable_players.pop(player.guid)
            sorted_players.remove(player)
            starters[idx] = player.guid

        # all remaining movable players go to bench
        bench.extend(list(movable_players.keys()))

        return Roster(
            guid=roster.guid,
            owners=roster.owners,
            starters=starters,
            reserve=reserve,
            bench=bench,
            players=roster.players,
            taxi=taxi,
        )
