# Results log

All rows: `python evaluate.py` unless noted. Score ≈ survived seconds; kills = predator kills per run.

## Historical (6 seeds 1–6, before the harness had a kills column)

| Version | Commit | Mean score | Min survived | Eaten penalty (sum) |
|---|---|---|---|---|
| v1 heuristic | — | 976 | 741 | −224 |
| v1 + capped dumps, multi-tree memory | — | 960 | 606 | −135 |
| v1 + tree merge, fruiting pref, sprint hysteresis | — (reconstructed as `simple_policy.py`) | **1178** | 617 | −238 |
| v1 + drift correction | — | 1077 | 499 | −168 |
| v2 localization + shared map | 5adab2a | 1047 | 738 | −186 |
| v2 + no spawn while fleeing | — | 928 | 481 | −243 |
| v2.1 + terrain-aware flee | db8f93e | 1068 | 753 | −181 |
| dummy | — | 27 | 15 | 0 |

## 12-seed runs (seeds 1–12)

(appended by Task 2 onward)

## Obstacle-stuck plan (stuck = progress along intended direction < 30 % of the biome-adjusted step)

| Policy / commit | seed | survived | stuck % of moving ticks | longest streak | top modes |
|---|---|---|---|---|---|
| baseline (v2.1 simplified, 8b4…) | 1 | 796 | 9.3 % | 333 (tofruit) | totree, tofruit, flee_mem |
| baseline | 3 | 1200 | 9.5 % | 362 (totree) | totree 30 %, tofruit 12 % |
| baseline | 6 | 1092 | 11.7 % | 178 (totree) | — |

### 12-seed gate (seeds 1–12, one process per seed)

| Policy | mean score | mean survived | min survived | kills/run | note |
|---|---|---|---|---|---|
| baseline v2.1 simplified (HEAD before Task 4) | 1025 | 997 | 569 | 49.4 | reference |
| Task 4 one-corner detour | 782 | 753 | 508 | 28.1 | **rejected**: stuck 9–12 % → 6–7 %, but survival −245 s; 47 % of steer calls diverted, 19 % gave the target up (corner oscillation on adjacent edges) |
| Task 3 stuck detector + blacklist | 1009 | 987 | 726 | 46.9 | **accepted**: stuck 9.3/9.5/11.7 % → 4.9/3.0/2.4 % (seeds 1/3/6), longest streak 333/362/178 → 156 (eat)/38/14 |
| Task 2 wall-aware fruit filter | 813 | 781 | 370 | 26.6 | **rejected**: eat-stuck → 0 % but survival −206 s. Lesson (also explains Task 4): the sim's 10°-step deflection slides agents around obstacles for free, so a straight line crossing an edge is usually still reachable; dropping such targets starves the colony. Only real non-progress (Task 3 snap-back) should trigger a give-up. |

### Phase 4 — coverage baseline (Task 6 premise check)

| seed | t | tree coverage (known/real) | landmarks | cells visited (of 30) | pop |
|---|---|---|---|---|---|
| 1 | 300 | 76 % (44/58) | 668 | 24 | 15 |
| 3 | 300 | 83 % (55/66) | 592 | 22 | 15 |
| 6 | 300 | 81 % (42/52) | 627 | 22 | 16 |

Task 6 (early survey) skipped: the map is already ~80 % known by t=300; the +30 % target is unreachable. Rotting fruit
is a matter of not sitting at the right trees (Task 7), not of not knowing where trees are.
| Task 7 grove preference (`_grove_value`, GROVE_R 120, GROVE_VALUE 80) | 1180 | **1142** | 837 | 44.5 | **accepted**: +155 s vs Task 3; capture ratio inconclusive (seed 2: 84 vs 82 %, seed 4: 67 vs 72 %) |
| Task 8 less early wandering (spread 70 px, patience 30 s for t<300) | 995 | 975 | 674 | 49.7 | **rejected**: early movement 2.7 → 1.9 energy/s per agent, but survival −167 s vs Task 7. Early spreading pays for itself. |
| Task 9 predator-aware cap (20 → 12 → schedule) | 955 | 930 | 586 | 44.8 | **rejected**: peak pop 21.5 as intended, coverage 91/60/46 %, survival −212 s vs Task 7 |
| Task 10 early cap 16 | 1007 | 983 | 606 | 52.0 | **rejected**: −159 s vs Task 7; 24 skipped (dominated). Cap stays at 12. |

