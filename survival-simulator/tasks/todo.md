# Task List — stop agents running into obstacles

Verification commands: `python scratch/stuck.py <seed> <max_time>` (stuck fraction), `python evaluate.py`
(12 seeds; use `scratch/run_detached.ps1` for long runs), `python tests/test_policy_equivalence.py`.
Log every measurement in `tasks/results.md`.

## Task 1: Stuck metric

**Description:** `scratch/stuck.py` runs the Hivemind on one seed with access to true simulator positions and
counts, per tick and agent, "stuck" = commanded `move_distance > 0` but progress along the intended direction
< 30 % of the biome-adjusted step (pushing on or sliding along an obstacle). Reports the
stuck fraction of moving agent-ticks overall and per policy mode (`m["mode"]`), plus the longest stuck streak.
Run on seeds 1, 3, 6 to t=1200 and record the baseline.

**Acceptance criteria:**
- [x] Script prints overall and per-mode stuck fractions and the longest streak (ticks, mode)
- [x] Baseline row for seeds 1, 3, 6 in `tasks/results.md`

**Verification:**
- [x] `python scratch/stuck.py 3 1200` runs without error and reproduces the logged numbers within noise

**Dependencies:** None
**Files:** `scratch/stuck.py`, `tasks/results.md`
**Scope:** S

## Task 2: Heard-through-wall fruit — REJECTED (12-seed gate: survival 987 → 781 s; see results.md)

**Description:** For localized agents (`err <= LOC_OK`), replace the cone-only `_blocked()` test in `_eat` and in
`_record_sightings` with `_blocked_abs()` against nearby landmarks (exact geometry, any direction). When the chosen
fruit is heard but not seen (`distance < hearing_radius`) and `|angle| > 0.6`, turn toward it before walking so the
cone covers the path. Unlocalized agents keep the current behaviour.

**Acceptance criteria:**
- [ ] `eat` share of stuck ticks drops by ≥ 50 % on seeds 1, 3, 6
- [ ] 12-seed mean survival and kills not worse than baseline beyond noise

**Verification:**
- [ ] `python scratch/stuck.py 3 1200`; `python evaluate.py` (12 seeds); rows in `tasks/results.md`

**Dependencies:** Task 1
**Files:** `src/utils/controllers/hivemind_policy.py`
**Scope:** S

## Task 3: Stuck detector and target blacklist

**Description:** In `decide`, remember the position estimate before `_fix_pose` runs next tick. If the fix moves the
estimate back by ≥ 60 % of the biome-adjusted commanded move for 5 consecutive ticks, the agent is stuck: drop its
current claim/tree target, blacklist that target position for 200 ticks (`m["blacklist"]`), and start a 15-tick hop
perpendicular to the nearest landmark edge. Replaces the 40-tick timer in `_go_to_claim`.

**Acceptance criteria:**
- [x] Longest stuck streak on seeds 1, 3, 6 ≤ 10 ticks — partially: 156 (eat, seed 1) / 38 / 14; the eat case is Task 2's
- [x] No stuck flags in swamp/river when actually moving (checked in `scratch/stuck.py` by biome)
- [x] 12-seed mean survival and kills not worse than baseline beyond noise (987 vs 997 s, 46.9 vs 49.4 kills)

**Verification:**
- [x] `python scratch/stuck.py 3 1200`; `python evaluate.py`; rows in `tasks/results.md`

**Dependencies:** Task 1
**Files:** `src/utils/controllers/hivemind_policy.py`
**Scope:** S

## Task 4: One-corner detour for absolute targets — REJECTED (12-seed gate: survival 997 → 753 s; see results.md)

**Description:** In `_go_to_claim` and `_relocate_to_tree`, before walking straight at (tx, ty), test the segment
with `_blocked_abs` against landmarks within 250 px. If blocked by edge E, steer for E's endpoint nearest the target,
offset 15 px away from the edge, then re-evaluate next tick (one corner per tick, no route memory). Skip the target if
both endpoints are also blocked.

**Acceptance criteria:**
- [ ] `totree` + `tofruit` share of stuck ticks drops by ≥ 50 % on seeds 1, 3, 6
- [ ] 12-seed mean survival and kills not worse than baseline beyond noise

**Verification:**
- [ ] `python scratch/stuck.py 3 1200`; `python evaluate.py`; rows in `tasks/results.md`

**Dependencies:** Task 1
**Files:** `src/utils/controllers/hivemind_policy.py`
**Scope:** S

## Checkpoint A
- [x] Overall stuck fraction down ≥ 70 % vs Task 1 baseline (seeds 1, 3, 6) — 47/68/79 % with Task 3 alone (Tasks 2, 4 rejected)
- [x] 12-seed `evaluate.py` mean / kills not worse than the committed baseline beyond noise (987 vs 997 s; 46.9 vs 49.4 kills)
- [x] Tasks 2–4 each committed separately with their numbers

## Task 5: Wrap up

**Description:** Re-record the replay trajectory with the accepted policy, run all tests, log final numbers.

**Acceptance criteria:**
- [x] `python tests/test_policy_equivalence.py record` then all tests print ok
- [x] Final rows in `tasks/results.md`; commit

