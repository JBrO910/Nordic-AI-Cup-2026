# Task List — higher score via measurement, simplification, targeted fixes

Verification command for every task unless stated: `python evaluate.py` (12 seeds, prints mean / min / kills).
Record every result in `tasks/results.md` (policy, commit hash, mean, min survival, kills, wall time).

## Task 1: Evaluation harness upgrades

**Description:** Make `evaluate.py` the single source of truth: select the controller by `--policy module:Class`
(default `src.utils.controllers.hivemind_policy:Hivemind`), `--repeat N` to run each seed N times, default seeds
1–12, and report kills (count of score drops) next to the eaten-energy penalty.

**Acceptance criteria:**
- [x] `python evaluate.py --policy src.utils.controllers.dummy_agent_policy:dummy` and `--policy ...:Hivemind` both run
- [x] Output has one line per (seed, repeat) plus MEAN / MIN / total kills
- [x] `--repeat 2` doubles the rows

**Verification:**
- [x] Manual: run with `--seeds 1 2 --max-time 200` for both policies, check columns (`tests/test_evaluate.py` = ok)

**Dependencies:** None
**Files:** `evaluate.py`
**Scope:** S

## Task 2: Noise floor

**Description:** Run the current `Hivemind` twice on seeds 1–12 (`--repeat 2`) and record the per-seed spread and
the difference between the two means. This is the threshold a change must beat.

**Acceptance criteria:**
- [ ] `tasks/results.md` created with both runs and a stated threshold (e.g. "a change must beat the mean by > X")

**Verification:**
- [ ] Manual: numbers present in `tasks/results.md`

**Dependencies:** Task 1
**Files:** `tasks/results.md`
**Scope:** XS

## Task 3: Reconstruct version 3 as `simple_policy.py`

**Description:** Rebuild the ~200-line local policy that scored 1178/617 (per-agent frame, dead-reckoned multi-tree
memory with merging, fruiting flag, camp/hop, sprint hysteresis at 92/110 px, soft-capped old-age dumps, newborn scan)
from the session history, plus the one bug fix learned since: never spawn while fleeing. Same `decide(step)` interface.

**Acceptance criteria:**
- [x] `src/utils/controllers/simple_policy.py` ≤ 250 lines, no localization / shared map
- [x] Runs to completion on seeds 1–3 without exceptions

**Verification:**
- [x] `python evaluate.py --policy src.utils.controllers.simple_policy:Hivemind --seeds 1 2 3`

**Dependencies:** Task 1
**Files:** `src/utils/controllers/simple_policy.py`
**Scope:** M

## Task 4: A/B — choose the base

**Description:** Run both policies on seeds 1–12 and pick the base by mean survival with kills as tiebreaker; ties go
to the simpler one. Commit both files with the numbers in the message.

**Acceptance criteria:**
- [ ] `tasks/results.md` has both rows; base named in `tasks/plan.md` Architecture Decisions
- [ ] Git commit contains both policies and the numbers

**Verification:**
- [ ] `git log -1` shows the numbers

**Dependencies:** Tasks 2, 3
**Files:** `tasks/results.md`, `tasks/plan.md`
**Scope:** XS

## Checkpoint A
- [ ] Noise floor known, base chosen by number, everything committed
- [ ] Review with team before Phase 1

## Task 5: One dispersal rule

**Description:** The base has up to three overlapping ways to spread agents (spread-from-crowd, blind hop, richest-
leaves-shared-patch). Replace with a single rule: "if the nearest other agent is closer than D and I am the richer one,
walk D px away from it" (or the equivalent in the local-frame base). Ablate: score must not drop below the floor.

**Acceptance criteria:**
- [ ] Exactly one dispersal code path; constants `HOP_*`, `SHARE_DIST`, `SPREAD_DIST` reduced to one
- [ ] 12-seed mean within the noise floor of Checkpoint A (or better)

**Verification:**
- [ ] `python evaluate.py`; result row in `tasks/results.md`

**Dependencies:** Task 4
**Files:** chosen policy file
**Scope:** S

## Task 6: One targeting rule + tunables cleanup

**Description:** Reduce fruit/tree targeting to: visible unblocked fruit → go; else (if shared map exists) claimed
fruit within reach; else sit; relocate by one rule when nothing seen for `HOP_AFTER`. Remove the stuck/target
bookkeeping if the ablation shows no loss. Remove the duplicated `SCAN_EVERY` definition.

**Acceptance criteria:**
- [ ] No duplicate tunables; `_plan` has ≤ 5 tiers
- [ ] 12-seed mean within the noise floor (or better)

**Verification:**
- [ ] `python evaluate.py`; result row in `tasks/results.md`

**Dependencies:** Task 5
**Files:** chosen policy file
**Scope:** M

