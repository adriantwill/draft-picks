# Fantasy Football Draft Data Project Notes

Last updated: 2026-07-17

## Goal

Build a contextual draft decision model that recommends the best available player at each pick.

Core modeling question:

> Given everything known at this moment in the draft, which available candidate gives this team the best expected final result?

This is not a player-performance prediction model. Player projections, prior-year statistics, team changes, and similar inputs are intentionally delegated to ADP. ADP acts as a strong market prior built from the combined judgment of many fantasy players. The model's job is to learn when draft context should change the ADP ordering.

A good pick is modeled as a function of:

- Player expected performance
- Positional importance
- What has happened earlier in the draft
- What is likely to happen after the pick

Expected behavior:

- Early rounds should usually stay close to ADP because little team-specific context exists.
- Later rounds should react more to value, current roster construction, positional runs, league needs, and remaining alternatives.
- Every available candidate should be scored against the same current draft state.
- The recommendation should maximize expected team outcome, not individual player points.

## Modeling Strategy

One training row represents an observed pick:

- State immediately before the pick
- Candidate who was selected
- State or scarcity implied immediately after selecting that candidate
- Final team-level outcome used as the label

At inference time:

1. Capture current draft and roster state.
2. Create one candidate row for every available player.
3. Simulate selecting each candidate.
4. Recalculate candidate-specific roster fit and remaining-player scarcity.
5. Score all candidates.
6. Recommend the candidate with the highest expected team outcome.

Historical data contains only the action actually taken, not outcomes for every alternative action. The model therefore learns associations between observed decisions and later team success. This is useful, but it is not proof that an unchosen alternative would have performed worse.

Target league filters:

- Redraft leagues only
- 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX 
- Full PPR scoring 
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

## Draft Pick Features

### Candidate and market-value features

- Overall ADP
- Overall ADP rank
- Positional rank
- Position

Possible later experiment:

- Years of experience interacted with draft phase. This may distinguish late-round upside bets from stable veterans, but it should only be added after the ADP baseline works.

ADP, overall rank, and positional rank are correlated but not identical:

- ADP preserves distance between players.
- Overall rank preserves ordering but loses distance.
- Positional rank describes the candidate relative to alternatives at the same position.
- A model comparison should test ADP alone, ADP plus positional rank, and all three. Keep extra features only if held-out drafts improve.

### League context

- Number of teams
- Draft slot
- Pick number
- Round number
- Roster settings
- Number of required starters by position
- Number of flex spots
- Scoring format

The first supported formats should remain tightly filtered. The current effective league filter is full PPR, four-point passing touchdowns, one QB, two RB, two WR, one TE, one FLEX, redraft, non-best-ball, and 10-12 teams.

### Draft state before current pick

- Raw number of QBs/RBs/WRs/TEs drafted so far
- Positional picks divided by team count
- Positional share of all previous picks
- How many teams have filled required QB/RB/WR/TE/FLEX needs
- Current team roster construction
- Current team starter slots filled by position
- Current team bench depth by position
- Positional runs already happening

Personal position counts are useful as raw counts because roster rules are controlled. League-wide counts should include normalized versions because, for example, 30 drafted WRs means 3.0 per team in a 10-team league but only 2.14 per team in a 14-team league.

### Candidate-specific future context

- Best available player at each position after selecting the candidate
- Best available overall player after selecting the candidate
- Remaining teams before next pick
- Teams likely to need each position
- Candidate ADP gap versus the next player at the same position
- Candidate value relative to current pick
- Expected chance that comparable options survive until this team's next pick

The existing `next_best_*` idea is on the right track because it describes what remains after the candidate is removed. Training and live prediction must calculate this feature with identical timing and semantics.

### Required candidate-state interactions

At one live pick, `pick_no`, team position counts, and league position counts are constant for every candidate. These state features cannot change candidate ordering in a plain linear model unless they interact with candidate features.

Important interactions include:

- Candidate position x own count at that position
- Candidate position x open starter slots at that position
- Candidate position x league-wide count at that position
- Candidate position x teams still needing that position
- Candidate position x next-best value at that position
- Candidate ADP x pick or round
- Candidate experience x pick or round

