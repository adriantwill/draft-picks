import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from data_types import (
    AllPlayers,
    Draft,
    DraftPick,
    PlayerId,
    PlayerImpact,
)
from util import load_ids, normalize_player_name, sleeper_get

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def main():
    # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    # print(len(load_ids("data/good_drafts.txt")))
    train_model()


def train_model():
    with open("data/drafts_metadata.json", "r") as f:
        drafts: list[Draft] = json.load(f)
    rows: list[dict[str, Any]] = []
    merged = pd.read_csv("adp_all.csv")
    pos_to_num = {
        "QB": 0,
        "RB": 1,
        "WR": 2,
        "TE": 3,
    }
    for draft in drafts:
        print(draft)
        team_pos_count = np.zeros((4, draft["teams"]))
        merged_year = merged.loc[merged["year"] == int(draft["season"])]
        merged_year = merged_year.sort_values("AVG")
        for pick in draft["picks"]:
            row: dict[str, Any] = dict(pick)
            row["team_count"] = draft["teams"]
            row["season"] = int(draft["season"])
            row["is_qb"] = 1 if pick["player_position"] == "QB" else 0
            row["is_rb"] = 1 if pick["player_position"] == "RB" else 0
            row["is_wr"] = 1 if pick["player_position"] == "WR" else 0
            row["is_te"] = 1 if pick["player_position"] == "TE" else 0
            merged_year = merged_year.drop(
                merged_year[merged_year["player_id"] == pick["player_id"]].index
            )
            del row["player_position"]
            row["my_qb_picked"] = team_pos_count[0][pick["roster_id"] - 1]
            row["my_rb_picked"] = team_pos_count[1][pick["roster_id"] - 1]
            row["my_wr_picked"] = team_pos_count[2][pick["roster_id"] - 1]
            row["my_te_picked"] = team_pos_count[3][pick["roster_id"] - 1]
            row["qb_picked"] = sum(team_pos_count[0])
            row["rb_picked"] = sum(team_pos_count[1])
            row["wr_picked"] = sum(team_pos_count[2])
            row["te_picked"] = sum(team_pos_count[3])

            row["next_best_qb"] = merged_year[merged_year["position"] == "QB"].iloc[0][
                "AVG"
            ]
            row["next_best_rb"] = merged_year[merged_year["position"] == "RB"].iloc[0][
                "AVG"
            ]
            row["next_best_wr"] = merged_year[merged_year["position"] == "WR"].iloc[0][
                "AVG"
            ]
            row["next_best_te"] = merged_year[merged_year["position"] == "TE"].iloc[0][
                "AVG"
            ]
            row["second_best_qb"] = merged_year[merged_year["position"] == "QB"].iloc[
                1
            ]["AVG"]
            row["second_best_rb"] = merged_year[merged_year["position"] == "RB"].iloc[
                1
            ]["AVG"]
            row["second_best_wr"] = merged_year[merged_year["position"] == "WR"].iloc[
                1
            ]["AVG"]
            row["second_best_te"] = merged_year[merged_year["position"] == "TE"].iloc[
                1
            ]["AVG"]
            row["pos_gap"] = (
                row[f"next_best_{pick['player_position'].lower()}"] - pick["adp"]
            )
            row["wr_per_team"] = sum(team_pos_count[2]) / draft["teams"]
            row["wr_picked_normalized"] = sum(team_pos_count[2]) / row["pick_no"]
            row["rb_per_team"] = sum(team_pos_count[1]) / draft["teams"]
            row["rb_picked_normalized"] = sum(team_pos_count[1]) / row["pick_no"]
            row["qb_per_team"] = sum(team_pos_count[0]) / draft["teams"]
            row["qb_picked_normalized"] = sum(team_pos_count[0]) / row["pick_no"]
            row["te_per_team"] = sum(team_pos_count[3]) / draft["teams"]
            row["te_picked_normalized"] = sum(team_pos_count[3]) / row["pick_no"]

            row["target_score"] = draft["team_player_impact"][pick["roster_id"] - 1]
            row["weekly_z"] = draft["total_weekly_z"][pick["roster_id"] - 1]
            row["start_ratio"] = draft["total_start_ratio"][pick["roster_id"] - 1]
            team_pos_count[pos_to_num[pick["player_position"]]][
                pick["roster_id"] - 1
            ] += 1
            rows.append(row)
    df = pd.DataFrame(rows)
    print(df)
    X = df.drop(columns=["target_score", "player_id", "roster_id"])
    y = df["target_score", "weekly_z", "start_ratio", "season"]
    X_train = X[X["season"] < 2024]
    y_train = y[y["season"] < 2024]
    y_train = df.drop(columns="season")
    X_train = df.drop(columns="season")
    model = LinearRegression()
    model.fit(X_train, y_train)


def draft_impact(draft: Draft, all_players: AllPlayers) -> Draft:
    player_impact: PlayerImpact = defaultdict(int)
    team_size = 7

    total_points = np.zeros(draft["teams"])
    total_weekly_z = np.zeros(draft["teams"])
    total_start_ratio = np.zeros(draft["teams"])
    team_player_impact = np.zeros(draft["teams"])
    player_roster: dict[PlayerId, int] = {}
    for i in range(1, 18):
        weekly_team_points = np.zeros(draft["teams"])
        start_ratio = np.zeros(draft["teams"])
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
                    player_roster[starter] = roster
                    draft_starter_count += 1
                    player_impact[starter] += matchup["players_points"][starter]
            start_ratio[roster - 1] = draft_starter_count / team_size
            total_points[roster - 1] += points
            weekly_team_points[roster - 1] = points
        week_z = (weekly_team_points - np.mean(weekly_team_points)) / np.std(
            weekly_team_points
        )
        total_weekly_z += week_z
        total_start_ratio += start_ratio
    for pid in player_impact:
        roster = player_roster[pid]
        player_impact[pid] /= total_points[roster - 1]
        team_player_impact[roster - 1] += player_impact[pid]
    draft["total_start_ratio"] = list(total_start_ratio / 17)
    draft["total_weekly_z"] = list(total_weekly_z / 17)
    draft["team_player_impact"] = list(team_player_impact)
    draft["player_impact"] = player_impact
    return draft


def draft_info():
    good_drafts = load_ids("data/good_drafts.txt")
    with Path("nfl.json").open(encoding="utf-8") as f:
        all_players: AllPlayers = json.load(f)
    good_drafts = ["1125986091942735872"]
    draft_list: list[Draft] = []
    adp_csv = pd.read_csv("adp_all.csv")
    for draft in good_drafts:
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
        adp_csv = adp_csv.loc[adp_csv["year"] == int(response.get("season"))]
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
    Path("data/drafts_metadata.json").write_text(json.dumps(draft_list, indent=2))


if __name__ == "__main__":
    main()
