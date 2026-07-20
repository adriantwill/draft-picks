from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

CRAWL_DATA_DIR = DATA_DIR / "crawl"
SEEN_USER_IDS_PATH = CRAWL_DATA_DIR / "seen_users.txt"
QUALIFYING_DRAFT_IDS_PATH = CRAWL_DATA_DIR / "good_drafts.txt"
SEEN_LEAGUE_IDS_PATH = CRAWL_DATA_DIR / "seen_leagues.txt"
PENDING_USER_IDS_PATH = CRAWL_DATA_DIR / "pending_users.txt"

CLEAN_DATA_DIR = DATA_DIR / "clean"
ADP_WITH_FINISH_CSV_PATH = CLEAN_DATA_DIR / "merged.csv"
ADP_CSV_PATH = CLEAN_DATA_DIR / "adp_all.csv"
DRAFTS_METADATA_PATH = CLEAN_DATA_DIR / "drafts_metadata.json"

SCRAPE_DATA_DIR = DATA_DIR / "scrape"
ADP_SCRAPE_DIR = SCRAPE_DATA_DIR / "adp"
FINISH_SCRAPE_DIR = SCRAPE_DATA_DIR / "finsh"
NFL_PLAYERS_JSON_PATH = SCRAPE_DATA_DIR / "nfl.json"
