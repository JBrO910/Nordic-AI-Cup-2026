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
