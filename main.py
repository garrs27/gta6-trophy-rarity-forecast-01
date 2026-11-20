"""Forecaster for gta6-trophy-rarity-forecast-01 (Python 3.13, standard library only).

What it does
------------
For each case file in the input directory it forecasts, for every trophy of
Grand Theft Auto VI on PlayStation 5, five quantiles (5/25/50/75/95%) of the
trophy's earn rate on Exophase at the case's target, and writes
{"trophies": [{"id": n, "q": [...]}, ...]} to the output directory.

How it forecasts
----------------
An Exophase earn rate is a ratio, rate = earned / players_tracked, and both
sides move after a launch: the tracked population explodes as new players
sync, which *dilutes* every rate, while earned counts grow as players play
through the game. A persistence forecast (the house baseline) misses both
forces. This program forecasts each trophy in three steps:

1. PRIOR. Every trophy is classified from its name and description into a
   progression category (story chapter, story final, side-strand final,
   grind, collectible, skill, easy misc, 100% completion, platinum), and
   each category carries a week-one median and a slope taken from real
   trophy-rarity data of comparable Rockstar open-world launches -- GTA V
   and Red Dead Redemption 2, Sony-wide percentages (see MODEL.md for the
   table and sources). The prior is a full curve in log-time, anchored at
   its week-one median, so it can be read at any horizon.
2. HISTORY CORRECTION. The case's own reads are compared against the
   prior curve: the mean residual over the last 24 hours of reads (recency
   weighted) shifts the forecast's level, and the recent slope's departure
   from the prior slope adds a damped adjustment over the extrapolation
   distance. Both corrections are shrunk, so a steep early slope cannot
   run away -- the prior supplies the shape, the history supplies the
   level. When the history is flat (the practice cases, where every read
   is the identical launch-night page), the correction is small and the
   spread is widened a lot, because the next Exophase refresh can move
   every rate at once -- exactly what the practice answers do.
3. BLEND + SPREAD. The median is the prior curve at the target plus the
   shrunk corrections, capped just above the last read rate on horizons
   under a day (in a few hours a rate cannot climb far -- earning takes
   playtime -- while a refresh can only dilute it). The spread grows with
   the log-time distance being extrapolated and with the trend fit's
   residual, so the 90% band stays honest on a 4.5-day horizon.

The program is a pure function of its input file: no clock, no randomness,
no network, so the grader's two runs agree byte for byte. It runs in well
under a second per case.
"""

import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# The grader runs python3 -P -s, which keeps this file's directory off
# sys.path; nothing else is imported, but put it back first on principle.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# --- Priors: (week-one median %, log-time slope) per progression category.
# Week-one medians are set from mature Sony-wide rates of GTA V / RDR2
# (PSN Trophy Leaders, Sony percent earned) scaled by how far players get
# in seven days; see MODEL.md for the full table and sources. Slopes are
# the logit gain per log-hour over the launch week implied by those same
# games' story funnels (early chapters steep, grind nearly flat).
PRIORS = {
    # Opening mission: the trophy every launch-night player holds (its
    # earliest read is ~100%). RDR2's first mission, "Just a Scratch",
    # is 76.3% Sony-wide mature; by day seven the tracked population has
    # broadened past the day-one hardcore, so ~88%.
    "opening": (88.0, 0.30),
    # Platinum: GTA V platinum 0.1% mature, RDR2 0.1% mature; in week one
    # essentially nobody has 100% completion.
    "platinum": (0.02, 0.10),
    # 100% completion: RDR2 0.5% mature; a week is not enough.
    "completion100": (0.05, 0.10),
    # Story chapters, RDR2 Sony-wide mature: Ch1 64.9, Ch2 42.4, Ch3 35.9,
    # Ch4 32.0. Week one keeps most of Ch1, then the funnel bites.
    "story_ch1": (45.0, 0.90),
    "story_ch2": (28.0, 0.75),
    "story_ch3": (20.0, 0.65),
    "story_ch4": (15.0, 0.60),
    # Final mission: RDR2 "Redemption" 27.7% mature; week one ~8%.
    "story_final": (8.0, 0.50),
    # Named mid-story missions (heists, set pieces): between Ch2 and Ch3.
    "story_mission": (18.0, 0.65),
    # Final mission of a side-character strand: RDR2 optional honor
    # missions 7.8% mature; side strands are reached later than the main
    # story, so week one is lower.
    "side_final": (4.0, 0.40),
    # Whole side-strand completion (8 stranger strands): RDR2 "Western
    # Stranger" (10 strands) 9.9% mature.
    "side_strand": (3.0, 0.35),
    # Big grinds: RDR2 70 gold medals 0.2% mature, 100% 0.5% mature.
    "grind": (0.30, 0.25),
    # Collections / exploration: RDR2 one collectible strand 4.2% mature.
    "collect": (2.5, 0.35),
    # Skill feats (one-shot, stealth, escapes): low single digits.
    "skill": (2.0, 0.35),
    # Easy one-offs: RDR2 "Take From the Rich" 34.7%, "Give to the Poor"
    # 37.0%, "Trusty Steed" 50.2% mature; week one a good share.
    "misc_easy": (12.0, 0.50),
    # Secret one-off moments (vague descriptions): middle of the pack.
    "secret_misc": (6.0, 0.40),
}

