# Fantasy Football Draft Data Project Notes

Research date: 2026-06-30

## Goal

Build a dataset for fantasy football draft modeling, similar to the video transcript project.

Core modeling question:

What makes a good fantasy football draft pick?

The video framed a good pick as a function of:

- Player expected performance
- Positional importance
- What has happened earlier in the draft
- What is likely to happen after the pick

The target label in the video was team scoring over the first 12 weeks, not just individual player fantasy points. Reason: the goal is drafting a good team, and later-season team results become less tied to the original draft because of waivers, trades, injuries, and lineup changes.

## Video Method Summary

The video creator said they used Sleeper because Sleeper makes public fantasy league data available through an API.

Reported data scale:

- Over 500,000 Sleeper leagues accessed from 2018-2023
- After filtering, roughly 50,000-60,000 useful leagues
- After more cleanup, about 1.8 million draft picks

Likely league filters:

- Redraft leagues only
- Normal-ish roster settings
- Normal-ish scoring settings, likely PPR or half/full PPR
- Completed drafts
- Remove weird roster sizes
- Remove very unusual scoring
- Remove keeper/dynasty/auction/best-ball leagues unless intentionally modeling them

## Sleeper Data Source

Sleeper is the best source found for actual historical fantasy draft picks.

Sleeper API notes:

- Public read-only API
- No authentication token needed
- Rate limit guidance: stay under 1000 calls per minute
- Supports old seasons
- No official bulk endpoint found for "all users" or "all leagues"

Useful Sleeper endpoints:

- `GET /v1/user/<username_or_user_id>`
- `GET /v1/user/<user_id>/leagues/nfl/<season>`
- `GET /v1/league/<league_id>/users`
- `GET /v1/league/<league_id>/drafts`
- `GET /v1/draft/<draft_id>/picks`
- `GET /v1/league/<league_id>/matchups/<week>`
- `GET /v1/players/nfl`

Important catch:

Sleeper does not appear to provide a public "give me every league" endpoint. To collect many leagues, use graph crawling from seed users.

Official docs:

- https://docs.sleeper.com/

## Getting Sleeper User IDs

There is no official endpoint found for listing all Sleeper users.

Practical method: graph crawl.

1. Start with seed Sleeper usernames or user IDs.
2. Resolve each username/user ID through Sleeper's user endpoint.
3. Fetch that user's leagues for target seasons.
4. For each league, fetch league users.
5. Add new user IDs to the crawl queue.
6. Deduplicate users and leagues.
7. Repeat until enough leagues/drafts are collected.

Seed sources:

- Own Sleeper username
- Friends' Sleeper usernames
- Public fantasy creators who share Sleeper leagues
- Public league invite links/screenshots
- Previously exported Sleeper league IDs

Avoid random brute-forcing user IDs. Sleeper IDs are huge numeric IDs, so random guessing is low-yield and noisy.

## Data Needed

Raw API data to store first:

- Users
- Leagues
- League users
- Drafts
- Draft picks
- Rosters
- Matchups
- Players
- League settings
- Scoring settings
- Roster positions

Clean modeling tables later:

- One row per draft pick
- League context features
- Draft state before pick
- Player features
- Team outcome label

## Draft Pick Features From Transcript

Player/performance features:

- Overall ADP
- Positional ADP
- Years of experience
- Position

League context:

- Number of teams
- Draft slot
- Pick number
- Round number
- Roster settings
- Number of required starters by position
- Number of flex spots
- Scoring format

Draft state before current pick:

- Number of QBs/RBs/WRs/TEs drafted so far
- Number of players drafted at each position
- How many teams have filled required QB/RB/WR/TE/FLEX needs
- Best available player at each position by ADP
- Best available overall player by ADP
- Current team roster construction
- League-wide positional scarcity

Possible future-draft approximation:

- Remaining teams before next pick
- Teams likely to need each position
- ADP gaps between current player and next players at same position
- Positional runs already happening

## Outcome Label Idea

Target from transcript:

- Median team points over weeks 1-12

Why first 12 weeks:

- More stable than only week 1
- More tied to draft than weeks 13-17
- Avoids too much noise from playoffs, waivers, trades, and late-season roster churn

Need normalize team scores by league format. Example: 120 points in a one-flex league is more impressive than 120 points in a three-flex league.

Possible normalization:

- Team weekly points divided by league weekly average
- Team weekly points z-score within league/week
- Median normalized team score over weeks 1-12
- Percentile rank within league over weeks 1-12

## ADP Sources

ADP is useful as "wisdom of the crowd" for expected player value.

Sources found:

