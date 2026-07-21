"""Build a researched NFL coaching table for the 2017-2024 seasons.

The input file is useful as a roster of names, but it sometimes puts the
offensive play-caller in the OC field.  This builder keeps those two jobs
separate and adds tenure/background fields used by the draft model.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "coordinators.json"
OUTPUT_PATH = ROOT / "data" / "clean" / "coordinators_2017_2024.csv"
FIRST_YEAR = 2017
LAST_YEAR = 2024
NO_OC = "NONE"


# Official OC corrections.  The source sometimes substitutes the head coach
# because that coach called plays, even though another person held the OC job.
OC_OVERRIDES = {
    (2017, "BUF"): "Rick Dennison",
    (2017, "CLE"): NO_OC,
    (2017, "HOU"): NO_OC,
    (2017, "NYJ"): "John Morton",
    (2017, "SF"): NO_OC,
    (2018, "HOU"): NO_OC,
    (2018, "LAR"): NO_OC,
    (2018, "SF"): NO_OC,
    (2019, "ARI"): NO_OC,
    (2019, "CLE"): "Todd Monken",
    (2019, "LAR"): NO_OC,
    (2019, "SF"): NO_OC,
    (2020, "ARI"): NO_OC,
    (2020, "DEN"): "Pat Shurmur",
    (2020, "PHI"): NO_OC,
    (2020, "SF"): NO_OC,
    (2021, "ARI"): NO_OC,
    (2021, "MIA"): "George Godsey / Eric Studesville",
    (2022, "ARI"): NO_OC,
    (2022, "DEN"): "Justin Outten",
    (2022, "NE"): NO_OC,
    (2022, "SF"): NO_OC,
    (2023, "SF"): NO_OC,
    (2024, "CAR"): "Brad Idzik",
    (2024, "CLE"): "Ken Dorsey",
    (2024, "DEN"): "Joe Lombardi",
    (2024, "GB"): "Adam Stenavich",
    (2024, "LAR"): "Mike LaFleur",
    (2024, "MIA"): "Frank Smith",
    (2024, "MIN"): "Wes Phillips",
    (2024, "SF"): NO_OC,
}


# Background means the coach's career identity on appointment, not whether the
# coach personally called plays in a particular season.
HC_BACKGROUND = {
    "Adam Gase": "offense",
    "Andy Reid": "offense",
    "Anthony Lynn": "offense",
    "Antonio Pierce": "ceo",
    "Arthur Smith": "offense",
    "Ben McAdoo": "offense",
    "Bill Belichick": "defense",
    "Bill O'Brien": "offense",
    "Brandon Staley": "defense",
    "Brian Callahan": "offense",
    "Brian Daboll": "offense",
    "Brian Flores": "defense",
    "Bruce Arians": "offense",
    "Chuck Pagano": "defense",
    "Dan Campbell": "ceo",
    "Dan Quinn": "defense",
    "Dave Canales": "offense",
    "David Culley": "ceo",
    "DeMeco Ryans": "defense",
    "Dennis Allen": "defense",
    "Dirk Koetter": "offense",
    "Doug Marrone": "offense",
    "Doug Pederson": "offense",
    "Frank Reich": "offense",
    "Freddie Kitchens": "offense",
    "Hue Jackson": "offense",
    "Jack Del Rio": "defense",
    "Jason Garrett": "offense",
    "Jay Gruden": "offense",
    "Jerod Mayo": "defense",
    "Jim Caldwell": "offense",
    "Jim Harbaugh": "offense",
    "Joe Judge": "special_teams",
    "John Fox": "defense",
    "John Harbaugh": "special_teams",
    "Jon Gruden": "offense",
    "Jonathan Gannon": "defense",
    "Josh McDaniels": "offense",
    "Kevin O'Connell": "offense",
    "Kevin Stefanski": "offense",
    "Kliff Kingsbury": "offense",
    "Kyle Shanahan": "offense",
    "Lovie Smith": "defense",
    "Marvin Lewis": "defense",
    "Matt Eberflus": "defense",
    "Matt LaFleur": "offense",
    "Matt Nagy": "offense",
    "Matt Patricia": "defense",
    "Matt Rhule": "ceo",
    "Mike Macdonald": "defense",
    "Mike McCarthy": "offense",
    "Mike McDaniel": "offense",
    "Mike Mularkey": "offense",
    "Mike Tomlin": "defense",
    "Mike Vrabel": "defense",
    "Mike Zimmer": "defense",
    "Nathaniel Hackett": "offense",
    "Nick Sirianni": "offense",
    "Pat Shurmur": "offense",
    "Pete Carroll": "defense",
    "Raheem Morris": "defense",
    "Robert Saleh": "defense",
    "Ron Rivera": "defense",
    "Sean McDermott": "defense",
    "Sean McVay": "offense",
    "Sean Payton": "offense",
    "Shane Steichen": "offense",
    "Steve Wilks": "defense",
    "Todd Bowles": "defense",
    "Urban Meyer": "offense",
    "Vance Joseph": "defense",
    "Vic Fangio": "defense",
    "Zac Taylor": "offense",
}


# (appointment season, previous organization, previous job)
# A baseline entry can predate 2017 because it describes the current tenure.
HC_TENURES = {
    ("ARI", "Bruce Arians"): (2013, "IND", "interim head coach / offensive coordinator"),
    ("ARI", "Steve Wilks"): (2018, "CAR", "defensive coordinator"),
    ("ARI", "Kliff Kingsbury"): (2019, "USC", "offensive coordinator / quarterbacks"),
    ("ARI", "Jonathan Gannon"): (2023, "PHI", "defensive coordinator"),
    ("ATL", "Dan Quinn"): (2015, "SEA", "defensive coordinator"),
    ("ATL", "Arthur Smith"): (2021, "TEN", "offensive coordinator"),
    ("ATL", "Raheem Morris"): (2024, "LAR", "defensive coordinator"),
    ("BAL", "John Harbaugh"): (2008, "PHI", "defensive backs coach"),
    ("BUF", "Sean McDermott"): (2017, "CAR", "defensive coordinator"),
    ("CAR", "Ron Rivera"): (2011, "LAC", "defensive coordinator"),
    ("CAR", "Matt Rhule"): (2020, "Baylor", "head coach"),
    ("CAR", "Frank Reich"): (2023, "IND", "head coach"),
    ("CAR", "Dave Canales"): (2024, "TB", "offensive coordinator"),
    ("CHI", "John Fox"): (2015, "DEN", "head coach"),
    ("CHI", "Matt Nagy"): (2018, "KC", "offensive coordinator"),
    ("CHI", "Matt Eberflus"): (2022, "IND", "defensive coordinator"),
    ("CIN", "Marvin Lewis"): (2003, "WAS", "defensive coordinator"),
    ("CIN", "Zac Taylor"): (2019, "LAR", "quarterbacks coach"),
    ("CLE", "Hue Jackson"): (2016, "CIN", "offensive coordinator"),
    ("CLE", "Freddie Kitchens"): (2019, "CLE", "offensive coordinator"),
    ("CLE", "Kevin Stefanski"): (2020, "MIN", "offensive coordinator"),
    ("DAL", "Jason Garrett"): (2010, "DAL", "offensive coordinator / interim head coach"),
    ("DAL", "Mike McCarthy"): (2020, "GB", "head coach"),
    ("DEN", "Vance Joseph"): (2017, "MIA", "defensive coordinator"),
    ("DEN", "Vic Fangio"): (2019, "CHI", "defensive coordinator"),
    ("DEN", "Nathaniel Hackett"): (2022, "GB", "offensive coordinator"),
    ("DEN", "Sean Payton"): (2023, "NO", "head coach"),
    ("DET", "Jim Caldwell"): (2014, "BAL", "offensive coordinator"),
    ("DET", "Matt Patricia"): (2018, "NE", "defensive coordinator"),
    ("DET", "Dan Campbell"): (2021, "NO", "assistant head coach / tight ends"),
    ("GB", "Mike McCarthy"): (2006, "SF", "offensive coordinator"),
    ("GB", "Matt LaFleur"): (2019, "TEN", "offensive coordinator"),
    ("HOU", "Bill O'Brien"): (2014, "Penn State", "head coach"),
    ("HOU", "David Culley"): (2021, "BAL", "assistant head coach / passing game / wide receivers"),
    ("HOU", "Lovie Smith"): (2022, "HOU", "defensive coordinator"),
    ("HOU", "DeMeco Ryans"): (2023, "SF", "defensive coordinator"),
    ("IND", "Chuck Pagano"): (2012, "BAL", "defensive coordinator"),
    ("IND", "Frank Reich"): (2018, "PHI", "offensive coordinator"),
    ("IND", "Shane Steichen"): (2023, "PHI", "offensive coordinator"),
    ("JAX", "Doug Marrone"): (2017, "JAX", "interim head coach / offensive line"),
    ("JAX", "Urban Meyer"): (2021, "Ohio State", "head coach"),
    ("JAX", "Doug Pederson"): (2022, "PHI", "head coach"),
    ("KC", "Andy Reid"): (2013, "PHI", "head coach"),
    ("LAC", "Anthony Lynn"): (2017, "BUF", "interim head coach / offensive coordinator"),
    ("LAC", "Brandon Staley"): (2021, "LAR", "defensive coordinator"),
    ("LAC", "Jim Harbaugh"): (2024, "Michigan", "head coach"),
    ("LAR", "Sean McVay"): (2017, "WAS", "offensive coordinator"),
    ("LV", "Jack Del Rio"): (2015, "DEN", "defensive coordinator"),
    ("LV", "Jon Gruden"): (2018, "TB", "head coach"),
    ("LV", "Josh McDaniels"): (2022, "NE", "offensive coordinator"),
    ("LV", "Antonio Pierce"): (2023, "LV", "linebackers coach / interim head coach"),
    ("MIA", "Adam Gase"): (2016, "CHI", "offensive coordinator"),
    ("MIA", "Brian Flores"): (2019, "NE", "linebackers coach / defensive play-caller"),
    ("MIA", "Mike McDaniel"): (2022, "SF", "offensive coordinator"),
    ("MIN", "Mike Zimmer"): (2014, "CIN", "defensive coordinator"),
    ("MIN", "Kevin O'Connell"): (2022, "LAR", "offensive coordinator"),
    ("NE", "Bill Belichick"): (2000, "NYJ", "assistant head coach / defensive coordinator"),
    ("NE", "Jerod Mayo"): (2024, "NE", "inside linebackers coach"),
    ("NO", "Sean Payton"): (2006, "DAL", "assistant head coach / quarterbacks"),
    ("NO", "Dennis Allen"): (2022, "NO", "defensive coordinator"),
    ("NYG", "Ben McAdoo"): (2016, "NYG", "offensive coordinator"),
    ("NYG", "Pat Shurmur"): (2018, "MIN", "offensive coordinator"),
    ("NYG", "Joe Judge"): (2020, "NE", "special teams coordinator / wide receivers"),
    ("NYG", "Brian Daboll"): (2022, "BUF", "offensive coordinator"),
    ("NYJ", "Todd Bowles"): (2015, "ARI", "defensive coordinator"),
    ("NYJ", "Adam Gase"): (2019, "MIA", "head coach"),
    ("NYJ", "Robert Saleh"): (2021, "SF", "defensive coordinator"),
    ("PHI", "Doug Pederson"): (2016, "KC", "offensive coordinator"),
    ("PHI", "Nick Sirianni"): (2021, "IND", "offensive coordinator"),
    ("PIT", "Mike Tomlin"): (2007, "MIN", "defensive coordinator"),
    ("SEA", "Pete Carroll"): (2010, "USC", "head coach"),
    ("SEA", "Mike Macdonald"): (2024, "BAL", "defensive coordinator"),
    ("SF", "Kyle Shanahan"): (2017, "ATL", "offensive coordinator"),
    ("TB", "Dirk Koetter"): (2016, "TB", "offensive coordinator"),
    ("TB", "Bruce Arians"): (2019, "ARI", "head coach"),
    ("TB", "Todd Bowles"): (2022, "TB", "defensive coordinator"),
    ("TEN", "Mike Mularkey"): (2016, "TEN", "interim head coach / assistant head coach"),
    ("TEN", "Mike Vrabel"): (2018, "HOU", "defensive coordinator"),
    ("TEN", "Brian Callahan"): (2024, "CIN", "offensive coordinator"),
    ("WAS", "Jay Gruden"): (2014, "CIN", "offensive coordinator"),
    ("WAS", "Ron Rivera"): (2020, "CAR", "head coach"),
    ("WAS", "Dan Quinn"): (2024, "DAL", "defensive coordinator"),
}


# OC tenure metadata.  Entries are keyed by the season and team where that
# tenure first appears in this dataset.  Midseason appointments retain their
# actual appointment year (for example, Bill Lazor and Joe Brady).
OC_HIRES = {
    # 2017 baselines
    (2017, "ARI"): (2013, "IND", "offensive line coach"),
    (2017, "ATL"): (2017, "Alabama", "offensive coordinator"),
    (2017, "BAL"): (2016, "BAL", "quarterbacks coach"),
    (2017, "BUF"): (2017, "DEN", "offensive coordinator"),
    (2017, "CAR"): (2013, "CAR", "quarterbacks coach"),
    (2017, "CHI"): (2016, "CHI", "quarterbacks coach"),
    (2017, "CIN"): (2016, "CIN", "quarterbacks coach"),
    (2017, "DAL"): (2014, "DET", "offensive coordinator"),
    (2017, "DEN"): (2017, "LAC", "head coach"),
    (2017, "DET"): (2015, "DET", "quarterbacks coach"),
    (2017, "GB"): (2015, "GB", "wide receivers coach"),
    (2017, "IND"): (2016, "IND", "associate head coach"),
    (2017, "JAX"): (2016, "JAX", "quarterbacks coach"),
    (2017, "KC"): (2016, "KC", "quarterbacks coach"),
    (2017, "LAC"): (2016, "TEN", "head coach"),
    (2017, "LAR"): (2017, "ATL", "quarterbacks coach"),
    (2017, "LV"): (2017, "LV", "quarterbacks coach"),
    (2017, "MIA"): (2016, "IND", "quarterbacks coach"),
    (2017, "MIN"): (2016, "MIN", "tight ends coach / interim offensive coordinator"),
    (2017, "NE"): (2012, "LAR", "offensive coordinator"),
    (2017, "NO"): (2009, "NO", "quarterbacks coach"),
    (2017, "NYG"): (2016, "NYG", "quarterbacks coach"),
    (2017, "NYJ"): (2017, "NO", "wide receivers coach"),
    (2017, "PHI"): (2016, "LAC", "offensive coordinator"),
    (2017, "PIT"): (2012, "KC", "head coach"),
    (2017, "SEA"): (2011, "MIN", "offensive coordinator"),
    (2017, "TB"): (2016, "Southern Miss", "head coach"),
    (2017, "TEN"): (2016, "ATL", "assistant head coach / wide receivers"),
    (2017, "WAS"): (2017, "WAS", "quarterbacks coach"),
    # New tenures from 2018 onward
    (2018, "ARI"): (2018, "DEN", "offensive coordinator"),
    (2018, "BUF"): (2018, "Alabama", "offensive coordinator"),
    (2018, "CAR"): (2018, "MIN", "offensive coordinator"),
    (2018, "CHI"): (2018, "Oregon", "head coach"),
    (2018, "CIN"): (2017, "CIN", "quarterbacks coach"),
    (2018, "CLE"): (2018, "PIT", "offensive coordinator"),
    (2018, "DEN"): (2017, "DEN", "quarterbacks coach"),
    (2018, "GB"): (2018, "IND", "assistant head coach / offensive line"),
    (2018, "IND"): (2018, "LAC", "wide receivers coach"),
    (2018, "KC"): (2018, "KC", "running backs coach"),
    (2018, "LV"): (2018, "LAR", "quarterbacks coach"),
    (2018, "MIA"): (2018, "CHI", "offensive coordinator"),
    (2018, "MIN"): (2018, "PHI", "quarterbacks coach"),
    (2018, "NYG"): (2018, "CAR", "offensive coordinator"),
    (2018, "NYJ"): (2018, "NYJ", "quarterbacks coach"),
    (2018, "PHI"): (2018, "PHI", "wide receivers coach"),
    (2018, "PIT"): (2018, "PIT", "quarterbacks coach"),
    (2018, "SEA"): (2018, "IND", "quarterbacks coach"),
    (2018, "TEN"): (2018, "LAR", "offensive coordinator"),
    (2019, "ATL"): (2019, "TB", "head coach"),
    (2019, "BAL"): (2019, "BAL", "tight ends / assistant head coach"),
    (2019, "CIN"): (2019, "LV", "quarterbacks coach"),
    (2019, "CLE"): (2019, "TB", "offensive coordinator"),
    (2019, "DAL"): (2019, "DAL", "quarterbacks coach"),
    (2019, "DEN"): (2019, "SF", "quarterbacks coach"),
    (2019, "DET"): (2019, "SEA", "offensive coordinator"),
    (2019, "GB"): (2019, "JAX", "offensive coordinator"),
    (2019, "HOU"): (2019, "HOU", "tight ends coach"),
    (2019, "JAX"): (2019, "MIN", "offensive coordinator"),
    (2019, "MIA"): (2019, "NE", "wide receivers coach"),
    (2019, "MIN"): (2018, "MIN", "quarterbacks coach"),
    (2019, "NYJ"): (2019, "MIA", "offensive coordinator"),
    (2019, "TB"): (2019, "ARI", "offensive coordinator"),
    (2019, "TEN"): (2019, "TEN", "tight ends coach"),
    (2019, "WAS"): (2019, "WAS", "quarterbacks coach"),
    (2020, "CAR"): (2020, "LSU", "passing game coordinator / wide receivers"),
    (2020, "CHI"): (2020, "Penn State", "offensive analyst"),
    (2020, "CLE"): (2020, "CIN", "quarterbacks coach"),
    (2020, "DEN"): (2020, "NYG", "head coach"),
    (2020, "JAX"): (2020, "WAS", "head coach"),
    (2020, "LAC"): (2019, "LAC", "quarterbacks coach / interim offensive coordinator"),
    (2020, "LAR"): (2020, "WAS", "offensive coordinator"),
    (2020, "MIA"): (2020, "NYJ", "offensive coordinator"),
    (2020, "MIN"): (2020, "MIN", "assistant head coach / offensive adviser"),
    (2020, "NYG"): (2020, "DAL", "head coach"),
    (2020, "WAS"): (2020, "CAR", "quarterbacks coach"),
    (2021, "ATL"): (2021, "CHI", "passing game coordinator / quarterbacks"),
    (2021, "DET"): (2021, "LAC", "head coach"),
    (2021, "IND"): (2021, "IND", "quarterbacks coach"),
    (2021, "JAX"): (2021, "DET", "offensive coordinator / interim head coach"),
    (2021, "LAC"): (2021, "NO", "quarterbacks coach"),
    (2021, "MIA"): (2021, "MIA", "tight ends coach / running backs coach"),
    (2021, "MIN"): (2021, "MIN", "quarterbacks coach"),
    (2021, "NYJ"): (2021, "SF", "passing game coordinator"),
    (2021, "PHI"): (2021, "LAC", "offensive coordinator"),
    (2021, "PIT"): (2021, "PIT", "quarterbacks coach"),
    (2021, "SEA"): (2021, "LAR", "passing game coordinator"),
    (2021, "SF"): (2021, "SF", "run game coordinator"),
    (2021, "TEN"): (2021, "TEN", "tight ends coach"),
    (2022, "BUF"): (2022, "BUF", "quarterbacks coach"),
    (2022, "CAR"): (2022, "DAL", "consultant"),
    (2022, "CHI"): (2022, "GB", "quarterbacks / passing game coordinator"),
    (2022, "DEN"): (2022, "GB", "tight ends coach"),
    (2022, "DET"): (2022, "DET", "tight ends / passing game coordinator"),
    (2022, "GB"): (2022, "GB", "offensive line / run game coordinator"),
    (2022, "HOU"): (2022, "HOU", "quarterbacks / passing game coordinator"),
    (2022, "JAX"): (2022, "IND", "senior offensive assistant"),
    (2022, "LAR"): (2022, "Kentucky", "offensive coordinator"),
    (2022, "LV"): (2022, "NE", "wide receivers coach"),
    (2022, "MIA"): (2022, "LAC", "run game coordinator / offensive line"),
    (2022, "MIN"): (2022, "LAR", "tight ends / passing game coordinator"),
    (2022, "NYG"): (2022, "KC", "quarterbacks / passing game coordinator"),
    (2023, "ARI"): (2023, "CLE", "quarterbacks coach"),
    (2023, "BAL"): (2023, "Georgia", "offensive coordinator"),
    (2023, "CAR"): (2023, "LAR", "assistant head coach / tight ends"),
    (2023, "DAL"): (2023, "DAL", "consultant"),
    (2023, "DEN"): (2023, "LAC", "offensive coordinator"),
    (2023, "HOU"): (2023, "SF", "passing game coordinator"),
    (2023, "IND"): (2023, "JAX", "passing game coordinator"),
    (2023, "KC"): (2023, "KC", "quarterbacks coach"),
    (2023, "LAC"): (2023, "DAL", "offensive coordinator"),
    (2023, "LAR"): (2023, "NYJ", "offensive coordinator"),
    (2023, "NE"): (2023, "Alabama", "offensive coordinator"),
    (2023, "NYJ"): (2023, "DEN", "head coach"),
    (2023, "PHI"): (2023, "PHI", "quarterbacks coach"),
    (2023, "TB"): (2023, "SEA", "quarterbacks coach"),
    (2023, "TEN"): (2023, "TEN", "passing game coordinator"),
    (2023, "WAS"): (2023, "KC", "offensive coordinator"),
    (2024, "ATL"): (2024, "LAR", "quarterbacks / passing game coordinator"),
    (2024, "BUF"): (2023, "BUF", "quarterbacks coach / interim offensive coordinator"),
    (2024, "CAR"): (2024, "TB", "wide receivers coach"),
    (2024, "CHI"): (2024, "SEA", "offensive coordinator"),
    (2024, "CIN"): (2024, "CIN", "quarterbacks coach"),
    (2024, "CLE"): (2024, "BUF", "offensive coordinator"),
    (2024, "LAC"): (2024, "BAL", "offensive coordinator"),
    (2024, "LV"): (2024, "CHI", "offensive coordinator"),
    (2024, "NE"): (2024, "CLE", "offensive coordinator"),
    (2024, "NO"): (2024, "SF", "passing game coordinator"),
    (2024, "PHI"): (2024, "LAC", "offensive coordinator"),
    (2024, "PIT"): (2024, "ATL", "head coach"),
    (2024, "SEA"): (2024, "Washington", "offensive coordinator"),
    (2024, "TB"): (2024, "Kentucky", "offensive coordinator"),
    (2024, "TEN"): (2024, "JAX", "passing game coordinator"),
    (2024, "WAS"): (2024, "USC", "senior offensive analyst"),
}


# Opening-day offensive play-callers.  This avoids retroactively changing a
# season because duties moved after the season began.
HC_PLAYCALLER = {
    (2017, t) for t in {"ARI", "CLE", "GB", "HOU", "KC", "LAR", "MIA", "NO", "NYG", "PHI", "SF", "TB", "WAS"}
} | {
    (2018, t) for t in {"CHI", "GB", "HOU", "IND", "KC", "LAR", "LV", "MIA", "NO", "NYG", "PHI", "SF", "TB", "WAS"}
} | {
    (2019, t) for t in {"ARI", "CHI", "CIN", "CLE", "GB", "HOU", "IND", "KC", "LAR", "LV", "NO", "NYG", "NYJ", "PHI", "SF", "WAS"}
} | {
    (2020, t) for t in {"ARI", "CHI", "CIN", "CLE", "GB", "IND", "KC", "LAR", "LV", "NO", "NYJ", "PHI", "SF"}
} | {
    (2021, t) for t in {"ARI", "ATL", "CHI", "CIN", "CLE", "GB", "IND", "KC", "LAR", "LV", "NO", "PHI", "SF"}
} | {
    (2022, t) for t in {"ARI", "ATL", "CIN", "CLE", "DEN", "GB", "IND", "JAX", "KC", "LAR", "LV", "MIA", "MIN", "SF"}
} | {
    (2023, t) for t in {"ATL", "CAR", "CIN", "CLE", "DAL", "DEN", "IND", "KC", "LAR", "LV", "MIA", "MIN", "SF"}
} | {
    (2024, t) for t in {"CAR", "CIN", "CLE", "DAL", "DEN", "GB", "IND", "KC", "LAR", "MIA", "MIN", "NYG", "SF", "TEN"}
}


# The Patriots had no titled OC in 2022.  Matt Patricia was the primary caller.
PLAYCALLER_OVERRIDES = {
    (2021, "MIA"): "George Godsey / Eric Studesville",
    (2022, "NE"): "Matt Patricia",
}


FIELDNAMES = [
    "year",
    "team",
    "head_coach",
    "offensive_coordinator",
    "offensive_playcaller",
    "prev_hc_team",
    "prev_oc_team",
    "hc_previous_role",
    "oc_previous_role",
    "hc_background",
    "hc_offense",
    "hc_playcaller",
    "oc_playcaller",
    "hired",
    "oc_hired",
    "hc_new_hire",
    "oc_new_hire",
]


def load_source_rows() -> list[dict]:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    rows = [
        row
        for row in payload["coordinators"]
        if FIRST_YEAR <= int(row["year"]) <= LAST_YEAR
    ]
    return sorted(rows, key=lambda row: (int(row["year"]), row["team"]))


def official_oc(row: dict) -> str:
    key = (int(row["year"]), row["team"])
    return OC_OVERRIDES.get(key, row["oc"].replace(" (McCarthy called)", ""))


def build_rows() -> list[dict]:
    output = []
    active_oc_tenure: dict[str, tuple[int, str, str]] = {}
    prior_hc: dict[str, str] = {}
    prior_oc: dict[str, str] = {}

    for source in load_source_rows():
        year = int(source["year"])
        team = source["team"]
        hc = source["hc"]
        oc = official_oc(source)

        hired, prev_hc_team, hc_previous_role = HC_TENURES[(team, hc)]
        hc_background = HC_BACKGROUND[hc]

        if oc == NO_OC:
            active_oc_tenure.pop(team, None)
            oc_hired, prev_oc_team, oc_previous_role = "", "", ""
        elif (year, team) in OC_HIRES:
            active_oc_tenure[team] = OC_HIRES[(year, team)]
            oc_hired, prev_oc_team, oc_previous_role = active_oc_tenure[team]
        else:
            oc_hired, prev_oc_team, oc_previous_role = active_oc_tenure[team]

        hc_calls = (year, team) in HC_PLAYCALLER
        playcaller = PLAYCALLER_OVERRIDES.get(
            (year, team), hc if hc_calls else oc
        )
        oc_calls = oc != NO_OC and playcaller == oc
        hc_new_hire = (
            hired == year if year == FIRST_YEAR else prior_hc.get(team) != hc
        )
        oc_new_hire = oc != NO_OC and (
            oc_hired == year
            if year == FIRST_YEAR
            else prior_oc.get(team) != oc
        )

        output.append(
            {
                "year": year,
                "team": team,
                "head_coach": hc,
                "offensive_coordinator": oc,
                "offensive_playcaller": playcaller,
                "prev_hc_team": prev_hc_team,
                "prev_oc_team": prev_oc_team,
                "hc_previous_role": hc_previous_role,
                "oc_previous_role": oc_previous_role,
                "hc_background": hc_background,
                "hc_offense": str(hc_background == "offense").lower(),
                "hc_playcaller": str(hc_calls).lower(),
                "oc_playcaller": str(oc_calls).lower(),
                "hired": hired,
                "oc_hired": oc_hired,
                "hc_new_hire": str(hc_new_hire).lower(),
                "oc_new_hire": str(oc_new_hire).lower(),
            }
        )
        prior_hc[team] = hc
        prior_oc[team] = oc

    return output


def validate(rows: list[dict]) -> None:
    expected_count = (LAST_YEAR - FIRST_YEAR + 1) * 32
    assert len(rows) == expected_count, (len(rows), expected_count)
    assert len({(row["year"], row["team"]) for row in rows}) == expected_count
    assert all(row["head_coach"] for row in rows)
    assert all(row["offensive_coordinator"] for row in rows)
    assert all(row["offensive_playcaller"] for row in rows)
    assert all(int(row["hired"]) <= int(row["year"]) for row in rows)
    assert all(
        not row["oc_hired"] or int(row["oc_hired"]) <= int(row["year"])
        for row in rows
    )
    for field in ("hc_offense", "hc_playcaller", "oc_playcaller", "hc_new_hire", "oc_new_hire"):
        assert {row[field] for row in rows} <= {"true", "false"}


def main() -> None:
    rows = build_rows()
    validate(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
