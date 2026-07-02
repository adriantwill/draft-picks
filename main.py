import time
from collections import Counter, deque
from pathlib import Path

import requests

REQUESTS_PER_MINUTE = 600
SECONDS_PER_REQUEST = 60 / REQUESTS_PER_MINUTE

last_request_time = 0.0


def main():
    # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
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


def sleeper_get(url: str):
    global last_request_time

    now = time.monotonic()
    elapsed = now - last_request_time
    wait_time = SECONDS_PER_REQUEST - elapsed

    if wait_time > 0:
        time.sleep(wait_time)

    response = requests.get(url, timeout=10)
    last_request_time = time.monotonic()

    response.raise_for_status()
    return response.json()


def bfs_leagues(user_ids: list[str]):
    seen_leagues = load_ids("data/seen_leagues.txt")
    good_drafts = load_ids("data/good_drafts.txt")
    seen_users = load_ids("data/seen_users.txt") | set(user_ids)

    try:
        years = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
        req_count = 0
        q = deque(user_ids)
        while q:
            last_user = q.pop()
            for year in years:
                last_league = sleeper_get(
                    f"https://api.sleeper.app/v1/user/{last_user}/leagues/nfl/{year}",
                )
                req_count += 1
                if req_count % 100 == 0:
                    save_seen_files(seen_leagues, good_drafts, seen_users)
                for league in last_league:
                    league_id = league["league_id"]
                    if league_id in seen_leagues:
                        continue
                    if is_target_league(league):
                        good_drafts.add(league["draft_id"])
                    seen_leagues.add(league_id)
                    print(league_id)
                    users = sleeper_get(
                        f"https://api.sleeper.app/v1/league/{league_id}/users"
                    )
                    req_count += 1
                    for user in users:
                        user_id = user["user_id"]
                        if user_id in seen_users:
                            continue
                        seen_users.add(user_id)
                        q.append(user_id)
    finally:
        save_seen_files(seen_leagues, good_drafts, seen_users)


def load_ids(path: str) -> set[str]:
    file = Path(path)
    if not file.exists():
        return set()
    return set(file.read_text().splitlines())


def save_seen_files(seen_leagues: set, good_drafts: set, seen_users: set):
    Path("data").mkdir(exist_ok=True)
    Path("data/seen_leagues.txt").write_text("\n".join(seen_leagues) + "\n")
    Path("data/good_drafts.txt").write_text("\n".join(good_drafts) + "\n")
    Path("data/seen_users.txt").write_text("\n".join(map(str, seen_users)) + "\n")


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
        and pass_td <= 6.0
        and pass_td >= 4.0
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
