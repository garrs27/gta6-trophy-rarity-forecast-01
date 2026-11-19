"""Build the demo forecast (local only, not graded).

Builds a simulated final-like case from the REAL GTA VI trophy list and
the REAL launch-night rates in the kit's practice cases, with a simulated
2.5-day history from the backtest's independent "base" scenario, runs
the submitted main.py on it exactly as the grader would, and renders the
forecast as CSV, Markdown and HTML.

The demo case's history is SIMULATED -- it stands in for the real final
case (f00), which only exists at the deadline. Everything in the
forecast table is computed by main.py from that case file; nothing is
hand-written.
"""
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import tools.backtest as bt  # noqa: E402

DEMO = ROOT / "demo"
DEMO.mkdir(exist_ok=True)


def main():
    kit = ROOT.parent / "kit" / "gta6-trophy-rarity-forecast-01-kit" / "input"
    trophies = json.loads((kit / "p00.in").read_text())["trophies"]
    case, answer = bt.simulate("base", trophies, bt.opening_ids_from_kit())
    case["id"] = "f00-demo"
    case["notes"] = ("DEMO CASE -- history simulated with the backtest's independent "
                     "'base' scenario from the real trophy list and real launch-night "
                     "rates; stands in for the real final case f00, cut at the deadline.")
    (DEMO / "f00-demo.in").write_text(json.dumps(case, indent=1) + "\n")

    ind = DEMO / "in"
    outd = DEMO / "out"
    ind.mkdir(exist_ok=True)
    outd.mkdir(exist_ok=True)
    (ind / "f00-demo.in").write_text(json.dumps(case))
    env = dict(os.environ, MAKEFUN_INPUT_DIR=str(ind), MAKEFUN_OUTPUT_DIR=str(outd))
    subprocess.run([sys.executable, str(ROOT / "main.py")], env=env, check=True)
    fc = json.loads((outd / "f00-demo.out").read_text())
    (DEMO / "f00-demo.out").write_text(json.dumps(fc, indent=1) + "\n")

    from main import classify  # noqa: E402
    last = case["history"][-1]
    first = case["history"][0]
    rows = []
    for i, tr in enumerate(trophies):
        q = next(r["q"] for r in fc["trophies"] if r["id"] == tr["id"])
        cat = "opening" if first["rates"][i] is not None and first["rates"][i] >= 95.0 else classify(tr)
        rows.append({
            "id": tr["id"], "name": tr["name"], "tier": tr["tier"],
            "category": cat, "last_rate": last["rates"][i],
            "q05": q[0], "q25": q[1], "median": q[2], "q75": q[3], "q95": q[4],
            "truth_demo": answer[tr["id"]],
        })

    with open(DEMO / "forecast.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    med = sorted(rows, key=lambda r: -r["median"])
    lines = []
    lines.append("# GTA VI trophy rarity, week one — demo forecast\n")
    lines.append("Forecast of every GTA VI PlayStation 5 trophy's Exophase earn rate at "
                 "**2026-11-26 00:00 UTC** (one week after launch), computed by `main.py` "
                 "from the demo case `f00-demo.in` (simulated 2.5-day history, base "
                 "scenario — see `MODEL.md`). The `truth_demo` column is the simulator's "
                 "own day-7 rate, shown only to judge the forecast here; the program "
                 "never sees it.\n")
    lines.append("## Headline\n")
    lines.append(f"- Median forecast across all 55 trophies: "
                 f"**{sorted(r['median'] for r in rows)[27]:.2f}%**")
    lines.append(f"- Highest median: **{med[0]['name']}** at {med[0]['median']:.2f}% "
                 f"(90% band {med[0]['q05']:.2f}–{med[0]['q95']:.2f}%)")
    lines.append(f"- Story final mission (`You Gotta Know When to Get Off`): "
                 f"{next(r for r in rows if r['id'] == 7)['median']:.2f}% "
                 f"(band {next(r for r in rows if r['id'] == 7)['q05']:.2f}–"
                 f"{next(r for r in rows if r['id'] == 7)['q95']:.2f}%)")
    lines.append(f"- 100% completion (`A Long Road`): "
                 f"{next(r for r in rows if r['id'] == 14)['median']:.3f}%")
    lines.append(f"- Platinum (`Vice Got a Price!`): "
                 f"{next(r for r in rows if r['id'] == 1)['median']:.3f}%")
    lines.append(f"- Demo pinball loss (logit scale): "
                 f"**{bt.pinball_loss(fc, answer):.4f}** vs house persistence "
                 f"{bt.pinball_loss(bt.house_persistence(case), answer):.4f} and house "
                 f"curve {bt.pinball_loss(bt.house_curve(case), answer):.4f}")
    lines.append(f"- Demo 90% coverage: {bt.coverage90(fc, answer):.2f}, "
                 f"typical miss {bt.typical_miss(fc, answer):.2f} points\n")
    lines.append("## Per-trophy forecast\n")
    lines.append("| # | Trophy | Tier | Category | Last rate | Median | 90% band | Truth (demo) |")
    lines.append("|---:|---|---|---|---:|---:|---:|---:|")
    for r in rows:
        lines.append(f"| {r['id']} | {r['name']} | {r['tier']} | {r['category']} | "
                     f"{r['last_rate']:.2f}% | **{r['median']:.2f}%** | "
                     f"{r['q05']:.2f}–{r['q95']:.2f}% | {r['truth_demo']:.2f}% |")
    (DEMO / "forecast.md").write_text("\n".join(lines) + "\n")

    hrows = "".join(
        f"<tr><td>{r['id']}</td><td>{r['name']}</td><td>{r['tier']}</td>"
        f"<td>{r['category']}</td><td>{r['last_rate']:.2f}%</td>"
        f"<td><b>{r['median']:.2f}%</b></td>"
        f"<td>{r['q05']:.2f}–{r['q95']:.2f}%</td>"
        f"<td>{r['truth_demo']:.2f}%</td></tr>" for r in rows)
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>GTA VI trophy rarity, week one — demo forecast</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1000px;margin:2em auto;padding:0 1em}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:4px 8px;text-align:left}}
th{{background:#222;color:#fff}}tr:nth-child(even){{background:#f4f4f4}}</style></head>
<body><h1>GTA VI trophy rarity, week one — demo forecast</h1>
<p>Forecast of every GTA VI PlayStation 5 trophy's Exophase earn rate at <b>2026-11-26 00:00 UTC</b>,
computed by <code>main.py</code> from the demo case <code>f00-demo.in</code> (simulated 2.5-day history,
base scenario). The <i>Truth (demo)</i> column is the simulator's own day-7 rate, shown only to
judge the forecast here; the program never sees it. Demo pinball loss
<b>{bt.pinball_loss(fc, answer):.4f}</b> vs house persistence
{bt.pinball_loss(bt.house_persistence(case), answer):.4f} and house curve
{bt.pinball_loss(bt.house_curve(case), answer):.4f}.</p>
<table><tr><th>#</th><th>Trophy</th><th>Tier</th><th>Category</th><th>Last rate</th>
<th>Median</th><th>90% band</th><th>Truth (demo)</th></tr>{hrows}</table>
<p><i>Methodology: see MODEL.md. Priors: see priors.json.</i></p></body></html>"""
    (DEMO / "forecast.html").write_text(html)
    print(f"demo written: {len(rows)} trophies, loss {bt.pinball_loss(fc, answer):.4f}")


if __name__ == "__main__":
    main()
