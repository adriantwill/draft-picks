from typing import NotRequired, TypedDict


type PlayerId = str
type PlayerImpact = dict[PlayerId, float]
type IdSet = set[str]


class NflPlayer(TypedDict):
    player_id: PlayerId
    position: str | None
    search_full_name: NotRequired[str | None]


type AllPlayers = dict[PlayerId, NflPlayer]


class DraftPick(TypedDict):
    pick_no: int
    round: int
    draft_slot: int
    roster_id: int
    player_id: PlayerId
    player_position: str
    adp: float | None
    overall_rank: int | None
    pos_rank: int | None


class Draft(TypedDict):
    league_id: str
    draft_id: str
    teams: int
    season: str
    picks: list[DraftPick]
    scores: NotRequired[list[float]]
    player_impact: NotRequired[PlayerImpact]


class SleeperMatchup(TypedDict):
    roster_id: int
    points: float
    starters: list[PlayerId]
    starters_points: list[float]
    players_points: dict[PlayerId, float]
