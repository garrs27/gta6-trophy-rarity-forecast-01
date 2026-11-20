# GTA VI trophy rarity, week one — methodology

## The problem

Grand Theft Auto VI launched 19 November 2026 on PlayStation 5. No console
maker publishes how many people play it or how far they get. The public
proxy is Exophase's trophy page: for each of the game's 55 PlayStation 5
trophies it prints the earn rate — the percent of the players Exophase
tracks for the game who have earned it — and the players-tracked count.
The house reads that page every 10–30 minutes and keeps every read.

The entry is a program, `main.py`, that reads one case (every read before
a checkpoint) and forecasts, for each trophy, five quantiles (5/25/50/75/95%)
of its earn rate at the target: 2026-11-26 00:00 UTC, a week after launch.
It is scored by mean pinball loss on the logit scale, and a prize needs a
loss strictly below the best house entry (persistence baseline, curve
baseline, house AI model forecast).

## The key fact: a rate is a ratio

```
rate = earned / players_tracked
```

Both sides move after a launch, in opposite directions for the rate:

- **Dilution.** The tracked population explodes as new players sync
  (launch night: 638 players tracked, then a refresh to 3,868 — and
  every rate but the 100% one *fell*). A trophy's rate can drop while
  more people than ever are earning it.
- **Progression.** Earned counts grow as players play through the game,
  on a schedule set by the trophy's position in the progression funnel:
  the opening mission within hours, chapter trophies over days, grinds
  and 100% completion over weeks or never.

A persistence forecast ("the rate stays where it is") misses both forces.
This program forecasts each trophy as a **prior curve corrected by the
case's own history**.

## 1. Prior curves from comparable launches

Every trophy is classified from its name and description into a
progression category, and each category carries a week-one median and a
log-time slope. The medians are set from real trophy-rarity data of
comparable Rockstar open-world launches — mature Sony-wide percentages —
scaled by how far players get in seven days.

| Category | Week-one median | Slope | Anchored on (mature, Sony-wide) |
|---|---|---|---|
| opening (first mission) | 88% | 0.30 | RDR2 "Just a Scratch" 76.3%; GTA VI's own launch-night read is 100% |
| story_ch1 | 45% | 0.90 | RDR2 Ch.1 "Back in the Mud" 64.9% |
| story_ch2 | 28% | 0.75 | RDR2 Ch.2 42.4%; GTA V mid-story ~15% (tracker sample) |
| story_ch3 | 20% | 0.65 | RDR2 Ch.3 35.9% |
| story_ch4 | 15% | 0.60 | RDR2 Ch.4 32.0% |
| story_final | 8% | 0.50 | RDR2 "Redemption" (final mission) 27.7% |
| story_mission (named missions) | 18% | 0.65 | Between Ch.2 and Ch.3 of the RDR2 funnel |
| side_final (character strand final) | 4% | 0.40 | RDR2 optional honor missions 7.8% |
| side_strand (8 stranger strands) | 3% | 0.35 | RDR2 "Western Stranger" (10 strands) 9.9% |
| grind (250 stunts, 50 challenges, gold medals…) | 0.30% | 0.25 | RDR2 70 gold medals 0.2%; 100% completion 0.5% |
| collect (explore, discover, purchase all…) | 2.5% | 0.35 | RDR2 one collectible strand 4.2% |
| skill (one-shot feats, stealth, escapes) | 2.0% | 0.35 | Low single digits across both games |
| misc_easy (try each activity, spend $100k…) | 12% | 0.50 | RDR2 "Take From the Rich" 34.7%, "Give to the Poor" 37.0%, "Trusty Steed" 50.2% |
| secret_misc (vague one-off moments) | 6% | 0.40 | Middle of the pack by construction |
| completion100 | 0.05% | 0.10 | RDR2 "Best in the West" 0.5% mature; a week is not enough |
| platinum | 0.02% | 0.10 | GTA V platinum 0.1% mature; RDR2 0.1% mature |

The prior is a full curve in log-time, anchored at its week-one median:

```
prior_logit(t) = logit(m_week1) + beta * (ln(1 + t_hours) - ln(169))
```

so it can be read at any horizon. The full table with sources is in
`priors.json`.

### Sources

- RDR2 Sony-wide percentages: PSN Trophy Leaders,
  https://psntrophyleaders.com/game/view/red-dead-redemption-2-ps4
  (522,425 players tracked; "Sony Percent Earned" column — the same
  population concept Exophase tracks).
- GTA V percentages: PocketPSN,
  https://pocketpsn.com/game/3375-grand-theft-auto-v/KairoNoKizzy
  (tracker sample — lower than PSN-wide, because its denominator
  includes dormant owners; used only for shape, not levels).
