"""Backtest for the GTA VI trophy forecaster (local validation only, not graded).

Two checks:
  1. PRACTICE: score main.py and the house persistence baseline on the
     practice cases against a reconstructed answer. The rules state the
     04:30Z refresh took players tracked 638 -> 3,868 with every rate but
     the 100% one lower; counts are reconstructed by growing each
     trophy's launch-night earn count modestly over the 90 minutes
     (story +15%, side +10%, misc +10%, grind/collect/skill +3%) and
     dividing by 3,868. Approximate -- reported as such.
  2. SYNTHETIC FINAL: generate a full launch week with an independent
     generative model (different category targets and population growth
     from the forecaster's priors), cut the case at the deadline
     (2026-11-21 11:30 UTC), and score main.py vs the house persistence
     baseline vs the house curve baseline on the true day-7 rates.
     Three scenarios: base, slow progression, fast population growth.

Scoring is the contest's own: mean pinball loss on the logit scale over
every trophy x level, rates clamped to 0.01..99.99.

Usage:
    python3 tools/backtest.py            # practice + all scenarios
    python3 tools/backtest.py practice   # practice only
    python3 tools/backtest.py final      # synthetic finals only
"""
import json
import math
import random
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main as model  # noqa: E402
from main import forecast_case, classify  # noqa: E402

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
RELEASE = datetime(2026, 11, 19, 0, 0, tzinfo=timezone.utc)


def clamp(x):
    return min(99.99, max(0.01, x))


def logit(pct):
    return math.log(clamp(pct) / (100.0 - clamp(pct)))


def pinball_loss(forecast, answer_rates):
    """forecast: {"trophies": [{"id","q"}]}; answer_rates: {id: rate%}."""
    total, n = 0.0, 0
    for row in forecast["trophies"]:
        y = answer_rates[row["id"]]
        for tau, q in zip(LEVELS, row["q"]):
            d = logit(y) - logit(q)
            total += 2.0 * max(tau * d, (tau - 1.0) * d)
            n += 1
    return total / n


def typical_miss(forecast, answer_rates):
    errs = [abs(answer_rates[r["id"]] - r["q"][2]) for r in forecast["trophies"]]
    return sum(errs) / len(errs)


def coverage90(forecast, answer_rates):
    ok = sum(1 for r in forecast["trophies"]
             if r["q"][0] <= answer_rates[r["id"]] <= r["q"][4])
    return ok / len(forecast["trophies"])


def house_persistence(case):
    """The house baseline, reimplemented from the kit's starter."""
    last = case["history"][-1]
    spread = 0.5 * math.sqrt(case["horizon_minutes"] / 1440.0)
    rows = []
    for i, t in enumerate(case["trophies"]):
        rate = last["rates"][i]
        lg = logit(rate if rate is not None else 0.0)
        q = []
        for z in Z:
            v = 100.0 / (1.0 + math.exp(-(lg + z * spread)))
            q.append(min(99.99, max(0.01, round(v, 4))))
        rows.append({"id": t["id"], "q": q})
    return {"trophies": rows}


def house_curve(case):
    """The house curve baseline: OLS of logit(rate) on ln(1+hours) over the
    case's last 24h of reads, read at the target; spread = random walk +
    residual. Fewer than 3 reads -> persistence."""
    hist = case["history"]
    if len(hist) < 3:
        return house_persistence(case)
    cutoff = datetime.fromisoformat(case["at"].replace("Z", "+00:00")) - timedelta(hours=24)
    rows = []
    target_h = (datetime.fromisoformat(case["target"].replace("Z", "+00:00")) - RELEASE).total_seconds() / 3600.0
    spread_rw = 0.5 * math.sqrt(case["horizon_minutes"] / 1440.0)
    for i, t in enumerate(case["trophies"]):
        xs, ys = [], []
        for r in hist:
            rt = datetime.fromisoformat(r["at"].replace("Z", "+00:00"))
            if rt < cutoff:
                continue
            rate = r["rates"][i]
            if rate is None:
                continue
            h = (rt - RELEASE).total_seconds() / 3600.0
            xs.append(math.log1p(h))
            ys.append(logit(rate))
        if len(xs) < 3:
            rows.append(house_persistence(case)["trophies"][i])
            continue
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx > 1e-12 else 0.0
        a = my - b * mx
        resid = math.sqrt(sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys)) / n)
        spread = math.sqrt(spread_rw ** 2 + resid ** 2)
        lg = a + b * math.log1p(target_h)
        q = []
        for z in Z:
            v = 100.0 / (1.0 + math.exp(-(lg + z * spread)))
            q.append(min(99.99, max(0.01, round(v, 4))))
        rows.append({"id": t["id"], "q": q})
    return {"trophies": rows}