**Final policy = Task 7 state (commit with "grove preference"): 12-seed mean survived 1142 s, min 837 s, 44.5 kills/run.**

### Served policy decision (2026-09-17)

Same 3 seeds × 3 repeats: `simple_policy` (original plan) mean 900 (worst 632, 42–86 kills) vs `hivemind_policy` mean 1044
(worst 859, 35–70 kills). User chose to serve the **original-plan `simple_policy`** anyway; `agent_server.py` and
`local_playground.py`/`evaluate.py` default now point to it. `hivemind_policy.py` stays in the repo.

### Learned evasion (2026-09-17): duel objective (`scratch/duel_env.py`, 300 fixed randomized 1-v-1 setups on seeds 1–12)

Reward = −energy spent/100 per tick, −5 on death. Agent energy U(40,400), predator energy U(50,200), distance U(40,250).

| Policy | mean reward | death rate | energy spent | note |
|---|---|---|---|---|
| served rule (simple_policy threat branch, current constants) | −2.096 | 28.3 % | 102.6 | baseline (600-duel run: −2.131 / 28.2 % / 98.0) |
| rule, (1+22)-ES over 6 flee constants, 25 gens (`scratch/tune_flee.py`) | −2.039 | 26.7 % | 96.4 | plateau after gen 5: CHARGE_DIST=CHARGE_RELEASE=92, SEEN_ANGLE=2.36, FLEE_MEMORY=34 — rule shape is the limit, not the constants; **not adopted** (gain within duel noise of a rule change) |

### Heuristic-first plan (2026-09-17): spread agents apart before any RL

| Task | mean score | mean survived | min survived | kills/run | note |
|---|---|---|---|---|---|
| Task 0 baseline, served `simple_policy` + learned flee net (`flee_weights.npz` present) | 1164 | **1138** | 630 | 50.3 | reference for this plan |
| Task 0 baseline, same policy with the hand flee rule (weights file removed) | 952 | 924 | 519 | 47.2 | net ON is +214 s; the net wiring is now committed |
| Task 0 baseline on seeds 13–24 (net ON) | 1104 | 1073 | 822 | 42.4 | 24-seed baseline = **1105 s** |
| Task 1 spread hop (`SPREAD_DIST` 110, `HOP_TICKS` 15, `HOP_MIN_ENERGY` 120, `TAKEN_R` 40), seeds 1–12 / 13–24 | 1179 / 1131 | 1149 / 1098 | 584 / 897 | 46.9 / 48.7 | 24-seed **1124 s, +18 ± 68 s (paired sd 332), 12/24 seeds win** — noise-level; **kept** (never negative, user hypothesis). Premise check on seeds 1–2: a neighbour is inside 110 px only 21 % of agent-ticks, `spread` is 4 % of mode-ticks; `totree` 23–28 % and `camp` 14–20 % dominate. |
| Task 2 spread on spawn | — | — | — | — | skipped: subsumed by Task 1 (the richer parent hops away from its newborn) |
| Task 3 grove preference (`GROVE_VALUE` 80, score = d − 80·grove), 24 seeds | 1045 | 1015 | 592 | 44.8 | **rejected**: −109 s vs Task 1. A 4-tree grove buys 320 px of walking; too far on a dead-reckoned local frame. |
| Task 3b grove as tie-breaker (`GROVE_VALUE` 30, fruiting-first kept), 24 seeds | 1091 | 1060 | 677 | 44.4 | **rejected**: −64 s vs Task 1. Grove preference does not port from hivemind (shared, drift-corrected map) to the local policy. |
| Task 4 `SPREAD_DIST` 150, 24 seeds | 1109 | 1077 | 529 | 44.1 | **rejected**: −47 s vs 110. More spreading hurts; 110 is the ceiling. |

**Conclusion (2026-09-17):** spreading is not the bottleneck of `simple_policy` — agents are rarely crowded and the hop is worth
at most ~+20 s. Time goes to walking between trees and camping at fruitless ones; the local frame's drift makes long
relocations (grove preference) lose. Eval noise is sd ≈ 330 s per seed, so any change under ~±70 s needs 24+ seeds to call.
Final policy = Task 1 state: 24-seed mean survived 1124 s (baseline 1105).