- GTA VI launch-night reads: the competition kit's practice cases
  (`p00.in`, `p01.in`) — 638 players tracked, every rate 0.63–2.04%
  except the opening mission at 100%.
- The refresh mechanism (page unchanged for hours, then a jump to 3,868
  tracked players with every rate lower): the competition rules.

### Classification rules

- `platinum` by tier; `100% completion` by description.
- `Complete Chapter N` → story_ch1–ch4 by N.
- `Complete the final mission` → story_final; `…for <name>` → side_final.
- `Complete 8 mission strands for strangers` → side_strand.
- `Complete <Title>` (capitalised title, e.g. "Complete Breakfast Run",
  "Complete The Cartel Heist") → story_mission. Grind/misc trophies say
  "Complete 250 Stunts", "Complete 50 Challenges" or "Complete an arcade
  game" — a digit or a lowercase word after "Complete" — so they do not
  match.
- Keyword sets for grind / collect / skill / misc_easy (see `classify()`
  in `main.py`); secret trophies with vague descriptions → secret_misc.
- **Opening mission:** a trophy whose earliest read in the case is ≥95%
  is the opening mission whatever its description says (in the real data
  that is "Just Like Paradise", 100% at launch night).

## 2. History correction (shrunk)

The prior supplies the shape; the case's history supplies the level.
For each trophy:

- **Level correction.** Mean residual of the reads against the prior
  curve over the last 24 hours of reads (recency-weighted), added to the
  forecast with persistence 0.75 (0.50 when the history never moved).
  If GTA VI's players are faster than RDR2's, the forecast moves up;
  if slower, down — but only part-way, because a 2.5-day history cannot
  certify a week.
- **Slope correction.** OLS slope of logit(rate) on ln(1 + hours) over
  the last 24 hours of reads, minus the prior slope, applied over the
  log-time extrapolation distance and damped (×0.35, capped at ±0.6
  logit). This takes the house curve baseline's idea — the recent trend
  — without letting a steep early slope run away: the true curve is
  logistic in log-time and saturates, so a line fitted on the steep part
  overshoots badly at day seven.
- **Short-horizon ceiling.** For horizons under a day the median is
  capped just above the last read rate. In a few hours a rate cannot
  climb far (earning takes playtime) while a refresh can only dilute it.
  This never binds on the final's 4.5-day horizon.

A trophy already at 100% in the last read is handled separately: it can
only dilute, to ~93% by the end of week one.

## 3. Spread

Quantiles are the median in logit space plus z_tau × sigma, z =
(-1.645, -0.674, 0, 0.674, 1.645):

```
sigma = sqrt(0.65² + (0.20 × dlog)² + flat² + resid²)
```

- 0.65 base: the honest uncertainty of a launch-week forecast.
- dlog: log-time distance from the last read to the target.
- flat = 1.10 when the trophy's rate never moved in the case's history
  (the practice cases): a refresh the case has not seen can shift every
  rate at once, so the band must be wide. The house baseline's practice
  band covered ~0% of the answers; this one covers ~98% on the
  reconstructed practice answers.
- resid: the trend fit's residual standard deviation (capped at 0.5).
- Floor 0.60, cap 2.00.

Sigma was calibrated on the synthetic finals: mean loss 0.160 at base
0.50, 0.175 at 0.65, 0.202 at 0.80. The simulator-optimal value is the
narrowest, but the real final's median error will be larger than the
simulator's (unknown game pace, unknown tracked-population path), so
0.65 is chosen as a robustness compromise rather than the simulator
optimum.

## Validation

`tools/backtest.py` scores the program with the contest's own pinball
loss. Two checks:

**Practice** (answers reconstructed from the rules' facts — players
tracked 638 → 3,868 at the 04:30 refresh, every rate but the 100% one
lower; counts grown modestly over 90 minutes — approximate):

| case | this program | house persistence | house curve |
|---|---|---|---|
| p00 | 0.978 | 1.634 | 1.634 |
| p01 | 0.974 | 1.622 | 1.622 |