# ---------------------------------------------------------------- practice
def practice_answer(case, rng):
    """Reconstructed answer for a practice case, from the rules' facts:
    players tracked 638 -> 3,868 at the 04:30 refresh; every rate but the
    100% one lower. Counts grow a little in 90 minutes, by category."""
    last = case["history"][-1]
    n_new = 3868
    ans = {}
    for i, t in enumerate(case["trophies"]):
        rate = last["rates"][i]
        if rate is None:
            ans[t["id"]] = 0.01
            continue
        if rate >= 99.99:
            ans[t["id"]] = 100.0
            continue
        cat = classify(t)
        growth = {"story_ch1": 1.15, "story_ch2": 1.15, "story_ch3": 1.15,
                  "story_ch4": 1.15, "story_final": 1.10, "story_mission": 1.12,
                  "side_final": 1.08, "side_strand": 1.05, "grind": 1.03,
                  "collect": 1.03, "skill": 1.05, "misc_easy": 1.10,
                  "secret_misc": 1.08, "platinum": 1.0, "completion100": 1.0}.get(cat, 1.08)
        count = rate * 638 / 100.0 * growth * rng.uniform(0.9, 1.1)
        ans[t["id"]] = round(100.0 * count / n_new, 2)
    return ans


def run_practice():
    kit = ROOT.parent / "kit" / "gta6-trophy-rarity-forecast-01-kit" / "input"
    rng = random.Random(7)
    print("PRACTICE (reconstructed answers -- approximate, see docstring)")
    print(f"{'case':<6}{'model':<22}{'loss':>8}{'typ-miss':>9}{'cov90':>7}")
    for name in ("p00", "p01"):
        case = json.loads((kit / f"{name}.in").read_text())
        ans = practice_answer(case, rng)
        mine = forecast_case(case, name)
        base = house_persistence(case)
        curve = house_curve(case)
        for label, fc in (("mine", mine), ("house persistence", base), ("house curve", curve)):
            print(f"{name:<6}{label:<22}{pinball_loss(fc, ans):>8.4f}"
                  f"{typical_miss(fc, ans):>9.2f}{coverage90(fc, ans):>7.2f}")
    print("  (house baseline scores ~1.51 on the real practice per the rules)")


# ---------------------------------------------------------------- synthetic final
# Independent generative parameters -- deliberately NOT the forecaster's
# priors: different week-one targets, different population growth.
SCENARIOS = {
    "base": dict(n_inf=180_000, t50_n=36.0, k_n=1.1,
                 week1={"story_ch1": 38.0, "story_ch2": 24.0, "story_ch3": 17.0,
                        "story_ch4": 12.0, "story_final": 6.0, "story_mission": 15.0,
                        "side_final": 3.0, "side_strand": 2.0, "grind": 0.15,
                        "collect": 1.8, "skill": 1.5, "misc_easy": 9.0,
                        "secret_misc": 4.5, "platinum": 0.01, "completion100": 0.03}),
    "slow": dict(n_inf=120_000, t50_n=48.0, k_n=1.0,
                 week1={"story_ch1": 30.0, "story_ch2": 18.0, "story_ch3": 12.0,
                        "story_ch4": 8.0, "story_final": 4.0, "story_mission": 10.0,
                        "side_final": 2.0, "side_strand": 1.2, "grind": 0.08,
                        "collect": 1.0, "skill": 0.8, "misc_easy": 6.0,
                        "secret_misc": 3.0, "platinum": 0.01, "completion100": 0.02}),
    "fast-pop": dict(n_inf=400_000, t50_n=24.0, k_n=1.3,
                     week1={"story_ch1": 48.0, "story_ch2": 32.0, "story_ch3": 24.0,
                            "story_ch4": 18.0, "story_final": 9.0, "story_mission": 20.0,
                            "side_final": 5.0, "side_strand": 3.5, "grind": 0.4,
                            "collect": 3.0, "skill": 2.5, "misc_easy": 14.0,
                            "secret_misc": 7.0, "platinum": 0.02, "completion100": 0.06}),
    # Slow progression: players reach each milestone late, rates still
    # climbing hard at day 7 (no early saturation -- the world where
    # persistence is weakest).
    "late": dict(n_inf=150_000, t50_n=42.0, k_n=1.0, t50_scale=1.8,
                 week1={"story_ch1": 42.0, "story_ch2": 27.0, "story_ch3": 19.0,
                        "story_ch4": 13.0, "story_final": 7.0, "story_mission": 16.0,
                        "side_final": 3.5, "side_strand": 2.5, "grind": 0.2,
                        "collect": 2.2, "skill": 1.8, "misc_easy": 10.0,
                        "secret_misc": 5.0, "platinum": 0.01, "completion100": 0.04}),
}
# Hours after release when half of a category's week-one earners have it.
T50_EARN = {"story_ch1": 18.0, "story_ch2": 30.0, "story_ch3": 48.0,
            "story_ch4": 66.0, "story_final": 96.0, "story_mission": 54.0,
            "side_final": 84.0, "side_strand": 108.0, "grind": 120.0,
            "collect": 96.0, "skill": 84.0, "misc_easy": 36.0,
            "secret_misc": 60.0, "platinum": 150.0, "completion100": 150.0}