## Task 7: Ablate localization + shared map as a whole

**Description:** If the base is `hivemind_policy.py`, add a module flag `USE_WORLD_MAP` that disables localization,
world map, claims and terrain in one switch, and compare. Keep the subsystem only if it beats the floor; otherwise
delete it (git keeps it).

**Acceptance criteria:**
- [ ] One flag toggles the subsystem; both settings scored on 12 seeds
- [ ] Decision recorded in `tasks/results.md`; dead code deleted if it lost

**Verification:**
- [ ] `python evaluate.py` for both flag values

**Dependencies:** Task 6
**Files:** chosen policy file
**Scope:** S (flag) / M (deletion)

## Checkpoint B
- [ ] Base ≤ 300 lines, score ≥ Checkpoint A, committed with numbers

## Task 8: Kill post-mortem

**Description:** Run `scratch/deaths.py` on seeds 1, 3, 6 to t=1200 with the Checkpoint B base and tabulate: first-
seen distance, energy at first sight, could-sprint, mode before, biome, ticks fled, predators visible. Name the single
largest cause with its share.

**Acceptance criteria:**
- [ ] Table + one-sentence conclusion in `tasks/results.md`

**Verification:**
- [ ] Manual read

**Dependencies:** Checkpoint B
**Files:** `scratch/deaths.py`, `tasks/results.md`
**Scope:** XS

## Task 9: Energy floor

**Description:** An agent below `0.2·max_energy` cannot sprint and dies to any charge. Raise the spawn reserve so a
parent never drops below `0.2·max + 120` (enough for one sprint escape), and make old-age dumps respect the same floor
except when `aging` is confirmed.

**Acceptance criteria:**
- [ ] Post-mortem "could not sprint at first sight" share drops by half
- [ ] 12-seed kills and mean improve beyond the floor

**Verification:**
- [ ] `python evaluate.py`; `scratch/deaths.py` on seed 3

**Dependencies:** Task 8
**Files:** chosen policy file
**Scope:** XS

## Task 10: Ambush reduction

**Description:** Predators close 250→50 px in 13 ticks; a 30-tick scan cycle misses them. Set the scan interval from
the expected predator count (`0.01·sim_time`): e.g. 40 ticks at t<500, 15 ticks at t>2000. If the base keeps
landmarks, prefer sit spots within 15 px of an obstacle edge (halves the approach directions).

**Acceptance criteria:**
- [ ] Post-mortem "first seen < 60 px" share drops
- [ ] 12-seed kills improve beyond the floor

**Verification:**
- [ ] `python evaluate.py`

**Dependencies:** Task 9
**Files:** chosen policy file
**Scope:** S

## Task 11: Terrain-aware flee (only if localization kept)

**Description:** Keep the terrain map (biome per 40 px cell) and `_flee_dir` candidate scoring; verify on the duel
harness (`scratch/duel.py`) that flee never enters river/swamp, then ablate on 12 seeds.

**Acceptance criteria:**
- [ ] All 12 duel cases survive with ≤ 120 energy spent
- [ ] 12-seed kills not worse

**Verification:**
- [ ] `python scratch/duel.py`; `python evaluate.py`

**Dependencies:** Task 10
**Files:** chosen policy file, `scratch/duel.py`
**Scope:** S

## Checkpoint C
- [ ] Kills < 15/run, mean survival up, committed with numbers

## Task 12: Population cap from tree count

**Description:** Replace the time-based `POP_CAP` schedule with a cap tied to the number of known (or, in the local
base, recently seen) trees — capacity ≈ fruiting trees. Ablate.

**Acceptance criteria:**
- [ ] No-predator runs (`scratch/nopred.py`-style) reach ≥ 2500 s on seeds 2 and 4
- [ ] 12-seed mean not worse

**Verification:**
- [ ] `python evaluate.py`; no-predator script

**Dependencies:** Checkpoint C
**Files:** chosen policy file
**Scope:** S

## Task 13: Ship

**Description:** Wire `agent_server.py` to the chosen policy (module-level instance, `decide(step.dict())`). Run
`simulation_server.py` twice against one running server to confirm reset on `sim_time` decrease; log `/predict`
latency.

**Acceptance criteria:**
- [ ] Headless score ≈ server score on seed 1
- [ ] Second game on the same server process starts from a clean state
- [ ] Max `/predict` latency < 50 ms

**Verification:**
- [ ] Two terminals: `python agent_server.py`, then `python simulation_server.py` twice

**Dependencies:** Checkpoint C
**Files:** `agent_server.py`
**Scope:** XS

## Checkpoint: Complete
- [ ] Final 12-seed numbers in `tasks/results.md`; tagged commit; server verified
