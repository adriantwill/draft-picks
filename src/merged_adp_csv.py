from pathlib import Path

import pandas as pd

from path import (
    ADP_CSV_PATH,
    ADP_SCRAPE_DIR,
    ADP_WITH_FINISH_CSV_PATH,
    FINISH_SCRAPE_DIR,
    NFL_PLAYERS_JSON_PATH,
)
from util import normalize_player_name


def main():
    merged_adp(ADP_CSV_PATH)


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


def name_to_id(df: pd.DataFrame) -> pd.DataFrame:
    players = pd.read_json(
        NFL_PLAYERS_JSON_PATH,
    ).T
    players = players.drop_duplicates(
        subset=["search_full_name", "position"],
        keep="first",
    )
    df["search_full_name"] = df["Player"].apply(normalize_player_name)
    df = df.merge(
        players[["search_full_name", "position", "player_id"]],
        on=["search_full_name", "position"],
        how="left",
    )
    # df= df.drop(columns=["search_full_name"])
    return df


def filter_adp(adp: pd.DataFrame, i: int) -> pd.DataFrame:
    if i > 0:
        finish = pd.read_csv(f"{FINISH_SCRAPE_DIR}/receiving_finish_{2017 + i}.csv")
        qb_finish = pd.read_csv(f"{FINISH_SCRAPE_DIR}/passing_finish_{2017 + i}.csv")
        qb_finish["position"] = "QB"
        finish = pd.concat([finish, qb_finish], ignore_index=True)
        finish["normal_name"] = finish["player"].apply(normalize_player_name)
        adp["normal_name"] = adp["Player"].apply(normalize_player_name)
        adp = adp.filter(["Player", "AVG", "normal_name"])
        finish = finish.filter(["player", "fantasyPts", "position", "normal_name"])
        adp = pd.merge(adp, finish, on="normal_name")
        adp = adp.drop(columns=["Player", "normal_name"])
    else:
        adp["position"] = adp["POS"].str[:2]
        adp = adp.drop(
            adp[
                (adp["position"] != "WR")
                & (adp["position"] != "TE")
                & (adp["position"] != "QB")
                & (adp["position"] != "RB")
            ].index
        )
        adp = adp.filter(["Player", "AVG", "position"])
    return adp


def merged_adp(output_csv_path: Path):
    adp_finish = pd.DataFrame()
    for i in range(9):
        adp = pd.read_csv(
            f"{ADP_SCRAPE_DIR}/FantasyPros_{2017 + i}_Overall_ADP_Rankings.csv",
        )
        adp = filter_adp(
            adp, i if output_csv_path == ADP_WITH_FINISH_CSV_PATH else 0
        )
        adp["year"] = 2017 + i
        adp_finish = (
            adp if adp_finish.empty else pd.concat([adp_finish, adp], ignore_index=True)
        )
    adp_finish = name_to_id(adp_finish)
    if output_csv_path == ADP_WITH_FINISH_CSV_PATH:
        adp_finish = expected_points(adp_finish)
    adp_finish.to_csv(output_csv_path, index=False)


if __name__ == "__main__":
    main()