These interactions let the model learn ideas such as "another WR is less useful after this team already drafted four WRs" or "ADP matters more early than late." Alternatives are explicit interaction columns, separate models by draft phase, or a nonlinear model such as gradient-boosted trees. Linear regression remains a useful interpretable baseline.

## Outcome Label Idea

Preferred target:

- Normalized team scoring over an early-season window, initially weeks 1-12

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

Weekly within-league z-score direction is good because it compares teams against their actual competition and league format. Current code uses all 17 weeks, while the intended first target uses weeks 1-12. Choose the window before large-scale outcome collection.

Current code multiplies each weekly team z-score by the fraction of starters who were originally drafted. This does not cleanly measure either team strength or drafted-player production. In particular, multiplying a negative z-score by a small fraction moves a bad result toward zero and can make it look better. Prefer one clear label first:

- Unweighted team scoring z-score for team outcome, or
- A separately computed score using points contributed by originally drafted players

Keep drafted-starter retention as a diagnostic or separate feature/target rather than multiplying it into team performance without validating the meaning.

## ADP Sources

ADP is the market's aggregated estimate of player value. Treat it as the model's prior, not literal ground truth. The model should improve candidate decisions by adding roster fit and draft context rather than trying to rebuild player projections.

FantasyPros Source:

- Historical NFL best ball ADP pages exist by year
- Useful for overall ADP and positional ADP
- https://www.fantasypros.com/nfl/adp/

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

## Current Training Function Review

### Good direction

- Uses ADP as player-value baseline instead of attempting a second player projection model.
- Builds one row per observed decision.
- Captures current team's position counts before each pick.
- Captures league-wide position counts before each pick.
- Adds per-team and per-pick positional rates for league-size and draft-stage context.
- Encodes candidate position with separate indicator columns.
- Attempts to remove previous selections and calculate remaining alternatives after the candidate pick.
- Adds candidate-to-next-best positional ADP gap.
- Uses team-level performance rather than assigning individual fantasy points as the objective.
- Filters league formats, reducing unrelated variation.
- Computes overall and positional ranks after sorting within season.

### Current blockers before `df` is trainable

- `data/drafts_metadata.json` is currently absent, so the produced DataFrame cannot be inspected end to end.
- `main()` calls `draft_info()`, not `train_model()`, and `draft_info()` currently replaces the collected draft list with one hard-coded draft.
- `pos_gap` constructs keys using uppercase positions such as `next_best_WR`, while remaining-player columns use lowercase suffixes such as `next_best_wr`.
- `merged.csv` stores numeric player IDs as floats while Sleeper pick IDs are strings. Comparing them directly means drafted players may never be removed from the remaining pool.
- Original string `player_position` remains in each row alongside numeric indicator columns. It must remain metadata or be excluded from `X`.
- Target selection uses invalid tuple-style DataFrame indexing.
- Later assignments overwrite the intended chronological split, make train and test identical, and leave `target_score` inside `X`. This is direct target leakage.
- Missing ADP/rank values need an explicit filter, imputation, or missing-value policy.
- Remaining-player `.iloc[0]` and `.iloc[1]` lookups need defined behavior when fewer than two matched players remain.
- Positional share should represent prior selections divided by prior picks. Current division by `pick_no` is slightly different, especially in early rounds.

### Data-design issues to settle now

- Build remaining-player state from a preseason ADP player table. Current `merged.csv` is an inner join with end-of-season fantasy results, so player membership and ranks can indirectly depend on future information even though fantasy points are not used directly as features.
- Keep `draft_id`, `league_id`, `roster_id`, `player_id`, and `season` as row metadata for tracing and grouped splitting. Exclude them from model inputs rather than deleting them during row construction.
- Add a draft-team group key because every pick from one team shares the same outcome.
- The same final team target is attached to every pick made by that team. This supplies a team-level reward but creates noisy credit assignment and correlated observations.
- Current state features describe total positional demand but not its distribution. Add how many opposing teams have filled or still need each starting position.
- The current linear specification lacks candidate-state interactions, so roster context cannot properly change candidate ranking.
- Feature construction for live candidates must exactly match feature construction for historical chosen candidates.