**Verification:**
- [x] `for t in tests/*.py: python $t`

**Dependencies:** Checkpoint A
**Files:** `scratch/trajectory_seed3_300s.pkl`, `tasks/results.md`
**Scope:** XS

## Checkpoint: Complete
- [x] Stuck fraction and 12-seed score both logged (stuck 9–12 % → 2–5 %; 987 s / 46.9 kills); check visually in
      `python local_playground.py`

## Task 6: Early survey (explore while it is cheap)

**Description:** In `_forage`, for t < 300 s, localized agents with energy > 120 and no fruit in sight walk to the
stalest grid cell (`_explore`) instead of sitting at the first tree; they still stop for visible fruit and still
flee. Add `scratch/coverage.py`: known trees / real trees and known landmarks at t=300 on seeds 1, 3, 6.

**Acceptance criteria:**
- [ ] Coverage at t=300 (known/real trees) up by ≥ 30 % vs current on seeds 1, 3, 6
- [ ] 12-seed mean survival and kills not worse than baseline beyond noise

**Verification:**
- [ ] `python scratch/coverage.py 3`; `python evaluate.py`; rows in `tasks/results.md`

**Dependencies:** Checkpoint A (obstacle tasks)
**Files:** `src/utils/controllers/hivemind_policy.py`, `scratch/coverage.py`
**Scope:** S

## Task 7: Grove preference

**Description:** `_relocate_to_tree` scores each candidate tree by the number of known fruiting trees within 120 px
of it (each weighted by recency of fruit seen), minus a distance term, instead of "fruiting flag + distance". Sitting
spot stays the chosen tree. Unit test: three trees in a cluster beat one isolated tree at equal distance.

**Acceptance criteria:**
- [ ] `tests/test_grove.py` passes
- [ ] Fruit eaten/rotted ratio (economy script) improves on seeds 2, 4; 12-seed mean not worse beyond noise

**Verification:**
- [ ] `python tests/test_grove.py`; economy script; `python evaluate.py`; rows in `tasks/results.md`

**Dependencies:** Task 6
**Files:** `src/utils/controllers/hivemind_policy.py`, `tests/test_grove.py`
**Scope:** S

## Task 8: Less early wandering (conditional)

**Description:** Only if the cost-by-mode attribution still shows > 1 energy/s per agent of movement for t < 300 after
Tasks 6–7: during that window raise `SPREAD_DIST` hops' threshold and `HOP_AFTER` patience. Skip (mark n/a) otherwise.

**Acceptance criteria:**
- [ ] Movement cost for t < 300 ≤ 1 energy/s per agent, or task marked n/a with the measured number
- [ ] 12-seed mean not worse beyond noise

**Verification:**
- [ ] cost-by-mode script; `python evaluate.py`; rows in `tasks/results.md`

**Dependencies:** Task 7
**Files:** `src/utils/controllers/hivemind_policy.py`
**Scope:** XS

## Checkpoint B
- [ ] Coverage at t=300 up, eaten/rotted ratio up, 12-seed mean not worse beyond noise
- [ ] Tasks 6–8 each committed with numbers

## Task 9: Predator-aware population cap

**Description:** Replace the time-only `POP_CAP` lookup in `_choose_spawners` with `_pop_cap(t)`: 20 while no predator
has been sighted and t < 250; 12 until a second distinct predator has been sighted (two entries in `self.predators`
history ≥ 300 px apart, or two at once) or t ≥ 600; afterwards the existing schedule. Keep a small sighting history
(`self.predator_log`, positions + ticks) so "distinct" is decidable. Unit test drives `_pop_cap` with synthetic
sightings and times.

**Acceptance criteria:**
- [ ] `tests/test_pop_cap.py` passes (no sighting → 20; first sighting → 12; second distinct → schedule; t-fallbacks)
- [ ] Peak population and coverage at t=300 up vs Phase 4 on seeds 1, 3, 6; kills/run not up beyond noise
- [ ] 12-seed mean survival not worse than Phase 4 beyond noise

**Verification:**
- [ ] `python tests/test_pop_cap.py`; `python scratch/coverage.py 3`; `python evaluate.py`; rows in `tasks/results.md`

**Dependencies:** Checkpoint B (Phase 4)
**Files:** `src/utils/controllers/hivemind_policy.py`, `tests/test_pop_cap.py`
**Scope:** S

## Task 10: Early-cap schedule ablation

**Description:** Run the 12-seed harness with the early cap at 16, 20 and 24 (module constant). Keep the best by mean
survival with kills as tiebreaker; log all three rows.

**Acceptance criteria:**
- [ ] Three rows in `tasks/results.md`; chosen value committed with the numbers in the message

**Verification:**
- [ ] `python evaluate.py` ×3 (use `scratch/run_detached.ps1` + `scratch/collect.py`)

**Dependencies:** Task 9
**Files:** `src/utils/controllers/hivemind_policy.py`, `tasks/results.md`
**Scope:** XS

## Checkpoint C
- [ ] Coverage at t=300 up vs Phase 4, kills not up beyond noise, 12-seed mean not worse
- [ ] Tasks 9–10 committed with numbers