# Spread (logit units). The base spread is the honest uncertainty of a
# launch-week forecast; it grows with extrapolation distance and with the
# trend fit's residual, and jumps when the history never moved (a refresh
# the case has not seen yet can shift every rate at once). Calibrated on
# the synthetic finals: mean loss 0.160 at 0.50, 0.175 at 0.65, 0.202 at
# 0.80 -- the simulator-optimal value is the narrowest, but the real
# final's median error will be larger than the simulator's (unknown game
# pace, unknown tracked-population path), so 0.65 is chosen as a
# robustness compromise, not the simulator optimum.
SIGMA_BASE = 0.65
SIGMA_PER_LOG_HOUR = 0.20
SIGMA_FLAT_HISTORY = 1.10
SIGMA_FLOOR = 0.60
SIGMA_CAP = 2.00
TAU = 12.0
K_POOL = 2.0
SHRINK = 0.90
K_DRIFT = 0.0
SIGMA_SCALE = 0.95
# Practice LOO estimates agree in sign by category; each stored average is
# clipped to the required +/-0.15 logit range.
BIAS_BY_CATEGORY = {
    "opening": 0.15, "completion100": 0.0, "platinum": 0.15,
    "collect": -0.15, "grind": -0.15, "misc_easy": -0.15,
    "secret_misc": -0.15, "side_final": -0.15, "side_strand": -0.15,
    "skill": -0.15, "story_ch1": -0.15, "story_ch2": -0.15,
    "story_ch3": -0.15, "story_ch4": -0.15, "story_final": -0.15,
    "story_mission": -0.15,
}

# One read per 30 minutes is enough for the trend fit; denser reads are
# autocorrelated copies of the same Exophase refresh.
THIN_MINUTES = 30.0

# Hours after release at which the prior curve is anchored (one week).
PRIOR_ANCHOR_HOURS = 168.0


def clamp(x):
    return min(99.99, max(0.01, x))


def logit(pct):
    return math.log(clamp(pct) / (100.0 - clamp(pct)))


def sigmoid(x):
    if x >= 0:
        return 100.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return 100.0 * ex / (1.0 + ex)