def simulate(scn, trophies, opening_ids=frozenset()):
    """Returns (case_f00, answer_rates). Rates are what Exophase would print.
    opening_ids: trophies whose real launch-night rate is ~100% (the opening
    mission) -- their week-one truth is ~88%, like RDR2's first mission."""
    p = SCENARIOS[scn]
    deadline = datetime(2026, 11, 21, 11, 30, tzinfo=timezone.utc)
    target = datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc)

    def n_players(t_hours):
        return p["n_inf"] / (1.0 + (p["t50_n"] / max(t_hours, 0.1)) ** p["k_n"])

    def true_rate(tr, t_hours):
        if tr["id"] in opening_ids:
            # The opening mission: ~every tracked player holds it from the
            # first read (100% at launch night in the real data); it only
            # dilutes as the tracked population broadens, to ~88% by day 7.
            return 98.0 - 10.0 * (t_hours / 168.0)
        cat = classify(tr)
        m = p["week1"][cat]
        t50 = T50_EARN[cat] * p.get("t50_scale", 1.0)
        # Logistic in log-time, reaching m at 168h by construction.
        s = 0.55
        f = 1.0 / (1.0 + math.exp(-(math.log(max(t_hours, 0.1)) - math.log(t50)) / s))
        f168 = 1.0 / (1.0 + math.exp(-(math.log(168.0) - math.log(t50)) / s))
        return m * f / f168

    # Reads every 30 min on launch night, every 10 min after (house clock).
    reads = []
    t = datetime(2026, 11, 18, 23, 50, tzinfo=timezone.utc)
    step = timedelta(minutes=30)
    while t < deadline:
        h = (t - RELEASE).total_seconds() / 3600.0
        n = n_players(h)
        rates = []
        for tr in trophies:
            r = true_rate(tr, h)
            # Exophase prints 2 decimals; counts are integers.
            count = round(r * n / 100.0)
            rates.append(round(100.0 * count / n, 2))
        reads.append({"slot": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "at": t.isoformat().replace("+00:00", "Z"),
                      "players_tracked": round(n), "trophies_earned": None, "rates": rates})
        if t >= datetime(2026, 11, 19, 4, 30, tzinfo=timezone.utc):
            step = timedelta(minutes=10)
        t += step
    answer = {}
    h = 168.0
    n = n_players(h)
    for tr in trophies:
        r = true_rate(tr, h)
        count = round(r * n / 100.0)
        answer[tr["id"]] = round(100.0 * count / n, 2)
    case = {"schema": "makefun/gta6-trophies-case/v1", "id": "f00",
            "at": deadline.isoformat().replace("+00:00", "Z"),
            "horizon_minutes": 6510, "target": target.isoformat().replace("+00:00", "Z"),
            "levels": LEVELS,
            "game": {"name": "Grand Theft Auto VI", "platform": "PS5",
                     "release_date": "2026-11-19",
                     "source": "https://www.exophase.com/game/grand-theft-auto-vi-psn/trophies/"},
            "trophies": trophies, "history": reads,
            "notes": "synthetic backtest case (simulated launch week, not real data)"}
    return case, answer


def opening_ids_from_kit():
    kit = ROOT.parent / "kit" / "gta6-trophy-rarity-forecast-01-kit" / "input"
    case0 = json.loads((kit / "p00.in").read_text())
    first = case0["history"][0]["rates"]
    return frozenset(tr["id"] for i, tr in enumerate(case0["trophies"])
                     if first[i] is not None and first[i] >= 95.0)


