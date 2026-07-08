import json
import re
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split

REQUESTS_PER_MINUTE = 600
SECONDS_PER_REQUEST = 60 / REQUESTS_PER_MINUTE

last_request_time = 0.0


def main():
    # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    # print(len(load_ids("data/good_drafts.txt")))
    name_to_id()


def train_model():
    with open("data/drafts_metadata_temp.json", "r") as f:
        drafts = json.load(f)
    rows = []
    merged = pd.read_csv("merged_expected.csv")
    pos_to_num = {"QB": 0, "RB": 1, "WR": 2, "TE": 3}
    for draft in drafts:
        team_pos_count = np.zeros((4, draft["teams"]))
        merged_year = merged[merged["year"] == int(draft["season"])]
        merged_year = merged_year.sort_values("AVG")
        for pick in draft["picks"]:
            row = pick
            print(row)
            row["player_position"] = pos_to_num[row["player_position"]]
            merged_year.drop(
                merged_year[merged_year["sleeper_id"] == pick["player_id"]].index
            )
            team_pos_count[row["player_position"]][pick["roster_id"] - 1] += 1
            del row["player_id"]
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
            row["target_score"] = draft["scores"][pick["roster_id"] - 1]
            rows.append(row)
    df = pd.DataFrame(rows)
    print(df)
    X = df.drop(columns="target_score")
    y = df["target_score"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    model = LinearRegression()
    model.fit(X_train, y_train)


def normalize_player_name(name: str) -> str:
    name = str(name).lower()
    name = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", name)
    name = re.sub(r"[^a-z0-9]+", "", name)
    return name


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
        adp["year"] = 2017 + i
        merged = pd.merge(adp, finish, on="normal_name")
        merged = merged.drop(columns=["Player", "normal_name"])
        if adp_finish.empty:
            adp_finish = merged
        else:
            adp_finish = pd.concat([adp_finish, merged], ignore_index=True)
    expected_points(adp_finish).to_csv("merged.csv", index=False)


def clean_data(
    dataframes: list[pd.DataFrame],
):
    for df in dataframes:
        df["Player"] = df["Player"].str.replace(" Jr.", "", regex=False)
        df["Player"] = df["Player"].str.replace(" Sr.", "", regex=False)
        df["Player"] = df["Player"].str.replace(" III", "", regex=False)
        df["Player"] = df["Player"].str.replace(" II", "", regex=False)
        df["Player"] = df["Player"].str.replace(" IV", "", regex=False)
        df["Player"] = df["Player"].str.strip()


def sleeper_get(url: str, retries: int = 3):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=20, verify=False)
            response.raise_for_status()
            return response.json()

        except (requests.exceptions.RequestException, ValueError) as e:
            print("request failed, retrying", attempt + 1, type(e).__name__, url)
            time.sleep(5 * (attempt + 1))

    print("failed after retries", url)
    return None