### Camp-time A/B (2026-09-18), 24 seeds, paired vs Task 1 (1124 s)

Premise check (seeds 1–3, current policy): agents already eat ~90 % of fruit in t<300 (71–219 rot = 4–13 score points, the
ceiling of any "early fruit rush"); first predator arrives by t≈100–150 in every seed; mean energy fill falls 47 % → 32 % →
18 % over 0/300/600–900 s while pop drops 15 → 10. Fruit rush **not attempted**: a fruit is worth 0.02–0.06 points.

| Variant | mean survived | Δ vs Task 1 | wins | min | note |
|---|---|---|---|---|---|
| A `NO_FRUIT_GIVEUP` 200 → 100 | 1081 | −42 ± 72 | 12/24 | 534 | **rejected** |
| B leave a barren tree when a fruiting unvisited one is known | 1023 | −101 ± 77 | 9/24 | 646 | **rejected** |
| A+B | 1053 | −70 ± 72 | 8/24 | 485 | **rejected** |

Lesson: leaving trees sooner converts `camp` ticks into `totree` walking, which costs more than sitting. The local policy's
camping patience (200 ticks) is already on the short side; if anything, try *longer* patience next.
| C `NO_FRUIT_GIVEUP` 200 → 300 (longer patience) | 1119 | −5 ± 71 | 12/24 | 563 | **rejected** (flat); kills 43.0 vs 46.9. Camping patience is at its optimum between 100 and 300. |

### Population cap sweep (2026-09-18): `POP_CAP` schedule, `scratch/cap_sweep.sh`

Runs of the same seed are **not reproducible** (`environment.py` hands the policy `set`s of entities, so observation order
follows memory addresses; seed 1 gave 710 s and 1266 s for the identical policy). Seeds are therefore independent samples,
not pairs: n=24 gives SE ≈ 50 s per arm, n=72 ≈ 30 s. The round-1 control (base, 24 seeds) drew 973 s; its 48-seed re-run
drew 1106 s — a 130 s swing with no code change, which is the noise floor to keep in mind for every table above.

| `POP_CAP` | n | mean survived ± SE | min | kills/run |
|---|---|---|---|---|
| base `[(0,12),(600,12),(1800,5)]` | 72 | 1062 ± 30 | 581 | 48.2 |
| flat 8 | 24 | 1087 ± 51 | 575 | 37.9 |
| flat 10 | 24 | 1046 ± 41 | 704 | 41.5 |
| flat 12 (no late taper) | 24 | 1072 ± 52 | 668 | 45.8 |
| flat 14 | 72 | 1114 ± 29 | 672 | 51.4 |
| 10 → 5 (t 600–1800) | 24 | 1054 ± 44 | 682 | 42.3 |
| 12 → 3 (t 600–1800) | 72 | 1096 ± 29 | 469 | 48.1 |
| 12 → 5 earlier (t 300–1200) | 72 | 1104 ± 29 | 542 | 46.4 |
| 12 → 5 later (t 1200–2400) | 24 | 1083 ± 61 | 468 | 52.0 |
| 8 → 14 (few early, many late) | 72 | 1103 ± 32 | 485 | 43.9 |
| 6 → 12 (t 0–900) | 24 | 1031 ± 55 | 528 | 41.2 |

**Conclusion:** every schedule lands in 1030–1115 s; the best point estimate (flat 14, +52 ± 42 s) is within noise and the
12-seed Tasks 9–10 found 16/20 worse. Agent count in 8–14, with or without a taper in either direction, does not move
survival. `POP_CAP` stays `[(0,12),(600,12),(1800,5)]`. Kills scale with the cap (flat 8: 38, flat 14: 51) while survival
does not, so more agents ≈ more predator food, fewer agents ≈ less foraging — the two cancel.

### Shared map (2026-09-18): serve `hivemind_policy` + learned flee net

The simulator is **nondeterministic per seed** (SPEC; confirmed: same code, seed 1 survived 710 s then 1412 s), so
`--repeat` adds real samples. Rows below are 24 seeds × passes.

