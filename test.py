import shutil
import sys
import time
from pathlib import Path
from typing import Any

import requests


SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from load_data import is_good_draft, is_target_league  # noqa: E402
from path import QUALIFYING_DRAFT_IDS_PATH  # noqa: E402


API_BASE_URL = "https://api.sleeper.app/v1"
REQUESTS_PER_MINUTE = 600
SECONDS_PER_REQUEST = 60 / REQUESTS_PER_MINUTE

last_request_time = 0.0


def sleeper_get(session: requests.Session, url: str) -> Any | None:
    global last_request_time

    for attempt in range(3):
        try:
            wait_time = SECONDS_PER_REQUEST - (
                time.monotonic() - last_request_time
            )
            if wait_time > 0:
                time.sleep(wait_time)

            last_request_time = time.monotonic()
            response = session.get(url, timeout=20)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            print(
                "request failed",
                attempt + 1,
                type(error).__name__,
                url,
            )
            time.sleep(5 * (attempt + 1))

    return None


def main() -> None:
    draft_ids = QUALIFYING_DRAFT_IDS_PATH.read_text().splitlines()
    kept_draft_ids: list[str] = []
    removed_draft_ids: list[str] = []
    unknown_draft_ids: list[str] = []
    leagues: dict[str, dict[str, Any] | None] = {}

    with requests.Session() as session:
        for index, draft_id in enumerate(draft_ids, start=1):
            draft = sleeper_get(session, f"{API_BASE_URL}/draft/{draft_id}")
            if not isinstance(draft, dict) or not draft.get("league_id"):
                kept_draft_ids.append(draft_id)
                unknown_draft_ids.append(draft_id)
                continue

            league_id = draft["league_id"]
            if league_id not in leagues:
                league = sleeper_get(session, f"{API_BASE_URL}/league/{league_id}")
                leagues[league_id] = league if isinstance(league, dict) else None

            league = leagues[league_id]
            if league is None:
                kept_draft_ids.append(draft_id)
                unknown_draft_ids.append(draft_id)
            elif not is_target_league(league) or not is_good_draft(draft, league):
                removed_draft_ids.append(draft_id)
                print(
                    "removing",
                    draft_id,
                    "league",
                    league_id,
                    "failed load_data filters",
                )
            else:
                week_one_matchups = sleeper_get(
                    session,
                    f"{API_BASE_URL}/league/{league_id}/matchups/1",
                )
                if week_one_matchups is None:
                    kept_draft_ids.append(draft_id)
                    unknown_draft_ids.append(draft_id)
                elif week_one_matchups and week_one_matchups[0].get("players"):
                    picks = sleeper_get(
                        session,
                        f"{API_BASE_URL}/draft/{draft_id}/picks",
                    )
                    if picks is None:
                        kept_draft_ids.append(draft_id)
                        unknown_draft_ids.append(draft_id)
                        continue

                    settings = draft.get("settings") or {}
                    expected_picks = (settings.get("teams") or 0) * (
                        settings.get("rounds") or 0
                    )
                    pick_numbers = (
                        {pick.get("pick_no") for pick in picks}
                        if isinstance(picks, list)
                        else set()
                    )
                    if (
                        isinstance(picks, list)
                        and expected_picks > 0
                        and len(picks) == expected_picks
                        and pick_numbers == set(range(1, expected_picks + 1))
                    ):
                        kept_draft_ids.append(draft_id)
                    else:
                        removed_draft_ids.append(draft_id)
                        print(
                            "removing",
                            draft_id,
                            "league",
                            league_id,
                            "incomplete draft",
                            "expected",
                            expected_picks,
                            "actual",
                            len(picks) if isinstance(picks, list) else None,
                        )
                else:
                    removed_draft_ids.append(draft_id)
                    print(
                        "removing",
                        draft_id,
                        "league",
                        league_id,
                        "missing week 1 player data",
                    )

            if index % 100 == 0:
                print(
                    "checked",
                    index,
                    "of",
                    len(draft_ids),
                    "removed",
                    len(removed_draft_ids),
                    "unknown",
                    len(unknown_draft_ids),
                )

    backup_path = QUALIFYING_DRAFT_IDS_PATH.with_suffix(".txt.bak")
    if not backup_path.exists():
        shutil.copy2(QUALIFYING_DRAFT_IDS_PATH, backup_path)

    temporary_path = QUALIFYING_DRAFT_IDS_PATH.with_suffix(".txt.tmp")
    temporary_path.write_text("\n".join(kept_draft_ids) + "\n")
    temporary_path.replace(QUALIFYING_DRAFT_IDS_PATH)

    print("kept", len(kept_draft_ids))
    print("removed", len(removed_draft_ids))
    print("unknown and kept", len(unknown_draft_ids))
    print("backup", backup_path)


if __name__ == "__main__":
    main()
