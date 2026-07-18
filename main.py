import json
import re
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
    SleeperMatchup,
)
from util import load_ids, sleeper_get


def main():
    # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    # print(len(load_ids("data/good_drafts.txt")))
    merged_adp()


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
        merged_year = merged[merged["year"] == int(draft["season"])]
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
                merged_year[merged_year["player_id"].str == pick["player_id"]].index
            )
            del row["player_id"]
            del row["roster_id"]
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
            row["target_score"] = draft["scores"][pick["roster_id"] - 1]
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
            team_pos_count[pos_to_num[pick["player_position"]]][
                pick["roster_id"] - 1
            ] += 1
            rows.append(row)
    df = pd.DataFrame(rows)
    print(df)
    X = df.drop(columns="target_score")
    y = df["target_score", "season"]
    X_train = X[X["season"] < 2024]
    y_train = y[y["season"] < 2024]
    y_train = df.drop(columns="season")
    X_train = df.drop(columns="season")
    model = LinearRegression()
    model.fit(X_train, y_train)


def normalize_player_name(name: str) -> str:
    name = str(name).lower()
    name = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", name)
    name = re.sub(r"[^a-z0-9]+", "", name)
    return name


def merged_adp():
    adp_finish = pd.DataFrame
    players = pd.read_json("nfl.json").T
    players = players.drop_duplicates(
        subset=["search_full_name", "position"],
        keep="first",
    )
    for i in range(8):
        adp = pd.read_csv(f"adp/FantasyPros_{2017 + i}_Overall_ADP_Rankings.csv")
        adp["position"] = adp["POS"].str[:2]
        adp = adp.drop(
            adp[
                (adp["position"] != "WR")
                & (adp["position"] != "TE")
                & (adp["position"] != "QB")
                & (adp["position"] != "RB")
            ].index
        )
        adp = adp[["Player", "AVG", "position"]]
        adp["search_full_name"] = adp["Player"].apply(normalize_player_name)
        adp["year"] = 2017 + i
        adp = adp.merge(
            players[["search_full_name", "position", "player_id"]],
            on=["search_full_name", "position"],
            how="left",
        )
        adp_finish = (
            adp if adp_finish.empty else pd.concat([adp_finish, adp], ignore_index=True)
        )

    adp_finish.to_csv("adp_all.csv", index=False)


def create_merged():
    adp_finish = pd.DataFrame
    for i in range(8):
        adp = pd.read_csv(f"adp/FantasyPros_{2017 + i}_Overall_ADP_Rankings.csv")
        finish = pd.read_csv(f"finsh/receiving_finish_{2017 + i}.csv")
        qb_finish = pd.read_csv(f"finsh/passing_finish_{2017 + i}.csv")
        qb_finish["position"] = "QB"
        finish = pd.concat([finish, qb_finish], ignore_index=True)
        finish["normal_name"] = finish["player"].apply(normalize_player_name)
        adp["normal_name"] = adp["Player"].apply(normalize_player_name)
        adp = adp[["Player", "AVG", "normal_name"]]
        finish = finish[["player", "fantasyPts", "position", "normal_name"]]
        finish = finish[["player", "fantasyPts", "position", "normal_name"]]
        finish = finish[["player", "fantasyPts", "position", "normal_name"]]
        adp["year"] = 2017 + i
        merged = pd.merge(adp, finish, on="normal_name")
        merged = merged.drop(columns=["Player", "normal_name"])
        if adp_finish.empty:
            adp_finish = merged
        else:
            adp_finish = pd.concat([adp_finish, merged], ignore_index=True)
    expected_points(adp_finish).to_csv("merged.csv", index=False)


#  - Current target multiplies team z-score by drafted-starter retention at main.py:190. This creates
#    odd behavior: a bad team with fewer drafted starters gets pulled toward zero and looks less bad.


def draft_impact(draft: Draft, all_players: AllPlayers) -> Draft:
    player_impact: PlayerImpact = defaultdict(int)
    team_size = 7

    total_points = np.zeros(draft["teams"])
    player_roster: dict[PlayerId, int] = {}
    for i in range(1, 18):
        weekly_team_points = np.zeros(draft["teams"])
        start_ratio = np.zeros(draft["teams"])
        matchups: list[SleeperMatchup] = sleeper_get(
            f"https://api.sleeper.app/v1/league/{draft['league_id']}/matchups/{i}"
        )
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
    for pid in player_impact:
        roster = player_roster[pid]
        player_impact[pid] /= total_points[roster - 1]
    draft["start_ratio"] = list(start_ratio)
    draft["week_z"] = list(week_z)
    draft["player_impact"] = player_impact
    return draft


def expected_points(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["year", "position", "AVG"]).copy()
    df["bucket"] = df.groupby(by=["year", "position"]).cumcount() // 6
    expected_points = (
        df[df["year"] < 2024]
        .groupby(by=["bucket", "position"])["fantasyPts"]
        .median()
        .to_frame("median")
    ).reset_index()
    df = df.merge(expected_points, on=["position", "bucket"])
    df["expected_diff"] = df["fantasyPts"] - df["median"]
    return df


def name_to_id():
    players = pd.read_json("nfl.json").T
    players = players.drop_duplicates(
        subset=["search_full_name", "position"],
        keep="first",
    )
    merged = pd.read_csv("merged.csv")
    merged["search_full_name"] = merged["player"].apply(normalize_player_name)
    merged = merged.merge(
        players[["search_full_name", "position", "player_id"]],
        on=["search_full_name", "position"],
        how="left",
    )
    merged = merged.drop(columns=["search_full_name"])
    merged.to_csv("merged.csv", index=False)


def draft_info():
    good_drafts = load_ids("data/good_drafts.txt")
    with Path("nfl.json").open(encoding="utf-8") as f:
        all_players: AllPlayers = json.load(f)
    good_drafts = ["1125986091942735872"]
    draft_list: list[Draft] = []
    merged_csv = pd.read_csv("adp_all.csv")
    for draft in good_drafts:
        response = sleeper_get(f"https://api.sleeper.app/v1/draft/{draft}")
        if not response:
            continue
        draft_json: Draft = {
            "league_id": response.get("league_id"),
            "draft_id": response.get("draft_id"),
            "teams": response.get("settings", {}).get("teams"),
            "season": response.get("season"),
            "picks": [],
        }
        adp_csv = merged_csv[(merged_csv["year"]) == int(response.get("season"))]
        adp_csv = adp_csv.sort_values("AVG").reset_index(drop=True)
        adp_csv["pos_rank"] = adp_csv.groupby("position").cumcount() + 1
        picks = sleeper_get(f"https://api.sleeper.app/v1/draft/{draft}/picks")
        if not picks:
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
            match = adp_csv[adp_csv["player_id"] == float(pick.get("player_id"))]
            if not match.empty:
                overall_rank = int(match.index[0]) + 1
                pos_rank = int(match.iloc[0]["pos_rank"])
                adp = match.reset_index().at[0, "AVG"]
            pick_json: DraftPick = {
                "pick_no": pick.get("pick_no"),
                "round": pick.get("round"),
                "draft_slot": pick.get("draft_slot"),
                "roster_id": pick.get("roster_id"),
                "player_id": pick.get("player_id"),
                "player_position": metadata.get("position"),
                "adp": (adp),
                "overall_rank": (overall_rank),
                "pos_rank": (pos_rank),
            }
            print(pick_json)
            draft_json["picks"].append(pick_json)
        draft_list.append(draft_impact(draft_json, all_players))
    Path("data/drafts_metadata.json").write_text(json.dumps(draft_list, indent=2))


if __name__ == "__main__":
    main()