| Policy | pass 1 | pass 2 | mean survived | kills/run | note |
|---|---|---|---|---|---|
| `simple_policy` Task 1 state (served until now) | 1124 | 1124 | **1124** | 47.0 | per-seed values differ between passes; equal means are coincidence |
| `hivemind_policy` as-is (hand flee rule) | 1019 | — | 1019 | 51.8 | seeds 1–12 alone: 1007 vs the 1142 recorded for the same commit — that gap is run-to-run noise |
| `hivemind_policy` + flee net (`FLEE_NET`, same wiring as simple_policy) | 1227 | 1184 | **1205** | 44.4 | **accepted, now served**: +81 s over simple_policy across 48 games, +186 s over hivemind without the net |

Server smoke (`scratch/server_smoke.py`): 10.9 ms/tick mean, 38 ms max, clean reset on game 2.

### Flee-net RL round 2 (2026-09-18): plateau — no variant beats v1

| Candidate | training | 48-game mean survived | kills/run | note |
|---|---|---|---|---|
| v1 (served, zero-padded to OBS_DIM 16) | — | 1173 | 45.9 | same-day reference (`scratch/night_v1_full.txt`) |
| v2 duel: second-predator features, 1-v-N duel env, 1161 PPO iters | duel eval −2.14 / 31 % vs v1 −2.38 / 34 % | 1199 | 41.7 | +26 s, noise; **not adopted** |
| in-game PPO (`scratch/train_flee_game.py`), 37 iters × 20 full games, ~380 k flee steps/iter | ep reward −0.88 → −0.84, deaths/flee-episode 11.2 → 10.4 % | 1218 (24 games, greedy eval it 19) | 39.8 | flat within ±70; stopped; **not adopted** |

Conclusion: evasion is at its ceiling for this net. Deaths are ~11 % of in-game flee episodes; the remaining kills hit agents that
never saw the predator or could not sprint (energy < 20 %). First duel run stalled at it 284 on an unbounded placement loop (fixed).

### Why the colony dies (`scratch/collapse.py`, `scratch/latefruit.py`, hivemind, seeds 1–3)

At death (t≈1050–1330) the map still holds 20–30 trees and 30–45 uneaten fruit. From t≈500 deaths ≥ births; energy fill 25–30 %;
`POP_CAP` shrinks the colony to 7 at t=1000 while births need ≥ 250 energy. Late game (t ≥ 700): `sit` 27–33 % of ticks, fleeing
27–40 %, eating/walking-to-fruit 12–14 %; median uneaten fruit is 320–350 px from the nearest agent, only 10–11 % within 150 px;
the hivemind knows 13–18 % of map fruit; 34–49 % of agents can sprint. The colony starves next to food it neither reaches
(`HOME_REACH` 320, `FRUIT_REACH` 200) nor knows about (`TREE_TTL` 60 s < tree lifetime, explore only after 15 s idle, ≤ 600 px).

### Forage variants (2026-09-18), hivemind + flee net v1, 48 games each (24 seeds × 2), baseline same-day 1173 (96-game 1189)

| Variant (all changes from t=600 unless noted) | mean survived | min | kills/run | note |
|---|---|---|---|---|
| reach: `HOME_REACH` 320→600, `FRUIT_REACH` 200→350 | 1144 | 555 | 42.6 | mechanism moved (sit 27→9 %, eat+tofruit 14→27 %, sprint-able 49→64 % on seed 1) but fleeing rose to 57 %; **flat** |
| survey: `HOP_AFTER` 150→60, explore ≤ 900 px, `TREE_TTL` 600→900 | 1140 | 611 | 41.9 | known fruit 13–18 → 14–21 %; **flat** |
| pop: `POP_CAP` flat 12 to 1800, `RESERVE` 80 from t=600 | 1148 | 745 | 46.3 | sprint-able 32 % (thinner energy per agent); **flat** |
| **disperse**: reach + `SPREAD_DIST` 110→300 (one agent per tree) | 1254 / 1209 (2 passes) | 810 / 645 | 47.5 / 54.2 | **96-game 1231, +42 ± 48**; late fleeing 40→27 % on seed 1 (one run reached 1797); kills up; not clearly above noise |
| disperse + pop | 1145 | 689 | 50.2 | **rejected** |

