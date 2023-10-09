from sleeperbot.clients import (
    fantasy_calc,
    ktc,
    sleeper,
)
from sleeperbot.models import Roster

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
        my_user_id = sleeper.get_my_user_id()
        self.owners = {owner.guid: owner for owner in sleeper.get_owners()}

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
        starters: list[str] = []
        reserve: list[str] = []

        sorted_players = sorted(roster.players, key=lambda player: player.redraft, reverse=True)

        # 1. Remove IR, Taxi, and players on bye
        for player in roster.players:
            if player.guid in roster.taxi:
                sorted_players.remove(player)

            elif player.status == "Inactive" and len(reserve) < self.settings.reserve_slots:
                reserve.append(player.guid)
                sorted_players.remove(player)

            elif player.bye_week == self.settings.week:
                sorted_players.remove(player)

        # 2. Fill all starting positions that can only be filled by one roster position
        lineup_positions = [
            position for position in self.settings.roster_positions if len(LINEUP_POSITION_MAP.get(position, [])) == 1
        ]

        for lineup_position in lineup_positions:
            starter = next(player for player in sorted_players if player.position == lineup_position)
            starters.append(starter.guid)
            sorted_players.remove(starter)

        # 3. Fill all flex positions that can be filled by multiple roster positions
        #    - starting with the flex spots which can be filled by the most positions
        flex_positions = sorted(
            [position for position in self.settings.roster_positions if len(LINEUP_POSITION_MAP.get(position, [])) > 1],
            key=lambda position: len(LINEUP_POSITION_MAP[position]),
            reverse=True,
        )

        for flex_position in flex_positions:
            starter = next(player for player in sorted_players if player.position in LINEUP_POSITION_MAP[flex_position])
            starters.append(starter.guid)
            sorted_players.remove(starter)

        # 4. Fill out bench
        bench = [p.guid for p in sorted_players]

        return Roster(
            guid=roster.guid,
            owners=roster.owners,
            starters=starters,
            reserve=reserve,
            bench=bench,
            players=roster.players,
            # touching taxi squad should not be done as part of roster optimization
            # since there are very explicit rules/times when taxi players can be added
            taxi=roster.taxi,
        )
