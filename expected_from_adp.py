import pandas as pd

from util import normalize_player_name


def main():
    create_merged()


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


def name_to_id(df: pd.DataFrame):
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


def create_merged():
    adp_finish = pd.DataFrame()
    for i in range(8):
        adp = pd.read_csv(f"adp/FantasyPros_{2017 + i}_Overall_ADP_Rankings.csv")
        finish = pd.read_csv(f"finsh/receiving_finish_{2017 + i}.csv")
        qb_finish = pd.read_csv(f"finsh/passing_finish_{2017 + i}.csv")
        qb_finish["position"] = "QB"
        finish = pd.concat([finish, qb_finish], ignore_index=True)
        finish["normal_name"] = finish["player"].apply(normalize_player_name)
        adp["normal_name"] = adp["Player"].apply(normalize_player_name)
        adp = adp.filter(["Player", "AVG", "normal_name"])
        finish = finish.filter(["player", "fantasyPts", "position", "normal_name"])
        adp["year"] = 2017 + i
        merged = pd.merge(adp, finish, on="normal_name")
        merged = merged.drop(columns=["Player", "normal_name"])
        if adp_finish.empty:
            adp_finish = merged
        else:
            adp_finish = pd.concat([adp_finish, merged], ignore_index=True)
    expected_points(adp_finish).to_csv("merged.csv", index=False)


if __name__ == "__main__":
    main()
