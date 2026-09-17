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