Predator facts that bound the late game (`environment.py:674-728`, `predator.py`): predators spawn asleep, wake at 100 energy,
walk at 5.5 energy/s and sprint at ~25/s → a chase lasts ≈ 4 s before a 3.3 s rest; eating refills to 200. Agents out-sprint
them (20 vs 15 px/tick) only above 20 % energy. Predator count = 0.01·t (18 at t=1800, 30 at 3000), never despawn.

**Served (2026-09-18 12:10): hivemind + flee net v1 + disperse** (`HOME_REACH` 600 / `FRUIT_REACH` 350 / `SPREAD_DIST` 300 from
t=600). 96-game mean 1231 s vs 1189 baseline; server smoke 11 ms/tick mean, 88 ms max, clean reset.

### Platform validation attempt 1 (2026-09-18): 666 s, "agent server bottleneck: accumulated wait > 600 s"

Budget = 600 s wait per game = 20 ms per tick *including network*. Server via a Cloudflare quick tunnel from a Windows box:
~90 ms/tick (tunnel RTT ~100 ms; platform is Hetzner Helsinki, 46.62.240.126). Fixes: `_fix_from_landmarks` heading test
moved before the trig/hypot (identical result) → decide 8 → 2.0 ms/tick, server-side < 1 ms per request; host the server on
a Hetzner VM in `hel1` (same DC, ~1 ms RTT) and register `http://<ip>:9052/predict` directly. 24-game sanity after the
optimization: 1278 s (disperse range).

### Late-game structural round (2026-09-18 afternoon), hivemind + flee v1 + disperse base, 48 games each

Measured first: the colony eats its fruit young — mean 31–36 energy per fruit, 55–68 % eaten under 30, 10–15 % ripe (fruit is
20 at spawn, 60 after 20 s, rots at 50 s). `scratch/hm_ripe.py`: fruit map records carry `ripe_tick` = (last tick any localized
agent could perceive the spot, 30 s pose history) + 200; claims and close-range eating skip unripe fruit unless energy < 25 %.
Result: mean energy per fruit 32 → 45, young share 61 → 21 %, early energy fill 48 → 80 %.

| Variant | mean survived | min | kills/run | note |
|---|---|---|---|---|
| ripe | 1231 | 754 | 54.0 | flat vs disperse 1231: extra energy is capped away (`max_energy`, `POP_CAP` 12→7→5) |
| **ripe + `POP_CAP` flat 12 to 1800 (`RESERVE` 80 from 600)** | **1271** | 662 | 55.6 | highest mean; second pass pending |
| ripe + cap 16 | 1252 | 773 | 61.8 | |
| ripe + avoid (fresh map predator < 280 px: face it, walk off) | 1207 | 755 | 50.4 | kills −4, survival flat |

Why everything lands at 1200–1280: with N ≈ 0.01·t predators each sweeping ~110 px/s × 250 px of vision, an agent is seen
about every 10 s at t≈1000 and loses ~11 % of encounters → life expectancy ≈ 100 s regardless of food; at t=1800 (18
predators) ≈ 55 s, below reproduction age. Food, spacing, reach and population are upstream of that limit.
| ripe + cap 12, pass 2 | 1202 | 646 | 54.8 | 96-game 1236 ± 30 — flat vs disperse |
| **sprint** = ripe + cap 12 + `HUNGRY` 0.30 + `RESERVE` 120 from t=600 + `SCAN_EVERY` 15 / alert 10 from t=600 | 1289 / 1262 | 728 / 517 | 62.5 | **96-game 1275 ± 28 vs disperse 1231 ± 27; 21 % of games > 1500 s; served 2026-09-18 15:45** |

Kill post-mortem (`scratch/deaths.py`, ripe+cap12, seeds 1–3, 188 kills): 35–45 % could not sprint when the predator was first
seen (energy < 105), 25–30 % first detected under 60 px (heard, outside the cone), ~50 % were sitting/scanning, 30 % had
several predators in view, ~1 % never saw it. The sprint variant targets the first two. decide 2.6 ms/tick mean, 14 ms max.

### Cover and open-view facing (2026-09-18 evening), on top of sprint (96-game 1275 ± 28), 48 games each

