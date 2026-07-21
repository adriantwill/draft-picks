import shutil
import time
from typing import Any

import requests

from src.path import QUALIFYING_DRAFT_IDS_PATH


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
    league_start_weeks: dict[str, int | None] = {}

    with requests.Session() as session:
        for index, draft_id in enumerate(draft_ids, start=1):
            draft = sleeper_get(session, f"{API_BASE_URL}/draft/{draft_id}")
            if not isinstance(draft, dict) or not draft.get("league_id"):
                kept_draft_ids.append(draft_id)
                unknown_draft_ids.append(draft_id)
                continue

            league_id = draft["league_id"]
            if league_id not in league_start_weeks:
                league = sleeper_get(session, f"{API_BASE_URL}/league/{league_id}")
                if isinstance(league, dict):
                    settings = league.get("settings") or {}
                    league_start_weeks[league_id] = settings.get("start_week")
                else:
                    league_start_weeks[league_id] = None

            start_week = league_start_weeks[league_id]
            if start_week is None:
                kept_draft_ids.append(draft_id)
                unknown_draft_ids.append(draft_id)
            elif start_week == 1:
                kept_draft_ids.append(draft_id)
            else:
                removed_draft_ids.append(draft_id)
                print(
                    "removing",
                    draft_id,
                    "league",
                    league_id,
                    "start_week",
                    start_week,
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
