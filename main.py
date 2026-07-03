import time
from collections import Counter, deque
from pathlib import Path

import pandas as pd
import requests

REQUESTS_PER_MINUTE = 600
SECONDS_PER_REQUEST = 60 / REQUESTS_PER_MINUTE

last_request_time = 0.0


def main():
    # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print(len(load_ids("data/good_drafts.txt")))
    return
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
    bfs_leagues(user_ids)


def sleeper_get(url: str, retries: int = 3):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            return response.json()

        except (requests.exceptions.RequestException, ValueError) as e:
            print("request failed, retrying", attempt + 1, type(e).__name__, url)
            time.sleep(5 * (attempt + 1))

    print("failed after retries", url)
    return None


def draft_info():
    good_drafts = load_ids("data/good_drafts.txt")
    for draft in good_drafts:
        response = sleeper_get(f"https://api.sleeper.app/v1/draft/{draft}")
        if not response:
            continue
        draft_json = {
            "league_id": response.get("league_id"),
            "draft_id": response.get("draft_id"),
            "teams": response.get("settings", {}).get("teams"),
            "flex": response.get("settings", {}).get("slots_flex"),
            "season": response.get("season"),
        }
        adp_csv = pd.read_csv(
            f"FantasyPros_{draft_json['season']}_Overall_ADP_Rankings.csv"
        )
        adp_csv["player"].str.replace(" Jr.", "", regex=False)
        adp_csv["player"].str.replace(".", "", regex=False)
        adp_csv = adp_csv.sort_values("AVG")
        draft_json["picks"] = []
        picks = sleeper_get(f"https://api.sleeper.app/v1/draft/{draft}/picks")
        if not picks:
            continue
        picked_players = set()
        rosters = {}
        for pick in picks:
            player_name = adp_csv["player"]
            metadata = pick.get("metadata") or {}
            position = metadata.get("position")
            row = adp_csv[
                (adp_csv["player"] == player_name)
                & (adp_csv["POS"].str[:2] == position)
            ]
            overall_rank = adp_csv[adp_csv["player"] == player_name].index[0]
            pos_df = adp_csv[adp_csv["POS"].str[:2] == position]
            pos_rank = pos_df[pos_df["player"] == player_name].index[0]
            pick_json = {
                "pick_no": pick.get("pick_no"),
                "round": pick.get("round"),
                "draft_slot": pick.get("draft_slot"),
                "roster_id": pick.get("roster_id"),
                "player_id": pick.get("player_id"),
                "player_position": metadata.get("position"),
                "player_team": metadata.get("team"),
                "picked_players_before": picked_players,
                "roster_before": rosters["roster_id"],
                "adp": row["AVG"],
                "overall_rank": overall_rank,
                "pos_rank": pos_rank,
            }
            rosters.setdefault(pick.get("roster_id"), []).append(pick.get("position"))
            picked_players.add(pick.get("player_id"))
            draft_json["picks"].append(pick_json)


def bfs_leagues(user_ids: list[str]):
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
                    if league_id in seen_leagues:
                        continue
                    if is_target_league(league):
                        good_drafts.add(league["draft_id"])
                        print(league["draft_id"])
                    seen_leagues.add(league_id)
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
    rec = scoring_settings.get("rec")
    pass_td = scoring_settings.get("pass_td")
    num_teams = settings.get("num_teams")
    return (
        league.get("sport") == "nfl"
        and league.get("season_type") == "regular"
        and settings.get("best_ball") == 0
        and settings.get("type") == 0
        and rec is not None
        and rec >= 0.5
        and rec <= 1.0
        and pass_td is not None
        and pass_td == 4.0
        and pos_count["QB"] == 1
        and pos_count["RB"] == 2
        and pos_count["WR"] == 2
        and pos_count["TE"] == 1
        and pos_count["FLEX"] <= 2
        and pos_count["FLEX"] >= 1
        and "SUPER_FLEX" not in pos_count
        and "IDP" not in pos_count
        and num_teams is not None
        and num_teams >= 10
        and num_teams <= 14
    )


if __name__ == "__main__":
    main()
