import time
from pathlib import Path

import requests

REQUESTS_PER_MINUTE = 600
SECONDS_PER_REQUEST = 60 / REQUESTS_PER_MINUTE

last_request_time = 0.0


def sleeper_get(url: str, retries: int = 3):
    global last_request_time

    for attempt in range(retries):
        try:
            elapsed = time.monotonic() - last_request_time
            wait_time = SECONDS_PER_REQUEST - elapsed
            if wait_time > 0:
                time.sleep(wait_time)

            last_request_time = time.monotonic()
            response = requests.get(
                url,
                timeout=20,  # verify=False
            )
            response.raise_for_status()
            return response.json()

        except (requests.exceptions.RequestException, ValueError) as e:
            print("request failed, retrying", attempt + 1, type(e).__name__, url)
            time.sleep(5 * (attempt + 1))

    print("failed after retries", url)
    return None


def load_ids(path: str) -> set[str]:
    file = Path(path)
    if not file.exists():
        return set()
    return set(file.read_text().splitlines())
