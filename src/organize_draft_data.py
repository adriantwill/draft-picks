import json
from collections import defaultdict

import numpy as np
import pandas as pd

from data_types import AllPlayers, Draft, DraftPick, PlayerId, PlayerImpact
from path import (
    ADP_CSV_PATH,
    DRAFTS_METADATA_PATH,
    NFL_PLAYERS_JSON_PATH,
    QUALIFYING_DRAFT_IDS_PATH,
)
from util import load_ids, normalize_player_name, sleeper_get


def main():
    draft_info()


def draft_impact(draft: Draft, all_players: AllPlayers) -> Draft:
    player_impact: PlayerImpact = defaultdict(int)
    team_size = 7

    total_points = np.zeros(draft["teams"])
    total_weekly_z = np.zeros(draft["teams"])
    total_start_ratio = np.zeros(draft["teams"])
    team_player_impact = np.zeros(draft["teams"])
    total_starter_points_z = np.zeros(draft["teams"])
    player_roster: dict[PlayerId, int] = {}
    num_weeks = 17 if int(draft["season"]) >= 2021 else 16
    for i in range(1, num_weeks + 1):
        weekly_team_points = np.zeros(draft["teams"])
        start_ratio = np.zeros(draft["teams"])
        starter_points = np.zeros(draft["teams"])
        matchups = sleeper_get(
            f"https://api.sleeper.app/v1/league/{draft['league_id']}/matchups/{i}"
        )
        if not matchups or type(matchups) is not list:
            continue
        for matchup in matchups:
            roster = matchup["roster_id"]
            points = matchup["points"]
            for i, pos in enumerate(["DEF", "K"]):
                points -= (
                    matchup["starters_points"][-i - 1]
                    if matchup["starters"][-i - 1] in all_players
                    and all_players[matchup["starters"][-i - 1]]["position"] == pos
                    else 0
                )
            roster_list = [
                pick["player_id"]
                for pick in draft["picks"]
                if pick["roster_id"] == roster
            ]
            draft_starter_count = 0
            for starter in matchup["starters"]:
                if starter in roster_list:
                    # list of 12 teams
                    starter_points[roster - 1] += matchup["players_points"][starter]
                    player_roster[starter] = roster
                    draft_starter_count += 1
                    player_impact[starter] += matchup["players_points"][starter]
            start_ratio[roster - 1] = draft_starter_count / team_size
            total_points[roster - 1] += points
            weekly_team_points[roster - 1] = points
        week_z = (weekly_team_points - np.mean(weekly_team_points)) / np.std(
            weekly_team_points
        )
        starter_points_z = (starter_points - np.mean(starter_points)) / np.std(
            starter_points
        )
        total_starter_points_z += starter_points_z
        total_weekly_z += week_z
        total_start_ratio += start_ratio
    for pid in player_impact:
        roster = player_roster[pid]
        player_impact[pid] /= total_points[roster - 1]
        team_player_impact[roster - 1] += player_impact[pid]
    draft["total_start_ratio"] = list(total_start_ratio / num_weeks)
    draft["total_weekly_z"] = list(total_weekly_z / num_weeks)
    draft["team_player_impact"] = list(team_player_impact)
    draft["player_impact"] = player_impact
    draft["mean_drafted_starter_points_z"] = list(
        total_starter_points_z / num_weeks
    )  # TODO ensure each matchup has vlaid # of weeks and users
    return draft


def draft_info():
    good_drafts = load_ids(QUALIFYING_DRAFT_IDS_PATH)
    with NFL_PLAYERS_JSON_PATH.open(encoding="utf-8") as f:
        all_players: AllPlayers = json.load(f)
    draft_list: list[Draft] = []
    adp_csv_original = pd.read_csv(ADP_CSV_PATH, dtype={"player_id": "string"})
    print(adp_csv_original.head().dtypes)
    for draft in list(good_drafts)[:100]:
        response = sleeper_get(f"https://api.sleeper.app/v1/draft/{draft}")
        if not response or type(response) is not dict:
            continue
        draft_json: Draft = {
            "league_id": response.get("league_id"),
            "draft_id": response.get("draft_id"),
            "teams": response.get("settings", {}).get("teams"),
            "season": response.get("season"),
            "picks": [],
            "total_weekly_z": [],
            "total_start_ratio": [],
            "team_player_impact": [],
        }
        adp_csv = adp_csv_original.loc[
            adp_csv_original["year"] == int(response.get("season"))
        ]
        adp_csv = adp_csv.sort_values("AVG").reset_index(drop=True)
        adp_csv["pos_rank"] = adp_csv.groupby("position").cumcount() + 1
        picks = sleeper_get(f"https://api.sleeper.app/v1/draft/{draft}/picks")
        if not picks or type(picks) is not list:
            continue
        for pick in picks:
            metadata = pick.get("metadata") or {}
            player_name = metadata["first_name"] + " " + metadata.get("last_name")
            player_name = normalize_player_name(player_name)
            position = metadata.get("position")
            if position == "K" or position == "DEF":
                continue
            overall_rank = None
            pos_rank = None
            adp = None
            match = adp_csv[adp_csv["player_id"] == pick.get("player_id")]
            print(match)
            if not match.empty:
                overall_rank = int(match.index[0]) + 1
                pos_rank = int(match.iloc[0]["pos_rank"])
                adp = match.reset_index().at[0, "AVG"]
            pick_json: DraftPick = {
                "pick_no": pick["pick_no"],
                "round": pick.get("round"),
                "draft_slot": pick.get("draft_slot"),
                "roster_id": pick.get("roster_id"),
                "player_id": pick.get("player_id"),
                "player_position": metadata.get("position"),
                "adp": (adp),
                "overall_rank": (overall_rank),
                "pos_rank": (pos_rank),
            }
            draft_json["picks"].append(pick_json)
        draft_list.append(draft_impact(draft_json, all_players))
    DRAFTS_METADATA_PATH.write_text(json.dumps(draft_list, indent=2))


if __name__ == "__main__":
    main()