| Variant | mean survived | min | kills/run | note |
|---|---|---|---|---|
| view: after a scan / while sitting with no predator known, face the heading whose cone sees the most open ground (12 headings × 3 rays vs learned edges + boundary) | 1117 | 650 | 56.5 | **rejected, −158**. Mechanism moved (kills first noticed < 60 px: 26 → 18 %, never-saw-it 6 → 0) but survival fell: facing the open side faces away from the tree, so new fruit is not "watched" → loses its ripe dating → eaten young again |
| cover: from t=600 tree score += 150 px × exposure (share of 24 rays reaching 250 px unblocked) | 1198 | 718 | 57.8 | **rejected, −77** |
| view + cover | 1146 | 460 | 50.2 | **rejected** |

Both variants also cost ray casts (decide 2.6 → 5.5 ms/tick). Lesson: the sitting heading is load-bearing for the ripe-fruit
mechanism; any facing rule must keep the home tree inside the cone or the hearing radius.
| view2: open-view heading constrained to keep the nearest tree (< 80 px) inside the cone (7 candidates in ±(half−0.15) around the tree bearing) | 1165 | 702 | 49.9 | **rejected, −110**. Fewer kills (50 vs 62) but shorter games: sitting heading is not the lever; the constant turning (any |Δ| > 0.25 rad) also keeps agents out of the plain `sit` state |

### Selective breeding (2026-09-18 night), 48 games each; leaderboard ranks *score*, not survived

Children mutate ±50 % per trait (10 % each); the old `fitness()` bred for max_energy (500 → 960 over a game), which raises
the sprint lock (20 % of max) — a direct cause of "could not sprint" kills — and ignored sprint speed (cap 40, predators 15).

| Variant | score | survived | min score | kills/run | note |
|---|---|---|---|---|---|
| sprint (served), 96 games | 1311 ± 29 | 1275 | 542 | 59 | 33 % of games > 1450 |
| breed: fitness = 3·sprint/40 + speed/20 + 1.5·vision/400 + cone/(π/2) + hear/100 − max_e/1000 | 1260 | 1224 | 704 | 56 | sprint 20 → 26 by t=1200, but max_e still 929 (dumps ignore fitness); **rejected** |
| breed2: + weaker half (below median fitness) may not dump-breed | 1283 | 1218 | **829** | **40** | −28 score, +290 floor, −19 kills; candidate for the one-shot evaluation; pass 2 pending |
| breed2, pass 2 → 96 games | 1303 ± 27 | 1236 | 760 | 37.6 | 10th percentile 959 vs sprint 929; 27 % > 1450 vs 33 % |

**Decision (2026-09-18 night):** serve **sprint** for validation attempts (best is kept: more high draws). For the one-shot
evaluation, breed2 is the lower-variance pick at equal mean: `cp scratch/hm_breed2.py src/utils/controllers/hivemind_policy.py`
and restart `agent_server.py` before enqueueing. Deployment: server on a VM near Hetzner Helsinki (Azure Sweden Central), plain
`http://<ip>:9052/predict`, no tunnel — the 600 s per-game wait budget is 20 ms per tick including network.

### Resource-driven population (2026-09-19, teammate's idea), on sprint, 48 games each (sprint 96-game: score 1311, survived 1275)

No `POP_CAP`; births throttled only by `RESERVE`; from t=100 s, when colony mean energy < CULL_MEAN the oldest n/8 stop eating
(sit, no claims, still flee; dump-spawn first if > 100 energy).

| Variant | score | survived | min | kills/run | note |
|---|---|---|---|---|---|
| nocap (control, cull off) | 1195 | 1163 | 702 | 61.3 | **rejected** −112 |
| dyn, CULL_MEAN 100 | 1218 | 1186 | 689 | 64.2 | **rejected** −90; pop 37–40 by t=100, fruit eaten down to 13–25 on the map, mean energy 16–21 % all game = at the 20 % sprint lock |
| dyn, CULL_MEAN 200 | 1190 | 1158 | 687 | 64.1 | **rejected** −121; the cull cannot lift the mean once the population has overshot |