(The rules state the house baseline scores ~1.51 on the real practice;
the reconstruction puts it at ~1.63. Either way this program is well
below it, with 90% coverage 0.98 vs the house's 0.00.)

**Synthetic finals** — a full launch week generated by an independent
model (different week-one targets and population growth from the
forecaster's priors), case cut at the deadline, scored on the true
day-7 rates:

| scenario | this program | house persistence | house curve |
|---|---|---|---|
| base | 0.177 | 0.386 | 0.331 |
| slow progression | 0.188 | 0.371 | 0.342 |
| fast population growth | 0.180 | 0.396 | 0.327 |
| late growth (no early saturation) | 0.205 | 0.600 | 0.313 |

The program beats both house baselines in every scenario (typical miss
~1.1–1.7 points vs 1.5–3.8 for persistence), including the world where
persistence is weakest. 90% coverage on the synthetic finals is 1.00 —
the bands are wide, which is the honest choice when the true dynamics
are unknown; the loss still wins because the medians are much closer.

Run it yourself: `python3 tools/backtest.py` (practice + all scenarios).

## Demo forecast

`tools/make_demo.py` builds a simulated final-like case from the real
trophy list and real launch-night rates (base scenario), runs `main.py`
on it exactly as the grader would, and renders `demo/forecast.csv`,
`demo/forecast.md` and `demo/forecast.html`. Headline numbers from that
demo: median forecast 5.05% across all 55 trophies; opening mission
93.5% (band 82.5–97.8%); Chapter 1 52.0% (26.1–76.9%); final mission
5.8% (2.0–15.9%); 100% completion 0.016%; platinum 0.015%. Demo
pinball loss 0.177 vs house persistence 0.386 and house curve 0.331.
The demo case's history is simulated and labelled as such everywhere;
the submitted program only ever reads the case it is given.

## Limitations (honest)

- The priors are cross-game. RDR2's story is ~50 hours; GTA VI's
  length and pacing are not public. If GTA VI plays much faster or
  slower, the medians shift — the history correction only partly
  compensates, because 2.5 days of history cannot certify a week.
- The simulator is the author's own construction. Beating the house
  baselines on it is evidence, not proof, about the real final.
- The tracked-population path N(t) is unknowable in advance; a weekend
  surge or a slow sync week moves every rate together, which no
  per-trophy model can foresee. The spread is the honest answer to that.
- The practice answers are reconstructed, not the house's real reads;
  the practice loss is indicative only.

## Winner-template retrofit

The history fit now works on the explicit log-ratio residual
`r_t = logit(rate_t) - prior_logit(t)`. Residuals are clipped to +/-2.0
logit, then both the level mean and weighted OLS slope use an exponential
recency kernel `exp(-(last_t - t) / TAU)`. The slope is fitted to the
residual series, so it measures departure from the prior curve directly.
Fits use the last 24 hours when available. Category pooling first averages
each trophy's raw level correction within its progression category, then
blends the trophy estimate with that category mean using `K_POOL` and the
number of reads. This makes same-category trophies the comparables.

The full correction `(persistence * blended_level + slope_adjustment)` is
multiplied by `SHRINK`. Quantiles retain the existing opening-mission branch
and short-horizon ceiling. Sigma is multiplied by `SIGMA_SCALE`; sigma-fit
residuals are winsorized at +/-2.0 before entering the existing capped
spread formula.

The population-dilution term uses recent thinned `players_tracked` counts to
estimate log population growth per log-hour. It is disabled (`K_DRIFT=0`):
testing positive values helped slow progression but materially hurt
fast-population and late scenarios. For example, at K_DRIFT=0.5 the losses
were 0.1994 fast-pop and 0.2551 late, versus 0.1808 and 0.2200 with drift
disabled after the other final calibration changes. The opening mission's
special branch remains unchanged.

Final constants:

| Constant | Value |
|---|---:|
| TAU | 12 hours |
| K_POOL | 2.0 |
| SHRINK | 0.90 |
| K_DRIFT | 0.0 (dropped after validation) |
| SIGMA_SCALE | 0.95 |
| BIAS_BY_CATEGORY | +/-0.15 logit by stable LOO sign; completion100=0.0 |

`tools/backtest.py` prints both the two-direction practice LOO analysis and
the sigma grid. Practice LOO category signs agree in both directions except
completion100, which is left at zero; all embedded estimates are clipped to
the required +/-0.15 range. The grid selected 0.95, the lowest-loss scale
that maintains practice cov90 >= 0.90 and synthetic mean cov90 >= 0.92.

### Validation after retrofit

Losses below use the current final model. “Before” is the recorded baseline
at the start of this retrofit; practice answers are reconstructed and all
synthetic finals are generated by the local independent simulator.

| Case | Before loss | After loss | After cov90 |
|---|---:|---:|---:|
| p00 | 0.9781 | 0.9497 | 0.98 |
| p01 | 0.9742 | 0.9477 | 0.98 |
| base | 0.1770 | 0.1641 | 1.00 |
| slow | 0.1877 | 0.1686 | 1.00 |
| fast-pop | 0.1796 | 0.1808 | 1.00 |
| late | 0.2047 | 0.2200 | 1.00 |
| synthetic mean | 0.1873 | 0.1834 | 1.00 mean |

The requirements pass: both practice losses are below their baseline plus
0.005, synthetic mean is below 0.1873, and practice coverage is in range.
The fast-pop and late medians are somewhat worse than their pre-retrofit
baseline individually; their combined constraints still pass, and the
drift term that worsened them was disabled. The regenerated demo loss is
0.1641.
