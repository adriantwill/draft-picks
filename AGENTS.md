# Fantasy Football Draft Data Project Notes

Last updated: 2026-07-20

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
- Three final team-level outcomes used as labels

At inference time:

1. Capture current draft and roster state.
2. Create one candidate row for every available player.
3. Simulate selecting each candidate.
4. Recalculate candidate-specific roster fit and remaining-player scarcity.
5. Predict overall team outcome, drafted-player contribution, and drafted-starter retention for every candidate.
6. Rank candidates using an explicit recommendation rule and return the associated `player_id`.

Historical data contains only the action actually taken, not outcomes for every alternative action. The model therefore learns associations between observed decisions and later team success. Held-out historical testing can measure prediction error for observed picks, but it cannot directly prove that an unchosen recommendation would have produced a better result. Recommendation quality ultimately needs a transparent draft simulator or prospective drafts.

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
- Team outcome labels

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

## Outcome Targets

Current code in `src/organize_draft_data.py` computes three separate team-level outcomes over weeks 1-17:

- `total_weekly_z`: average weekly within-league z-score of team points after removing kicker and defense points. This measures total team success and therefore includes help from waivers, trades, and lineup decisions.
- `total_start_ratio`: average fraction of the seven offensive starter slots occupied by players originally drafted by that team. This measures drafted-player retention, not player quality.
- `team_player_impact`: fraction of the team's offensive points contributed by originally drafted players while starting for that team. `main.py` currently stores this as `target_score`; rename it to something clearer such as `drafted_points_share`.

Keeping these outcomes separate avoids the signed-score problem caused by multiplying weekly z-score by a retention fraction. Together they distinguish a strong original draft from a team rescued by waiver-wire players. They are targets, not input features, because their actual values are unavailable on draft day.

The first multi-output model should predict all three values. Report separate metrics for each target. Do not average the raw predictions because weekly z-score and the two 0-1 ratios use different scales and meanings. Initial recommendation behavior should rank primarily by predicted weekly z-score, use predicted drafted-points share as the first tie-breaker, and predicted start ratio as the second tie-breaker. Revisit weighting only after inspecting held-out prediction distributions.

Before large-scale outcome collection, validate two edge cases in `draft_impact()`:

- Divide season aggregates by the number of successfully collected weeks rather than always by 17 when API calls fail.
- Define behavior when within-week team-point standard deviation is zero.

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
- `team_17_week_outcomes`
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

## Current Progress Snapshot

### Completed

- Project files now use paths rooted at the repository and separate crawl, scrape, and clean data directories.
- `data/clean/drafts_metadata.json` exists and has been tested end to end with five drafts from 2022-2024.
- The proof-of-concept metadata contains 627 offensive picks; 624 produce feature rows and three lack matched ADP, a 0.48% skip rate.
- `main()` calls `train_model()`, and `train_table()` returns one row per usable observed pick.
- Historical ADP is loaded from the preseason-only `adp_all.csv`, not the end-of-season results join.
- ADP `player_id` is loaded as a string, matching Sleeper IDs. Drafted players are now correctly removed from the remaining pool.
- Picks without ADP are skipped as training rows after their real roster and league state is updated, preserving later-pick context.
- Candidate position indicators, own-team position counts, league-wide counts, per-team rates, prior-pick positional shares, next/second-best positional ADP, and positional gaps are present.
- Positional shares now divide by `pick_no - 1`, with zero defined for the first pick.
- `src/organize_draft_data.py` computes three separate outcomes: weekly team z-score, drafted-starter ratio, and drafted-player point share.
- `main.py` has moved from `LinearRegression` to `HistGradientBoostingRegressor` and identifies all three training targets.

### Immediate blockers

- `main.py` creates one estimator and calls `.fit()` on that same object three times. `impact_model`, `z_model`, and `start_ratio_model` therefore all reference the same final estimator trained only on `start_ratio`. Create three independent named estimators or use `MultiOutputRegressor(HistGradientBoostingRegressor(...))`.
- Current training filter uses every season before 2025 and creates no test set. Train on seasons before 2024 and hold out complete 2024 drafts for the first pipeline test.
- `draft_id` and `league_id` are not copied into feature-table metadata. Add them plus a `draft_team_id` so related rows can be traced and grouped.
- No MAE or R-squared metrics are computed. Evaluate each target separately and compare against ADP-only models on identical held-out rows.
- Trained estimators are neither returned nor saved, and live candidate scoring is not implemented.
- `if not pick["adp"]` should become an explicit missing-value check so zero and `NaN` are not conflated.
- Remaining-player `.iloc[0]` and `.iloc[1]` accesses still need defined behavior when fewer than two players remain at a position.
- The five-draft sample validates code flow only. Increase to roughly 100 season-balanced drafts after the train/test pipeline works, then scale further.

### Next feature experiments

- Add richer fixed-size summaries of the available pool instead of copying an entire variable-length ADP table into every row.
- Useful first summaries per position: top 3-5 remaining ADPs, gaps between them, counts expected to go within the next 12 and 24 picks, candidate rank among remaining players, and position mix among the top available players overall.
- Add how many opposing teams have filled or still need each starting position.
- Measure each feature group by held-out ablation. Do not assume that more columns improve generalization.
- Live scoring must eventually construct the same feature semantics for every available candidate, predict three outcome values, attach them to `player_id`, and rank the candidates.

The same final team outcomes are attached to every pick made by one team. This creates correlated observations and noisy credit assignment. One million pick rows do not represent one million independent outcome labels; split by complete future seasons or drafts, never by random individual picks.

