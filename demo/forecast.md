# GTA VI trophy rarity, week one — demo forecast

Forecast of every GTA VI PlayStation 5 trophy's Exophase earn rate at **2026-11-26 00:00 UTC** (one week after launch), computed by `main.py` from the demo case `f00-demo.in` (simulated 2.5-day history, base scenario — see `MODEL.md`). The `truth_demo` column is the simulator's own day-7 rate, shown only to judge the forecast here; the program never sees it.

## Headline

- Median forecast across all 55 trophies: **5.05%**
- Highest median: **Just Like Paradise** at 93.53% (90% band 82.47–97.80%)
- Story final mission (`You Gotta Know When to Get Off`): 5.80% (band 1.97–15.90%)
- 100% completion (`A Long Road`): 0.016%
- Platinum (`Vice Got a Price!`): 0.015%
- Demo pinball loss (logit scale): **0.1770** vs house persistence 0.3857 and house curve 0.3314
- Demo 90% coverage: 1.00, typical miss 1.51 points

## Per-trophy forecast

| # | Trophy | Tier | Category | Last rate | Median | 90% band | Truth (demo) |
|---:|---|---|---|---:|---:|---:|---:|
| 1 | Vice Got a Price! | platinum | platinum | 0.00% | **0.01%** | 0.00–0.13% | 0.01% |
| 2 | Just Like Paradise | bronze | opening | 94.47% | **93.53%** | 82.47–97.80% | 88.00% |
| 3 | Paradise Lost | bronze | story_ch1 | 34.69% | **52.01%** | 26.09–76.89% | 38.00% |
| 4 | T**s Ass Drug Money | bronze | story_ch2 | 19.43% | **32.71%** | 13.67–59.88% | 24.00% |
| 5 | Vice City, Baby! | bronze | story_ch3 | 11.15% | **21.35%** | 8.12–45.45% | 17.00% |
| 6 | Top Of The World, Ma | bronze | story_ch4 | 6.41% | **13.84%** | 4.97–33.04% | 12.00% |
| 7 | You Gotta Know When to Get Off | gold | story_final | 2.40% | **5.80%** | 1.97–15.90% | 6.00% |
| 8 | Trust | bronze | story_mission | 9.17% | **18.51%** | 6.89–41.08% | 15.00% |
| 9 | Break the Bank | bronze | story_mission | 9.17% | **18.51%** | 6.89–41.08% | 15.00% |
| 10 | Family Matters | bronze | story_mission | 9.17% | **18.51%** | 6.89–41.08% | 15.00% |
| 11 | DWNFALL | bronze | story_mission | 9.17% | **18.51%** | 6.89–41.08% | 15.00% |
| 12 | Hi-Jacked | bronze | story_mission | 9.17% | **18.51%** | 6.89–41.08% | 15.00% |
| 13 | Snow Storm | bronze | story_mission | 9.17% | **18.51%** | 6.89–41.08% | 15.00% |
| 14 | A Long Road | gold | completion100 | 0.01% | **0.02%** | 0.01–0.05% | 0.03% |
| 15 | Cunning Stunts | silver | grind | 0.05% | **0.13%** | 0.04–0.41% | 0.15% |
| 16 | Master of None | bronze | misc_easy | 6.80% | **11.85%** | 4.19–29.21% | 9.00% |
| 17 | The Shootist | silver | grind | 0.05% | **0.13%** | 0.04–0.41% | 0.15% |
| 18 | Top Fun | bronze | skill | 0.67% | **1.44%** | 0.47–4.28% | 1.50% |
| 19 | Earn Cash, Not Kudos | bronze | skill | 0.67% | **1.44%** | 0.47–4.28% | 1.50% |
| 20 | Baited My Tackle | bronze | skill | 0.67% | **1.44%** | 0.47–4.28% | 1.50% |
| 21 | Stick Fiddler | bronze | misc_easy | 6.80% | **11.85%** | 4.19–29.21% | 9.00% |
| 22 | Road to Rehabilitation | bronze | side_final | 1.34% | **2.94%** | 0.98–8.52% | 3.00% |
| 23 | This Was No Boat Accident | bronze | side_final | 1.34% | **2.94%** | 0.98–8.52% | 3.00% |
| 24 | The Lone Rider | bronze | side_final | 1.34% | **2.94%** | 0.98–8.52% | 3.00% |
| 25 | Strangers & Freaks | silver | side_strand | 0.73% | **1.75%** | 0.58–5.18% | 2.00% |
| 26 | Supply & Demand | bronze | side_final | 1.34% | **2.94%** | 0.98–8.52% | 3.00% |
| 27 | Spin On This! | bronze | side_final | 1.34% | **2.94%** | 0.98–8.52% | 3.00% |
| 28 | Positive Mental Attitude | bronze | collect | 0.72% | **1.63%** | 0.54–4.85% | 1.80% |
| 29 | Fair Game | bronze | collect | 0.72% | **1.63%** | 0.54–4.85% | 1.80% |
| 30 | Don't Touch My Deck | silver | grind | 0.05% | **0.13%** | 0.04–0.41% | 0.15% |
| 31 | You WAiNKer! | silver | grind | 0.05% | **0.13%** | 0.04–0.41% | 0.15% |
| 32 | One Last Thing | bronze | grind | 0.05% | **0.13%** | 0.04–0.41% | 0.15% |
| 33 | Hot Together | bronze | misc_easy | 6.80% | **11.85%** | 4.19–29.21% | 9.00% |
| 34 | Retail Therapy | bronze | misc_easy | 6.80% | **11.85%** | 4.19–29.21% | 9.00% |
| 35 | Whip It Good | bronze | collect | 0.72% | **1.63%** | 0.54–4.85% | 1.80% |
| 36 | Gunslinger | bronze | skill | 0.67% | **1.44%** | 0.47–4.28% | 1.50% |
| 37 | Catch Me If You Can | bronze | secret_misc | 2.57% | **5.05%** | 1.70–14.05% | 4.50% |
| 38 | Challenging Tank | bronze | secret_misc | 2.57% | **5.05%** | 1.70–14.05% | 4.50% |
| 39 | Sneakthief | bronze | skill | 0.67% | **1.44%** | 0.47–4.28% | 1.50% |
| 40 | Maximum Withdrawal | silver | skill | 0.67% | **1.44%** | 0.47–4.28% | 1.50% |
| 41 | A Classic Blitz Play | bronze | skill | 0.67% | **1.44%** | 0.47–4.28% | 1.50% |
| 42 | The Goodtime State | bronze | collect | 0.72% | **1.63%** | 0.54–4.85% | 1.80% |
| 43 | Pest Control | bronze | misc_easy | 6.80% | **11.85%** | 4.19–29.21% | 9.00% |
| 44 | In The Beginning… | bronze | secret_misc | 2.57% | **5.05%** | 1.70–14.05% | 4.50% |
| 45 | Capital Offense | bronze | secret_misc | 2.57% | **5.05%** | 1.70–14.05% | 4.50% |
| 46 | Let’s Go Bowling | bronze | secret_misc | 2.57% | **5.05%** | 1.70–14.05% | 4.50% |
| 47 | Personal Best | bronze | secret_misc | 2.57% | **5.05%** | 1.70–14.05% | 4.50% |
| 48 | Actions Speak Louder | bronze | secret_misc | 2.57% | **5.05%** | 1.70–14.05% | 4.50% |
| 49 | Bad Luck, I Guess | bronze | secret_misc | 2.57% | **5.05%** | 1.70–14.05% | 4.50% |
| 50 | The Truth Is Out There | bronze | secret_misc | 2.57% | **5.05%** | 1.70–14.05% | 4.50% |
| 51 | Ten Pin | bronze | secret_misc | 2.57% | **5.05%** | 1.70–14.05% | 4.50% |
| 52 | Dime on the Dollar | bronze | misc_easy | 6.80% | **11.85%** | 4.19–29.21% | 9.00% |
| 53 | Treat Yo Self | bronze | misc_easy | 6.80% | **11.85%** | 4.19–29.21% | 9.00% |
| 54 | Little Boxes | bronze | collect | 0.72% | **1.63%** | 0.54–4.85% | 1.80% |
| 55 | On the Spot | bronze | collect | 0.72% | **1.63%** | 0.54–4.85% | 1.80% |
