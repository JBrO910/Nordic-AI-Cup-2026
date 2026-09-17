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
