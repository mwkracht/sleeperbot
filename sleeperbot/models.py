import dataclasses
import json
from dataclasses import (
    dataclass,
    field,
)
from datetime import datetime

from sleeperbot import config

GUID = str

_registry = {}


class Model:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        _registry[cls.__name__] = cls

    def __init__(self, *args, **kwargs):
        self._type = type(self).__name__

    def __repr__(self):
        kws = []

        for key, value in self.__dict__.items():
            _lines = repr(value).split("\n")
            lines = [f"    {line}" for line in _lines[1:]]

            value_repr = "\n".join([_lines[0]] + lines)

            kws.append(f"{key}={value_repr}")

        if sum([len(kw) for kw in kws]) > 100:
            kws = [f"    {kw}" if not kw.startswith(" ") else "        {kw}" for kw in kws]
            return "{}(\n{}\n)".format(type(self).__name__, ",\n".join(kws))

        return f"{type(self).__name__}({', '.join(kws)})"


@dataclass(repr=False)
class PlayerValue(Model):
    trends: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)

    def _compute_value(self, only: list[str] | None = None) -> float:
        value_num, value_denom = 0.0, 0.0
        only = only or ["fantasy_calc", "ktc"]

        if "ktc" in only and self.values.get("ktc") is not None:
            value_num += config.WEIGHT_KTC * self.values["ktc"]
            value_denom += config.WEIGHT_KTC * 1

        if "fantasy_calc" in only and self.values.get("fantasy_calc") is not None:
            value_num += config.WEIGHT_FANTASY_CALC * self.values["fantasy_calc"]
            value_denom += config.WEIGHT_FANTASY_CALC * 1

        if not value_denom:
            return 0

        return value_num / value_denom

    @property
    def sources(self):
        return {key for key, value in self.values.items() if value is not None}

    def __lt__(self, pv: "PlayerValue") -> bool:
        sources = list(self.sources & pv.sources)
        return self._compute_value(only=sources) < pv._compute_value(only=sources)

    def __le__(self, pv: "PlayerValue") -> bool:
        sources = list(self.sources & pv.sources)
        return self._compute_value(only=sources) <= pv._compute_value(only=sources)

    def __gt__(self, pv: "PlayerValue") -> bool:
        sources = list(self.sources & pv.sources)
        return self._compute_value(only=sources) > pv._compute_value(only=sources)

    def __ge__(self, pv: "PlayerValue") -> bool:
        sources = list(self.sources & pv.sources)
        return self._compute_value(only=sources) >= pv._compute_value(only=sources)

    def update(self, player_value: "PlayerValue"):
        self.trends.update({key: value for key, value in player_value.trends.items() if value is not None})
        self.values.update({key: value for key, value in player_value.values.items() if value is not None})

    def __repr__(self):
        return f"PlayerValue({self.values})"


@dataclass(repr=False)
class Player(Model):
    guid: GUID
    first_name: str
    last_name: str
    team: str | None = None
    position: str | None = None
    number: int | None = None
    bye_week: int | None = None

    # Active
    # Inactive
    # Injured Reserve
    # Non Football Injury
    # Physically Unable to Perform
    # Practice Squad
    status: str | None = None

    # COV
    # DNR
    # Doubtful
    # IR
    # NA
    # Out
    # PUP
    # Questionable
    # Sus
    injury_status: str | None = None

    dynasty: PlayerValue = field(default_factory=PlayerValue)
    redraft: PlayerValue = field(default_factory=PlayerValue)

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def on_reserve(self):
        return self.status == "Inactive"

    @property
    def will_play(self):
        return self.status == "Active" and self.injury_status in (None, "Questionable")

    @property
    def alternate_id(self):
        """
        Not every service will have sleeper GUIDs for players. In that case
        we fall back on the full name as our player ID.

        Some services have the wrong numbers for players. Some have wrong
        teams. The combo of first + last name has historically given us the
        best match rate.
        """
        return f"{self.first_name} {self.last_name}"

    def update_value(self, player: "Player"):
        self.dynasty.update(player.dynasty)
        self.redraft.update(player.redraft)


@dataclass(repr=False)
class Roster(Model):
    guid: GUID
    owners: list[GUID]

    starters: list[GUID] = field(default_factory=list)
    reserve: list[GUID] = field(default_factory=list)
    bench: list[GUID] = field(default_factory=list)
    taxi: list[GUID] = field(default_factory=list)

    player_ids: list[GUID] = field(default_factory=list)
    players: list[Player] = field(default_factory=list)


@dataclass(repr=False)
class Matchup(Model):
    guid: GUID
    away_roster: GUID
    home_roster: GUID


@dataclass(repr=False)
class Game(Model):
    guid: GUID
    start_time: int
    teams: list[str]

    # pre_game
    # in_game
    # complete
    status: str

    @property
    def kickoff(self) -> datetime:
        return datetime.utcfromtimestamp(self.start_time / 1000)


@dataclass(repr=False)
class Team(Model):
    guid: GUID
    name: str
    bye_week: int
    game: Game | None = None


@dataclass(repr=False)
class Owner(Model):
    guid: GUID

    display_name: str | None = None
    avatar: str | None = None

    roster: Roster | None = None
    matchup: Matchup | None = None


@dataclass(repr=False)
class LeagueSettings(Model):
    guid: GUID
    name: str

    status: str
    week: int
    season: int

    total_teams: int
    roster_positions: list[str]
    taxi_slots: int
    reserve_slots: int
    ppr: float
    te_ppr: float

    @property
    def bench_slots(self):
        return self.roster_positions.count("BN")

    @property
    def starter_slots(self):
        return len(self.roster_positions) - self.bench_slots

    @property
    def superflex(self):
        return self.roster_positions.count("QB") > 1


def serialize(value, *args, **kwargs):
    class DataclassEncoder(json.JSONEncoder):
        def default(self, o):
            if dataclasses.is_dataclass(o):

                def factory(kv_pairs):
                    """Must do all of this junk to be able to recursively add dataclass type"""
                    obj_dict = dict(kv_pairs)
                    obj_fields = set(list(zip(*kv_pairs))[0])

                    # we don't have the object so we have to guess the type based on the keys...
                    for model in _registry.values():
                        model_fields = set(model.__dataclass_fields__.keys())

                        if obj_fields.issubset(model_fields):
                            obj_dict["_type"] = model.__name__
                            break

                    else:
                        raise RuntimeError("Unable to determine model type!")

                    return obj_dict

                return dataclasses.asdict(o, dict_factory=factory)

            return super().default(o)

    return json.dumps(value, *args, **kwargs, cls=DataclassEncoder)


def deserialize(serialization):
    def to_dataclass(value):
        if isinstance(value, list):
            return [to_dataclass(item) for item in value]

        if isinstance(value, dict) and "_type" in value:
            _type = _registry[value.pop("_type")]

            return _type(**{k: to_dataclass(v) for k, v in value.items()})

        elif isinstance(value, dict):
            return {key: to_dataclass(value) for key, value in value.items()}

        return value

    return to_dataclass(json.loads(serialization))
