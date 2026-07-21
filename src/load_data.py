from collections import Counter, deque

import requests

from path import (
    PENDING_USER_IDS_PATH,
    QUALIFYING_DRAFT_IDS_PATH,
    SEEN_LEAGUE_IDS_PATH,
    SEEN_USER_IDS_PATH,
)
from util import load_ids, sleeper_get


def main():
    bfs_leagues()


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
    seen_leagues = load_ids(SEEN_LEAGUE_IDS_PATH)
    good_drafts = load_ids(QUALIFYING_DRAFT_IDS_PATH)
    seen_users = load_ids(SEEN_USER_IDS_PATH) | set(user_ids)
    pending_users = load_ids(PENDING_USER_IDS_PATH)
    q = deque(pending_users or user_ids)

    try:
        years = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
        req_count = 0
        while q:
            last_user = q[0]

            # if last_user in seen_users:
            #     continue
            bad_league_response = False
            for year in years:
                last_league = sleeper_get(
                    f"https://api.sleeper.app/v1/user/{last_user}/leagues/nfl/{year}",
                )
                if not last_league:
                    if last_league is None:
                        bad_league_response = True
                    continue
                req_count += 1
                for league in last_league:
                    league_id = league["league_id"]
                    if league_id in seen_leagues or not is_target_league(league):
                        continue
                    draft_id = league["draft_id"]
                    draft = sleeper_get(f"https://api.sleeper.app/v1/draft/{draft_id}")
                    if not draft:
                        if draft is None:
                            bad_league_response = True
                        continue
                    req_count += 1
                    if draft and is_good_draft(draft, league):
                        good_drafts.add(draft_id)
                        print(draft_id)
                    users = sleeper_get(
                        f"https://api.sleeper.app/v1/league/{league_id}/users"
                    )
                    if not users:
                        if users is None:
                            bad_league_response = True
                        continue
                    req_count += 1
                    for user in users:
                        user_id = user["user_id"]
                        if user_id in seen_users:
                            continue
                        seen_users.add(user_id)
                        q.append(user_id)
                    seen_leagues.add(league_id)
            q.popleft()
            if bad_league_response:
                q.append(last_user)
            save_seen_files(seen_leagues, good_drafts, seen_users, q)
    finally:
        save_seen_files(seen_leagues, good_drafts, seen_users, q)


def save_seen_files(seen_leagues: set, good_drafts: set, seen_users: set, q: deque):
    SEEN_LEAGUE_IDS_PATH.write_text("\n".join(seen_leagues) + "\n")
    QUALIFYING_DRAFT_IDS_PATH.write_text("\n".join(good_drafts) + "\n")
    SEEN_USER_IDS_PATH.write_text("\n".join(map(str, seen_users)) + "\n")
    PENDING_USER_IDS_PATH.write_text("\n".join(map(str, q)) + "\n")


def is_target_league(league):
    roster_positions = league.get("roster_positions") or []
    scoring_settings = league.get("scoring_settings") or {}
    settings = league.get("settings") or {}

    pos_count = Counter(roster_positions)
    idp_positions = {"DL", "LB", "DB", "IDP_FLEX"}
    pass_td = scoring_settings.get("pass_td")
    rec = scoring_settings.get("rec")
    num_teams = settings.get("num_teams")
    return (
        league.get("sport") == "nfl"
        and league.get("season_type") == "regular"
        and league.get("status") in {"in_season", "complete"}
        and league.get("draft_id") is not None
        and settings.get("best_ball") == 0
        and settings.get("type") == 0
        and settings.get("start_week") == 1
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
