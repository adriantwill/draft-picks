import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from src.data_types import Draft

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CRAWL_DIR = DATA_DIR / "crawl"
SEEN_USERS_DIR = CRAWL_DIR / "seen_users.txt"
GOOD_DRAFTS_DIR = CRAWL_DIR / "good_drafts.txt"
SEEN_LEAGUES_DIR = CRAWL_DIR / "seen_leagues.txt"
PENDING_USERS_DIR = CRAWL_DIR / "pending_users.txt"
CLEAN_DIR = DATA_DIR / "clean"
ADP_FINISH_DIR = CLEAN_DIR / "merged.csv"
ADP_DIR = CLEAN_DIR / "adp_all.csv"
DRAFTS_METADATA_DIR = CLEAN_DIR / "drafts_metadata.json"
SCRAPE_DIR = DATA_DIR / "scrape"
ADP_SCRAPE_DIR = SCRAPE_DIR / "adp"
FINISH_SCRAPE_DIR = SCRAPE_DIR / "finsh"
NFL_JSON = SCRAPE_DIR / "nfl.json"


def main():
    # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    # print(len(load_ids(GOOD_DRAFTS_DIR)))
    train_model()


def train_table() -> list[dict[str, Any]]:
    with DRAFTS_METADATA_DIR.open(encoding="utf-8") as f:
        drafts: list[Draft] = json.load(f)
    rows: list[dict[str, Any]] = []
    merged = pd.read_csv(ADP_DIR, dtype={"player_id": "string"})
    pos_to_num = {
        "QB": 0,
        "RB": 1,
        "WR": 2,
        "TE": 3,
    }
    for draft in drafts:
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
            row["my_qb_picked"] = int(team_pos_count[0][pick["roster_id"] - 1])
            row["my_rb_picked"] = int(team_pos_count[1][pick["roster_id"] - 1])
            row["my_wr_picked"] = int(team_pos_count[2][pick["roster_id"] - 1])
            row["my_te_picked"] = int(team_pos_count[3][pick["roster_id"] - 1])
            row["total_qb_picked"] = int(sum(team_pos_count[0]))
            row["total_rb_picked"] = int(sum(team_pos_count[1]))
            row["total_wr_picked"] = int(sum(team_pos_count[2]))
            row["total_te_picked"] = int(sum(team_pos_count[3]))

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
            row["wr_per_team"] = sum(team_pos_count[2]) / draft["teams"]
            row["wr_picked_normalized"] = (
                0
                if row["pick_no"] <= 1
                else sum(team_pos_count[2]) / (row["pick_no"] - 1)
            )
            row["rb_per_team"] = sum(team_pos_count[1]) / draft["teams"]
            row["rb_picked_normalized"] = (
                0
                if row["pick_no"] <= 1
                else sum(team_pos_count[1]) / (row["pick_no"] - 1)
            )
            row["qb_per_team"] = sum(team_pos_count[0]) / draft["teams"]
            row["qb_picked_normalized"] = (
                0
                if row["pick_no"] <= 1
                else sum(team_pos_count[0]) / (row["pick_no"] - 1)
            )
            row["te_per_team"] = sum(team_pos_count[3]) / draft["teams"]
            row["te_picked_normalized"] = (
                0
                if row["pick_no"] <= 1
                else sum(team_pos_count[3]) / (row["pick_no"] - 1)
            )

            row["target_score"] = draft["team_player_impact"][pick["roster_id"] - 1]
            row["weekly_z"] = draft["total_weekly_z"][pick["roster_id"] - 1]
            row["start_ratio"] = draft["total_start_ratio"][pick["roster_id"] - 1]
            team_pos_count[pos_to_num[pick["player_position"]]][
                pick["roster_id"] - 1
            ] += 1
            if not pick["adp"]:
                print("no adp")
            else:
                row["pos_gap"] = (
                    row[f"next_best_{pick['player_position'].lower()}"] - pick["adp"]
                )
                rows.append(row)
    return rows


def train_model():
    df = pd.DataFrame(train_table())
    train = df[df["season"] < 2025]
    X_train = train[
        "pick_no, round, draft_slot, adp, overall_rank, pos_rank, team_count, is_qb, is_rb, is_wr, is_te, my_qb_picked, my_rb_picked, my_wr_picked, my_te_picked, total_qb_picked, total_rb_picked, total_wr_picked, total_te_picked, next_best_qb, next_best_rb, next_best_wr, next_best_te, second_best_qb, second_best_rb, second_best_wr, second_best_te, pos_gap, wr_per_team, wr_picked_normalized, rb_per_team, rb_picked_normalized, qb_per_team, qb_picked_normalized, te_per_team, te_picked_normalized".split(
            ", "
        )
    ]
    y_train_z = train["weekly_z"]
    y_train_impact = train["target_score"]
    y_train_start_ratio = train["start_ratio"]
    impact_model = HistGradientBoostingRegressor().fit(X_train, y_train_impact)
    z_model = HistGradientBoostingRegressor().fit(X_train, y_train_z)
    start_ratio_model = HistGradientBoostingRegressor().fit(
        X_train, y_train_start_ratio
    )


if __name__ == "__main__":
    main()