## Model Choice

### Recommendation

Use two first-stage comparisons for each of the three targets:

1. **ADP-only histogram-boosting baseline:** predicts the target using only candidate ADP.
2. **Full-context histogram-boosting model:** uses ADP plus candidate, roster, league, and remaining-player context.

`HistGradientBoostingRegressor` is the best first serious model for the current numeric tabular features. Start with three explicitly named estimators because their separate metrics and meanings are easier to inspect. `MultiOutputRegressor` is an equivalent convenience wrapper here: it trains one independent histogram model per target and does not share information between targets.

Gradient-boosted trees fit the problem better than plain linear regression because they can learn:

- Candidate-position interactions with current roster counts
- Different ADP importance in early and late rounds
- Thresholds such as starter slots becoming full
- Nonlinear scarcity effects and positional runs
- Interactions between league size, pick number, and positional demand

Linear and Ridge models are not part of the current planned implementation. A random forest supports native multi-output regression but is not the first choice for roughly one million tabular rows because of runtime and memory cost. Neural multi-task models could share representations across targets, but they add complexity without a demonstrated held-out advantage.

A learning-to-rank model sounds aligned with live candidate ordering, but the historical data labels only the selected candidate. It does not provide relevance labels for all alternatives available at the same pick. Continue with regression-style candidate scoring until a defensible comparison or counterfactual label exists.

## Evaluation Plan

Primary comparison:

- Baseline: predict each observed target using candidate ADP only.
- Context model: predict each observed target using ADP plus candidate, roster, league, and remaining-player context.
- Report MAE and R-squared separately for `weekly_z`, drafted-points share, and drafted-starter ratio.
- Lower held-out prediction error means context explains observed outcomes better than ADP alone. It does not prove that a different historical recommendation would have caused a better result.

Data splitting:

- Hold out complete future seasons when enough seasons exist.
- Keep every pick from the same draft in the same split.
- Never randomly split individual picks across train and test.
- Report results by league size and draft phase, not only one aggregate metric.

Useful offline checks:

- Prediction error for each target versus its ADP-only baseline
- Candidate ranking stability across nearby draft states
- Recommendation agreement and disagreement with ADP
- Outcome of observed picks where model strongly disagrees with ADP
- Performance by early, middle, and late rounds
- Feature ablations: remove one feature group and measure change

Limits:

- Historical outcomes exist only for selected players, not unchosen alternatives.
- `weekly_z` includes injuries, lineup decisions, waivers, trades, and randomness; the other two targets help identify how much of that result came from original draftees.
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

## First Milestone — Proof of Concept In Progress

Build a tiny proof of concept:

- Sleeper user/league crawl is working and has found more than 10,000 qualifying draft IDs.
- Five drafts currently exercise the metadata and feature pipeline end to end.
- Next scale checkpoint is roughly 100 season-balanced drafts before processing all available drafts.
- Draft metadata and picks are currently stored in clean JSON; raw-response storage or normalized raw tables remain future work.

Success criteria:

- Can produce a table with one row per pick
- Columns include `league_id`, `draft_id`, `season`, `pick_no`, `round`, `draft_slot`, `roster_id`, `player_id`, `picked_by`
- Can count drafts, picks, leagues, and unique players
- Can identify incomplete or unusual drafts

## Second Milestone — Outcome Collection In Progress

Add team outcomes:

- Weeks 1-17 matchups are fetched for the proof-of-concept drafts.
- Team offensive points are normalized within league/week as z-scores.
- Drafted-starter retention and drafted-player contribution share are also aggregated.
- All three team outcomes are attached to every observed pick from that team.
- Before scaling, track successfully collected weeks and guard zero-variance league weeks.

## Third Milestone — Basic Features In Progress

Add modeling features:

- Join historical ADP
- Add positional ADP
- Add draft-state features before each pick
- Add team roster construction before each pick
- Add positional scarcity features
- Add richer fixed-size remaining-pool summaries after the baseline model works

Success criteria:

- Historical and live candidate features use identical calculations.
- Position is encoded categorically.
- Candidate-state interactions allow roster needs to change candidate ranking.
- Overall rank is computed within the sorted season, not from the original DataFrame index.

## Fourth Milestone — Next

Train and evaluate candidate scorers:

1. Fix the three-estimator overwrite bug.
2. Add traceable draft/team metadata to feature rows.
3. Hold out 2024 and compute per-target MAE and R-squared.
4. Build ADP-only histogram baselines for all three targets.
5. Compare full-context histogram models on identical held-out rows.
6. Increase from five to roughly 100 season-balanced drafts and rerun validation.
7. Measure feature groups with ablation tests.
8. Add live scoring that predicts three outcomes for every available candidate and returns ranked `player_id` values.

Success criteria:

- Context models beat their ADP-only baselines on held-out outcome prediction.
- Recommendations change when roster or remaining-player context changes.
- Early-round recommendations remain more ADP-driven than later-round recommendations.
- Results remain reasonable across 10-12 team leagues.

## Open Questions

- Is weeks 1-17 the best balance between outcome stability and draft attribution, or should weeks 1-12 be compared?
- Should recommendations use weekly z-score with tie-breakers, or a normalized weighted combination of all three predictions?
- Do richer remaining-pool summaries materially improve held-out results over next/second-best positional ADP alone?
- How should missing historical ADP players be handled?
- How many complete draft-team outcomes are enough for the first useful experiment?
- Should recommendation policies eventually be tested with a transparent draft simulator, prospective drafts, or both?