def parse_timestamp(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def round4(x):
    """Round to 4 decimals, half up; whole numbers come back as int."""
    scaled = x * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000
    return int(value) if float(value).is_integer() else value


def classify_trophy(trophy):
    """Progression category from the trophy's name, description and tier.

    The description is matched case-sensitively for one rule: a story
    mission is "Complete <Title>" -- "Complete Breakfast Run",
    "Complete The Cartel Heist" -- while grind and misc trophies say
    "Complete 250 Stunts", "Complete 50 Challenges" or "Complete an
    arcade game" (a digit or a lowercase word after "Complete").
    """
    text = (trophy.get("name", "") + " " + trophy.get("description", "")).lower()
    desc = trophy.get("description", "")
    tier = trophy.get("tier", "")
    if tier == "platinum":
        return "platinum"
    if "100% completion" in text:
        return "completion100"
    m = re.search(r"complete chapter (\d)", text)
    if m:
        ch = int(m.group(1))
        return {1: "story_ch1", 2: "story_ch2", 3: "story_ch3", 4: "story_ch4"}.get(ch, "story_ch4")
    if "complete the final mission" in text and "for " not in text:
        return "story_final"
    if "complete the final mission for " in text:
        return "side_final"
    if "complete " in text and "mission strands for strangers" in text:
        return "side_strand"
    if re.match(r"Complete [A-Z]", desc):
        return "story_mission"
    if re.search(r"\b(250 stunts|50 challenges|100 locations|3 collectible card sets|gold medal in all)\b", text):
        return "grind"
    if re.search(r"\b(discover \d+ vehicles|explore all|purchase all|register \d+ vehicles|meditate at every|hunt a unique)\b", text):
        return "collect"
    if re.search(r"\b(take down \d+ enemies|without being detected|rob \d+ bank vaults|rob an armored truck|win \d+ different races|win a .* drone race at every|beat cal in a fishing)\b", text):
        return "skill"
    if re.search(r"\b(try each type of activity|complete an arcade game|earn \$[\d,]+ laundering|spend \$[\d,]+|lose a \d+ star wanted|rob \d+ shops)\b", text):
        return "misc_easy"
    if trophy.get("secret"):
        return "secret_misc"
    return "misc_easy"


def classify(trophy):
    """Compatibility name used by the repository's backtest utility."""
    return classify_trophy(trophy)


def thin_history_reads(reads, release):
    """One read per THIN_MINUTES, oldest first; returns (hours, rates) lists."""
    out = []
    last_t = None
    for r in reads:
        t = parse_timestamp(r["at"])
        if last_t is not None and (t - last_t).total_seconds() < THIN_MINUTES * 60:
            continue
        out.append(r)
        last_t = t
    return out


def winsor(x):
    return max(-2.0, min(2.0, x))


def ols(xs, ys, weights=None):
    """Least squares y = a + b*x; returns (a, b, residual_sd, n)."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0, 0.0, 0
    if n == 1:
        return ys[0], 0.0, 0.0, 1
    weights = weights or [1.0] * n
    sw = sum(weights)
    mx = sum(w * x for w, x in zip(weights, xs)) / sw
    my = sum(w * y for w, y in zip(weights, ys)) / sw
    sxx = sum(w * (x - mx) ** 2 for w, x in zip(weights, xs))
    if sxx <= 1e-12:
        return my, 0.0, 0.0, n
    sxy = sum(w * (x - mx) * (y - my) for w, x, y in zip(weights, xs, ys))
    b = sxy / sxx
    a = my - b * mx
    resid = math.sqrt(sum(w * winsor(y - (a + b * x)) ** 2 for w, x, y in zip(weights, xs, ys)) / sw)
    return a, b, resid, n


def forecast_trophy_from_history(trophy, series, release, target_hours, horizon_hours, cat=None, pooled_delta=None):
    """series: list of (hours_since_release, rate_pct[, players_tracked])."""
    if cat is None:
        cat = classify_trophy(trophy)
    prior_med, prior_beta = PRIORS[cat]
    last_rate = series[-1][1] if series else None

    # Trophy already at 100% (the opening mission): it can only dilute as
    # fresh tracked players arrive who have not played it yet. Anchor the
    # dilution on the prior curve's shape: ~93% by the end of week one.
    if last_rate is not None and last_rate >= 99.99:
        frac = min(1.0, target_hours / PRIOR_ANCHOR_HOURS)
        med = 100.0 - 7.0 * frac
        sigma = 0.50 + 0.30 * frac
        lg = logit(med)
        qs = [round4(sigmoid(lg + z * sigma)) for z in Z]
        return [max(qs[0], 0.01)] + qs[1:], cat

    # Prior curve in log-time, anchored at the week-one median: it supplies
    # the forecast's shape. The case's history supplies a level correction
    # (how GTA VI actually runs against the prior) and a recent-slope
    # correction, both shrunk so neither can run away on extrapolation.
    x_target = math.log1p(target_hours)
    x_anchor = math.log1p(PRIOR_ANCHOR_HOURS)

    def prior_logit_at(hours):
        return logit(prior_med) + prior_beta * (math.log1p(hours) - x_anchor)

    # Level correction: mean residual of the reads against the prior curve,
    # recency-weighted (later reads count double), over the last 24 hours
    # of reads where the case has them, else all reads.
    last_t = series[-1][0]
    recent = [item for item in series if item[0] >= last_t - 24.0] or series
    residuals = [winsor(logit(item[1]) - prior_logit_at(item[0])) for item in recent]
    weights = [math.exp(-(last_t - item[0]) / TAU) for item in recent]
    sw = sum(weights)
    raw_delta = sum(w * y for w, y in zip(weights, residuals)) / sw if sw else 0.0
    delta = pooled_delta if pooled_delta is not None else raw_delta

    # Recent-slope correction: OLS slope over the last 24h of reads, minus
    # the prior slope, applied over the extrapolation distance and damped.
    xs = [math.log1p(item[0]) for item in recent]
    ys = residuals
    _a, beta_recent, resid, n_recent = ols(xs, ys, weights)
    distinct = len({round(item[1], 2) for item in series})
    dlog = max(0.0, x_target - math.log1p(last_t))
    slope_adj = 0.0
    if n_recent >= 5 and distinct > 1:
        slope_adj = max(-0.6, min(0.6, beta_recent * dlog * 0.35))

    # The level correction persists only partly: the further the target,
    # the more the forecast reverts to the prior curve.
    persistence = 0.75 if distinct > 1 else 0.50
    med_logit = prior_logit_at(target_hours) + SHRINK * (persistence * delta + slope_adj) + BIAS_BY_CATEGORY.get(cat, 0.0)
    populations = [(item[0], item[2]) for item in recent if len(item) > 2 and item[2] > 0]
    if K_DRIFT and len(populations) >= 2:
        growth = (math.log(populations[-1][1]) - math.log(populations[0][1])) / max(1e-9, math.log1p(populations[-1][0]) - math.log1p(populations[0][0]))
        med_logit += max(-0.25, min(0.25, -K_DRIFT * growth * dlog * (1.0 - last_rate / 100.0)))

    # Short-horizon ceiling. In the first hours after launch a trophy's
    # rate cannot climb far in a few hours -- earning takes playtime --
    # while a refresh of Exophase's tracked population can only dilute it
    # (launch night: the page sat unchanged for hours, then a refresh took
    # every rate down). The log-time prior curve, anchored at week one,
    # overstates short-horizon growth, so for horizons under a day the
    # median is capped just above the last read rate. It never binds on
    # the final's 4.5-day horizon.
    if horizon_hours < 24.0 and last_rate is not None and 0.0 < last_rate < 50.0:
        ceiling = last_rate * (1.0 + horizon_hours / 12.0)
        med_pct = sigmoid(med_logit)
        if med_pct > ceiling:
            med_logit = logit(ceiling)

    # Spread: base + extrapolation distance + flat-history refresh risk
    # + trend-fit residual.
    sigma = SIGMA_SCALE * math.sqrt(
        SIGMA_BASE ** 2
        + (SIGMA_PER_LOG_HOUR * dlog) ** 2
        + (SIGMA_FLAT_HISTORY if distinct <= 1 else 0.0) ** 2
        + min(resid, 0.5) ** 2
    )
    sigma = min(SIGMA_CAP, max(SIGMA_FLOOR, sigma))

    qs = [round4(sigmoid(med_logit + z * sigma)) for z in Z]
    for j in range(1, len(qs)):
        if qs[j] < qs[j - 1]:
            qs[j] = qs[j - 1]
    return qs, cat


def forecast_case(case, name):
    if case.get("levels", LEVELS) != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    history = case.get("history") or []
    if not history:
        raise ValueError(f"{name} has no history")
    trophies = case["trophies"]
    release = parse_timestamp(case["game"]["release_date"] + "T00:00:00Z") \
        if case.get("game", {}).get("release_date") else parse_timestamp(history[0]["at"])
    target = parse_timestamp(case["target"])
    target_hours = (target - release).total_seconds() / 3600.0
    horizon_hours = case.get("horizon_minutes", 0) / 60.0

    thinned = thin_history_reads(history, release)
    # Per-trophy series: (hours since release, rate), skipping nulls.
    rows = []
    pending = []
    for i, trophy in enumerate(trophies):
        series = []
        for r in thinned:
            rate = r["rates"][i] if i < len(r["rates"]) else None
            if rate is None:
                continue
            h = (parse_timestamp(r["at"]) - release).total_seconds() / 3600.0
            series.append((h, float(rate), int(r.get("players_tracked", 0) or 0)))
        if not series:
            # No read ever listed this trophy: fall back to the prior alone.
            cat = classify_trophy(trophy)
            prior_med, _ = PRIORS[cat]
            lg = logit(prior_med)
            qs = [round4(sigmoid(lg + z * SIGMA_BASE)) for z in Z]
            rows.append({"id": trophy["id"], "q": qs})
            continue
        # A trophy every launch-night player already holds is the opening
        # mission, whatever its description says: its earliest read is
        # ~100%, and it stays near the top of the list all week.
        cat = "opening" if series[0][1] >= 95.0 else classify_trophy(trophy)
        pending.append((trophy, series, cat))
    # Pool raw log-ratio level corrections within progression categories.
    deltas = []
    for trophy, series, cat in pending:
        prior_med, prior_beta = PRIORS[cat]
        anchor = math.log1p(PRIOR_ANCHOR_HOURS)
        last_t = series[-1][0]
        recent = [item for item in series if item[0] >= last_t - 24.0] or series
        weights = [math.exp(-(last_t - item[0]) / TAU) for item in recent]
        residuals = [winsor(logit(item[1]) - (logit(prior_med) + prior_beta * (math.log1p(item[0]) - anchor))) for item in recent]
        delta_i = sum(w * r for w, r in zip(weights, residuals)) / sum(weights)
        deltas.append((trophy, series, cat, delta_i, len(recent)))
    category_means = {}
    for _, _, cat, delta_i, _ in deltas:
        category_means.setdefault(cat, []).append(delta_i)
    category_means = {cat: sum(values) / len(values) for cat, values in category_means.items()}
    for trophy, series, cat, delta_i, n_i in deltas:
        blended = (n_i * delta_i + K_POOL * category_means[cat]) / (n_i + K_POOL)
        qs, _cat = forecast_trophy_from_history(trophy, series, release, target_hours, horizon_hours, cat, blended)
        rows.append({"id": trophy["id"], "q": qs})
    return {"trophies": rows}


def write_forecasts():
    """Read cases in filename order and write compact forecast JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


def main():
    write_forecasts()


if __name__ == "__main__":
    main()