Do not fix all issues by adding complexity at once. First produce a valid, traceable feature table with one shared historical/live feature builder. Then train simple baselines before adding more features.

## Model Choice

### Recommendation

Use three stages:

1. **ADP-only baseline:** establishes what the context model must improve upon.
2. **Ridge regression baseline:** keeps linear behavior interpretable while stabilizing correlated inputs such as ADP, overall rank, positional rank, raw counts, and normalized counts. It still requires explicit candidate-state interactions.
3. **Histogram gradient-boosted regression:** best first serious model for this tabular task once enough drafts exist.

Gradient-boosted trees fit the problem better than plain linear regression because they can learn:

- Candidate-position interactions with current roster counts
- Different ADP importance in early and late rounds
- Thresholds such as starter slots becoming full
- Nonlinear scarcity effects and positional runs
- Interactions between league size, pick number, and positional demand

Plain `LinearRegression` is still valuable as a debugging baseline, but it is unlikely to be the final model. Ridge is safer for the linear baseline because many current inputs are correlated. A random forest is a possible comparison but is not the first choice. Neural networks add complexity without a clear advantage for this structured tabular dataset.

A learning-to-rank model sounds aligned with live candidate ordering, but the historical data labels only the selected candidate. It does not provide relevance labels for all alternatives available at the same pick. Continue with regression-style candidate scoring until a defensible comparison or counterfactual label exists.

## Evaluation Plan

Primary comparison:

- Baseline: rank available candidates using ADP only.
- Context model: ADP plus candidate, roster, league, and remaining-player context.

Data splitting:

- Hold out complete future seasons when enough seasons exist.
- Keep every pick from the same draft in the same split.
- Never randomly split individual picks across train and test.
- Report results by league size and draft phase, not only one aggregate metric.

Useful offline checks:

- Team-outcome prediction error versus ADP-only baseline
- Candidate ranking stability across nearby draft states
- Recommendation agreement and disagreement with ADP
- Outcome of observed picks where model strongly disagrees with ADP
- Performance by early, middle, and late rounds
- Feature ablations: remove one feature group and measure change

Limits:

- Historical outcomes exist only for selected players, not unchosen alternatives.
- Team outcomes include injuries, lineup decisions, waivers, trades, and randomness.
- A lower prediction error does not directly prove recommendations beat skilled human drafting.
- Live-team results require many drafts and seasons before supporting strong conclusions.

## Main Risks

- Sleeper crawl may grow slowly without good seed users.
- Public API can change or rate-limit.
- Old player IDs and names may not perfectly match ADP sources.
- Keeper/dynasty leagues can pollute redraft model.
- Draft pick quality is hard to evaluate against human alternatives.
- Team points include manager behavior after draft: starts, waivers, trades, injuries.
- ADP data must match the correct season and scoring format.
- Need avoid using information unavailable at draft time.
- Historical managers usually follow ADP, limiting examples of successful deviations from ADP.
- A flexible model can learn quirks of league size, draft year, or manager behavior instead of reusable strategy.

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

Success criteria:

- Historical and live candidate features use identical calculations.
- Position is encoded categorically.
- Candidate-state interactions allow roster needs to change candidate ranking.
- Overall rank is computed within the sorted season, not from the original DataFrame index.

## Fourth Milestone

Train and evaluate candidate scorers:

1. Build an ADP-only baseline.
2. Train an interpretable Ridge baseline with explicit interactions.
3. Compare against histogram gradient-boosted regression after dataset is large enough.
4. Hold out complete drafts and future seasons.
5. Measure feature groups with ablation tests.
6. Simulate live picks by scoring every available candidate.

Success criteria:

- Context model beats ADP-only baseline on held-out team-outcome prediction.
- Recommendations change when roster or remaining-player context changes.
- Early-round recommendations remain more ADP-driven than later-round recommendations.
- Results remain reasonable across 10-12 team leagues.

## Open Questions

- Is weeks 1-12 the best balance between outcome stability and draft attribution?
- Which explicit interactions are enough for the linear baseline?
- Does a nonlinear model materially outperform the interpretable baseline?
- How should missing historical ADP players be handled?
- How many leagues are enough for first useful experiment?