Lesson: with ripe-fruit waiting the early colony is rich enough to breed to 40; the release valve comes too late. The cap
(12) is doing real work for this policy — it keeps fill at 50–65 % early so agents can sprint.
| float: cap 12, from t=600 +1 per 50 energy of colony mean above 250 (max +6) | 1269 | 1230 | 715 | 53.7 | **rejected** −42 score / −45 survived vs sprint; inside noise but the wrong sign. Population closed. |

### 2026-09-19: flee net v3 (map features) and biome awareness, 48 games each vs sprint (score 1311 / survived 1275)

| Variant | score | survived | min | kills/run | note |
|---|---|---|---|---|---|
| flee net v3: + nearest map-only (unseen) predator features, 40 in-game PPO iters × 20 games from padded v1 | 1167 | 1124 | 571 | 51.7 | **rejected** −144. Greedy 24-game evals during training 1224 / 1262 / 1232 / 1172 — never above the baseline; per-episode deaths 11.6 → 10.0 % did not carry into games. The served weights stay v1 (zero-padded to OBS_DIM 20). |
| biome: no homes/claims/exploration in desert or river, walks steered around known cells, grove weighted by fruit rate | 1203 | 1172 | **159** | 58.0 | **rejected** −108, worst game of the whole project. Kill-zone finding stands (desert 2.4×, river 2.1–2.7× kill ratio; swamp ≈ 1× since predators are slowed too), but time spent there did not move — the terrain map only knows cells agents stood on, and much of that time is flee paths. |
| scout: from t=300 one young rich agent walks to the stalest unoccupied non-desert cell anywhere (committed mission, no claims en route), 30 s cooldown | 1180 | 1147 | 602 | 55.6 | **rejected** −131. Motivated by seed 2 (top half desert): the top-right grassland's fruit rots almost entirely (300–600 s: 93 rotted / 11 eaten) while the colony sits in the bottom half. Scouts reach the corner but no outpost forms — a lone agent in a 60 %-desert quadrant dies or drifts home, and eligible scouts run out after t≈600. A group relocation would be needed; not attempted. |

### Migration / expeditions (2026-09-19 afternoon) — abandoned at the mechanism check, no gate

`scratch/hm_migrate.py`: every 30 s a hungry colony (mean energy < 50 %) sends its 4 youngest fed agents (age < 40,
energy > 150) to the best unoccupied region — known trees, or per-cell peak tree count / biome prior for unseen cells —
walking with flee priority and no claims en route. Seed 2's rotting top-right corner *is* chosen once peaks are remembered
from tick 0. But 120 s after departure 0/4 of the party are alive in every one of seven expeditions on seeds 1–3, only
1–5 of them eaten: **agents live 60–120 s**, so a party arrives with ~60 s to live and cannot breed there (needs > 250
energy). The colony persists only where children are born, and that cannot be moved by walking. Biome knowledge is not
the gap either: the colony knows 60–66 % of all cells by t=300 (78–79 % of forest/grass/swamp cells), ~90 % by t=600.
| senescence: `OLD_AGE` 55→45, `OLD_DUMP_ENERGY` 250→180 (old agents convert to children earlier and cheaper) | 1270 | 1240 | 615 | 58.1 | **rejected** −41 score vs sprint (1311); inside noise, wrong sign. The existing ageing/dump rules already capture the idea; earlier conversion just makes more low-energy parents. |

### Flee direction variants (2026-09-19 evening), 48 games each vs sprint (score 1311, kills 59)

| Variant | score | survived | min | kills/run | note |
|---|---|---|---|---|---|
| terrain: the net's flee direction passed through `_flee_dir` (avoid known river/swamp/desert, walls, obstacle edges) | 1174 | 1162 | 615 | 66.1 | **rejected** −137. Desert kill share halved (14 → 7 %), river 11.5 → 10 %, but total kills rose: deflecting the net's chosen side/angle breaks its evasion geometry; terrain underfoot matters less than the line it takes |
| decoy: agents that cannot sprint or are ageing lead a visible predator away from the colony centroid, terrain-blind | 1192 | 1179 | 630 | 70.9 | **rejected** −120 |
| both | 1103 | 1114 | 758 | 84.2 | **rejected** −208 |

The served net's raw direction is the best flee policy we have; hand-filtering it in either direction loses.