- FantasyPros historical ADP
- Fantasy Football Calculator historical ADP
- Sleeper ADP may be included through FantasyPros source breakdowns

FantasyPros:

- Historical NFL ADP pages exist by year
- Useful for overall ADP and positional ADP
- https://www.fantasypros.com/nfl/adp/

Fantasy Football Calculator:

- Historical ADP going back many years
- Says data is based on real human mock draft selections
- https://fantasyfootballcalculator.com/adp

## Other Possible Draft Data Sources

### ffscrapr

R package that wraps multiple fantasy APIs and returns tidy fantasy data.

Useful if exploring data before building custom Python pipeline.

Supports:

- Sleeper
- MyFantasyLeague
- Fleaflicker
- ESPN

Docs:

- https://ffscrapr.ffverse.com/

### MyFantasyLeague

Potentially useful backup source.

Pros:

- Long-running fantasy platform
- API exists
- Public league search may make discovery easier than Sleeper

Cons:

- More complex league formats
- Older platform quirks
- May require more cleanup

### Fleaflicker

Has public API docs and draft board endpoint.

Useful endpoint:

- `FetchLeagueDraftBoard`

Docs:

- https://www.fleaflicker.com/api-docs/index.html

### ESPN/Yahoo

Poor fit for broad public historical dataset.

Problems:

- More private/authenticated
- Harder bulk access
- Less open than Sleeper

## Python Feasibility

This project is very doable in Python.

Hard part is not Python. Hard part is:

- Discovering enough users/leagues
- Avoiding duplicate data
- Respecting rate limits
- Cleaning weird league formats
- Matching historical player IDs and ADP
- Building correct draft-state features
- Avoiding target leakage

Good Python stack:

- `httpx` or `requests` for API calls
- `sqlite` or `duckdb` for local storage
- `pandas` for exploration
- `polars` if data gets large
- `pyarrow` / parquet for saved datasets
- `tenacity` or custom retry logic for API reliability

Project rule:

- Use `.venv` for pip installs.
- Never run bare `pip`.

## Suggested Storage Tables

Raw tables:

- `crawl_users`
- `users`
- `leagues`
- `league_users`
- `drafts`
- `draft_picks`
- `rosters`
- `matchups`
- `players`
- `crawl_state`

Derived tables:

- `clean_leagues`
- `clean_draft_picks`
- `team_week_scores`
- `team_12_week_outcomes`
- `pick_features`
- `player_adp`

## Crawl Strategy

Start small:

1. Pick one seed user.
2. Crawl 2023 leagues.
3. Fetch league users.
4. Expand to 100-500 users.
5. Fetch drafts and picks.
6. Store all raw responses.
7. Build first clean draft-pick table.

Then scale:

1. Add seasons 2018-2023.
2. Expand user graph.
3. Add league filters.
4. Add matchup outcomes.
5. Add ADP joins.
6. Add feature generation.

Important implementation note:

Always store raw API responses or raw normalized tables before cleaning. If a filter or feature is wrong later, raw data avoids needing to crawl again.

## Main Risks

- Sleeper crawl may grow slowly without good seed users.
- Public API can change or rate-limit.
- Old player IDs and names may not perfectly match ADP sources.
- Keeper/dynasty leagues can pollute redraft model.
- Draft pick quality is hard to evaluate against human alternatives.
- Team points include manager behavior after draft: starts, waivers, trades, injuries.
- ADP data must match the correct season and scoring format.
- Need avoid using information unavailable at draft time.

## First Milestone

Build a tiny proof of concept:

- One seed user
- One season
- 50-100 leagues
- Draft metadata
- Draft picks
- Basic league filters
- Save to local database or parquet

Success criteria:

- Can produce a table with one row per pick
- Columns include `league_id`, `draft_id`, `season`, `pick_no`, `round`, `draft_slot`, `roster_id`, `player_id`, `picked_by`
- Can count drafts, picks, leagues, and unique players
- Can identify incomplete or unusual drafts

## Second Milestone

Add team outcomes:

- Fetch weeks 1-12 matchups
- Compute team weekly points
- Normalize within league/week
- Aggregate to team outcome
- Join each pick to drafting team's outcome

## Third Milestone

Add modeling features:

- Join historical ADP
- Add positional ADP
- Add draft-state features before each pick
- Add team roster construction before each pick
- Add positional scarcity features

## Open Questions

- Which seasons should be included first?
- Redraft only, or include keeper/dynasty later?
- PPR only, half-PPR, standard, or all with scoring normalization?
- Should outcome be total points, median weekly score, win rate, or playoff rate?
- Should model predict pick value, full-team outcome, or next-best-pick comparison?
- How many leagues are enough for first useful experiment?