def draft_impact():
    with Path("data/drafts_metadata.json").open(encoding="utf-8") as f:
        drafts = json.load(f)
    with Path("nfl.json").open(encoding="utf-8") as f:
        all_players = json.load(f)
    team_size = 7
    for draft in drafts:
        player_impact = defaultdict(int)
        total_points = np.zeros(draft["teams"])
        weekly_team_z = np.zeros(draft["teams"])
        player_roster = {}
        for i in range(1, 18):
            weekly_team_points = np.zeros(draft["teams"])
            start_ratio = np.zeros(draft["teams"])
            matchups = sleeper_get(
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
            weekly_team_z += week_z * start_ratio

        weekly_team_z /= 17
        for pid in player_impact:
            roster = player_roster[pid]
            player_impact[pid] /= total_points[roster - 1]
        draft["scores"] = list(weekly_team_z)
        draft["player_impact"] = player_impact
    Path("data/drafts_metadata_temp.json").write_text(json.dumps(drafts, indent=2))


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
    good_drafts = ["1125986091942735872"]
    draft_list = []
    merged_csv = pd.read_csv("merged_expected.csv")
    for draft in good_drafts:
        response = sleeper_get(f"https://api.sleeper.app/v1/draft/{draft}")
        if not response:
            continue
        draft_json = {
            "league_id": response.get("league_id"),
            "draft_id": response.get("draft_id"),
            "teams": response.get("settings", {}).get("teams"),
            "season": response.get("season"),
            "picks": [],
        }
        adp_csv = merged_csv[(merged_csv["year"]) == int(response.get("season"))]
        adp_csv = adp_csv.sort_values("AVG")
        picks = sleeper_get(f"https://api.sleeper.app/v1/draft/{draft}/picks")
        if not picks:
            continue
        for pick in picks:
            metadata = pick.get("metadata") or {}
            player_name = metadata.get("first_name") + " " + metadata.get("last_name")
            player_name = normalize_player_name(player_name)
            position = metadata.get("position")
            if position == "K" or position == "DEF":
                continue
            # merged_csv.loc[
            #     (merged_csv["position"] == position)
            #     & (merged_csv["Player"].apply(normalize_player_name) == player_name),
            #     "sleeper_id",
            # ] = pick["player_id"]
            overall_rank = None
            pos_rank = None
            adp = None
            print(player_name)
            overall_rank = (
                int(
                    adp_csv[
                        adp_csv["sleeper_id"] == float(pick.get("player_id"))
                    ].index[0]
                )
                + 1
            )
            pos_df = adp_csv[adp_csv["position"] == position].reset_index(drop=True)
            pos_rank = (
                int(
                    pos_df[pos_df["sleeper_id"] == float(pick.get("player_id"))].index[
                        0
                    ]
                )
                + 1
            )
            adp = (
                adp_csv[adp_csv["sleeper_id"] == float(pick.get("player_id"))]
                .reset_index()
                .at[0, "AVG"]
            )
            pick_json = {
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
            # print(pick_json)
            draft_json["picks"].append(pick_json)
        draft_list.append(draft_json)
    Path("data/drafts_metadata.json").write_text(json.dumps(draft_list, indent=2))
    merged_csv.to_csv("merged_expected.csv", index=False)


def bfs_leagues():
    seed_users = [
        "jjzachariason",
        "justinboone",
        "jeffratcliffe",
        "lordreebs",
        "joshlarky",
        "adamrank",
        "ryanhallam",
        "kaceykasem",
        "ryanmcdowell",
        "scottfish24",
        "scottfish",
        "theffballers",
        "andyholloway",
        "mikewright",
        "salpal2",
        "joebond",
    ]
    user_ids = []
    for seed in seed_users:
        user = requests.get(f"https://api.sleeper.app/v1/user/{seed}", timeout=10)
        user_ids.append(user.json()["user_id"])
    seen_leagues = load_ids("data/seen_leagues.txt")
    good_drafts = load_ids("data/good_drafts.txt")
    seen_users = load_ids("data/seen_users.txt") | set(user_ids)
    pending_users = load_ids("data/pending_users.txt")
    q = deque(pending_users or user_ids)

    try:
        years = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
        req_count = 0
        while q:
            last_user = q.pop()
            # if last_user in seen_users:
            #     continue
            for year in years:
                last_league = sleeper_get(
                    f"https://api.sleeper.app/v1/user/{last_user}/leagues/nfl/{year}",
                )
                if not last_league:
                    continue
                req_count += 1
                if req_count % 100 == 0:
                    save_seen_files(seen_leagues, good_drafts, seen_users, q)
                for league in last_league:
                    league_id = league["league_id"]
                    if league_id in seen_leagues or not is_target_league(league):
                        continue
                    seen_leagues.add(league_id)
                    draft_id = league["draft_id"]
                    draft = sleeper_get(f"https://api.sleeper.app/v1/draft/{draft_id}")
                    req_count += 1
                    if draft and is_good_draft(draft, league):
                        good_drafts.add(draft_id)
                        print(draft_id)
                    users = sleeper_get(
                        f"https://api.sleeper.app/v1/league/{league_id}/users"
                    )
                    if not users:
                        continue
                    req_count += 1
                    for user in users:
                        user_id = user["user_id"]
                        if user_id in seen_users:
                            continue
                        seen_users.add(user_id)
                        q.append(user_id)
    finally:
        save_seen_files(seen_leagues, good_drafts, seen_users, q)


def load_ids(path: str) -> set[str]:
    file = Path(path)
    if not file.exists():
        return set()
    return set(file.read_text().splitlines())


def save_seen_files(seen_leagues: set, good_drafts: set, seen_users: set, q: deque):
    Path("data").mkdir(exist_ok=True)
    Path("data/seen_leagues.txt").write_text("\n".join(seen_leagues) + "\n")
    Path("data/good_drafts.txt").write_text("\n".join(good_drafts) + "\n")
    Path("data/seen_users.txt").write_text("\n".join(map(str, seen_users)) + "\n")
    Path("data/pending_users.txt").write_text("\n".join(map(str, q)) + "\n")


def is_target_league(league):
    roster_positions = league.get("roster_positions") or []
    scoring_settings = league.get("scoring_settings") or {}
    settings = league.get("settings") or {}

    pos_count = Counter(roster_positions)
    idp_positions = {"IDP", "IDP_FLEX", "DL", "LB", "DB"}
    rec = scoring_settings.get("rec")
    pass_td = scoring_settings.get("pass_td")
    num_teams = settings.get("num_teams")
    return (
        league.get("sport") == "nfl"
        and league.get("season_type") == "regular"
        and league.get("status") in {"in_season", "complete"}
        and league.get("draft_id") is not None
        and settings.get("best_ball") == 0
        and settings.get("type") == 0
        and rec is not None
        # and rec >= 0.5
        and rec == 1.0
        and pass_td is not None
        and pass_td == 4.0
        and pos_count["QB"] == 1
        and pos_count["RB"] == 2
        and pos_count["WR"] == 2
        and pos_count["TE"] == 1
        and pos_count["K"] <= 1
        and pos_count["DEF"] <= 1
        # and pos_count["FLEX"] <= 2
        and pos_count["FLEX"] == 1
        and "SUPER_FLEX" not in pos_count
        and idp_positions.isdisjoint(pos_count)
        and num_teams is not None
        and num_teams >= 10
        and num_teams <= 12
    )


def is_good_draft(draft, league):
    settings = draft.get("settings") or {}
    league_settings = league.get("settings") or {}
    teams = settings.get("teams")
    flex = settings.get("slots_flex")

    return (
        draft.get("status") == "complete"
        and draft.get("type") == "snake"
        and draft.get("sport") == "nfl"
        and draft.get("season_type") == "regular"
        and draft.get("league_id") == league.get("league_id")
        and teams == league_settings.get("num_teams")
        and teams is not None
        and teams >= 10
        and teams <= 14
        and settings.get("slots_qb") == 1
        and settings.get("slots_rb") == 2
        and settings.get("slots_wr") == 2
        and settings.get("slots_te") == 1
        and flex is not None
        and flex >= 1
        and flex <= 2
        and settings.get("slots_super_flex", 0) == 0
    )


if __name__ == "__main__":
    main()
