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
