from pathlib import Path

import pandas as pd

from main import DATA_DIR
from util import normalize_player_name

ADP_FINISH_DIR = DATA_DIR / "adp_finish.csv"
ADP_DIR = DATA_DIR / "adp.csv"


def main():
    merged_adp(ADP_DIR)


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
    players = pd.read_json("nfl.json").T
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
    df["player_id"] = df["player_id"].astype(str)
    return df


def filter_adp(adp: pd.DataFrame, i: int) -> pd.DataFrame:
    if i > 0:
        finish = pd.read_csv(f"finsh/receiving_finish_{2017 + i}.csv")
        qb_finish = pd.read_csv(f"finsh/passing_finish_{2017 + i}.csv")
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


def merged_adp(csv_name: Path):
    adp_finish = pd.DataFrame()
    for i in range(8):
        adp = pd.read_csv(f"adp/FantasyPros_{2017 + i}_Overall_ADP_Rankings.csv")
        adp = filter_adp(adp, i if csv_name == ADP_FINISH_DIR else 0)
        adp["year"] = 2017 + i
        adp_finish = (
            adp if adp_finish.empty else pd.concat([adp_finish, adp], ignore_index=True)
        )
    adp_finish = name_to_id(adp_finish)
    if csv_name == ADP_FINISH_DIR:
        adp_finish = expected_points(adp_finish)
    adp_finish.to_csv(csv_name, index=False)


if __name__ == "__main__":
    main()
