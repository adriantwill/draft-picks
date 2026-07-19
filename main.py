import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from data_types import (
    Draft,
)

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


def train_model():
    with DRAFTS_METADATA_DIR.open(encoding="utf-8") as f:
        drafts: list[Draft] = json.load(f)
    rows: list[dict[str, Any]] = []
    merged = pd.read_csv(ADP_DIR)
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


if __name__ == "__main__":
    main()