def run_final():
    kit = ROOT.parent / "kit" / "gta6-trophy-rarity-forecast-01-kit" / "input"
    trophies = json.loads((kit / "p00.in").read_text())["trophies"]
    opening = opening_ids_from_kit()
    print("\nSYNTHETIC FINAL (independent generative model, 3 scenarios)")
    print(f"{'scenario':<10}{'model':<22}{'loss':>8}{'typ-miss':>9}{'cov90':>7}")
    for scn in SCENARIOS:
        case, ans = simulate(scn, trophies, opening)
        mine = forecast_case(case, "f00")
        base = house_persistence(case)
        curve = house_curve(case)
        for label, fc in (("mine", mine), ("house persistence", base), ("house curve", curve)):
            print(f"{scn:<10}{label:<22}{pinball_loss(fc, ans):>8.4f}"
                  f"{typical_miss(fc, ans):>9.2f}{coverage90(fc, ans):>7.2f}")


def calibration_analysis():
    """Reproducible practice LOO category bias and sigma grid diagnostics."""
    kit = ROOT.parent / "kit" / "gta6-trophy-rarity-forecast-01-kit" / "input"
    rng = random.Random(7)
    practices = []
    for name in ("p00", "p01"):
        case = json.loads((kit / f"{name}.in").read_text())
        practices.append((name, case, practice_answer(case, rng)))
    print("\nLOO LOGIT BIAS (train practice case -> held-out case)")
    category_errors = {}
    for train_idx, test_idx in ((0, 1), (1, 0)):
        train_name, train_case, train_ans = practices[train_idx]
        test_name, test_case, test_ans = practices[test_idx]
        train_fc = forecast_case(train_case, train_name)
        test_fc = forecast_case(test_case, test_name)
        train_by_cat = {}
        for row, tr in zip(train_fc["trophies"], train_case["trophies"]):
            cat = "opening" if row["q"][2] > 95 else classify(tr)
            train_by_cat.setdefault(cat, []).append(logit(train_ans[row["id"]]) - logit(row["q"][2]))
        biases = {cat: sorted(errs)[len(errs)//2] for cat, errs in train_by_cat.items()}
        residuals = []
        test_by_cat = {}
        for row, tr in zip(test_fc["trophies"], test_case["trophies"]):
            cat = "opening" if row["q"][2] > 95 else classify(tr)
            error = logit(test_ans[row["id"]]) - logit(row["q"][2])
            residuals.append(error - biases.get(cat, 0.0))
            test_by_cat.setdefault(cat, []).append(error)
            category_errors.setdefault(cat, []).append(error)
        print(f"{train_name} -> {test_name}: global train median={sorted([logit(train_ans[r['id']])-logit(r['q'][2]) for r in train_fc['trophies']])[27]:.4f}, heldout corrected mean={sum(residuals)/len(residuals):.4f}")
        for cat in sorted(set(train_by_cat) | set(test_by_cat)):
            held = test_by_cat.get(cat, [])
            if held:
                print(f"  {cat}: train bias={biases.get(cat, 0.0):+.4f}, heldout mean={sum(held)/len(held):+.4f}")
    print("  BIAS_BY_CATEGORY left at zeros unless both directions agree in sign.")

    datasets = [(name, case, ans) for name, case, ans in practices]
    for scn in SCENARIOS:
        case, ans = simulate(scn, json.loads((kit / "p00.in").read_text())["trophies"], opening_ids_from_kit())
        datasets.append((scn, case, ans))
    print("\nSIGMA_SCALE GRID (practice + synthetic)")
    best = None
    for scale in (0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10):
        model.SIGMA_SCALE = scale
        losses, practice_cov, synthetic_cov = [], [], []
        for name, case, ans in datasets:
            fc = forecast_case(case, name)
            losses.append(pinball_loss(fc, ans))
            cov = coverage90(fc, ans)
            (practice_cov if name in ("p00", "p01") else synthetic_cov).append(cov)
        mean_loss = sum(losses) / len(losses)
        pcov = sum(practice_cov) / len(practice_cov)
        scov = sum(synthetic_cov) / len(synthetic_cov)
        print(f"{scale:.2f}: mean pinball={mean_loss:.4f}, practice mean cov90={pcov:.3f}, synthetic mean cov90={scov:.3f}")
        if pcov >= 0.90 and scov >= 0.92 and (best is None or mean_loss < best[0]):
            best = (mean_loss, scale)
    model.SIGMA_SCALE = best[1] if best else 1.0
    print(f"selected SIGMA_SCALE={model.SIGMA_SCALE:.2f}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "practice"):
        run_practice()
    if which in ("all", "final"):
        run_final()
    if which in ("all", "calibration"):
        calibration_analysis()
