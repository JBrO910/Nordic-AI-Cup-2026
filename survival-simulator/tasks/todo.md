# Task List — stop agents running into obstacles

Verification commands: `python scratch/stuck.py <seed> <max_time>` (stuck fraction), `python evaluate.py`
(12 seeds; use `scratch/run_detached.ps1` for long runs), `python tests/test_policy_equivalence.py`.
Log every measurement in `tasks/results.md`.

## Task 1: Stuck metric

**Description:** `scratch/stuck.py` runs the Hivemind on one seed with access to true simulator positions and
counts, per tick and agent, "stuck" = commanded `move_distance > 0` but actual displacement < 1 px. Reports the
stuck fraction of moving agent-ticks overall and per policy mode (`m["mode"]`), plus the longest stuck streak.
Run on seeds 1, 3, 6 to t=1200 and record the baseline.

**Acceptance criteria:**
- [ ] Script prints overall and per-mode stuck fractions and the longest streak (ticks, mode)
- [ ] Baseline row for seeds 1, 3, 6 in `tasks/results.md`

**Verification:**
- [ ] `python scratch/stuck.py 3 1200` runs without error and reproduces the logged numbers within noise

**Dependencies:** None
**Files:** `scratch/stuck.py`, `tasks/results.md`
**Scope:** S

## Task 2: Heard-through-wall fruit

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
- [ ] Longest stuck streak on seeds 1, 3, 6 ≤ 10 ticks
- [ ] No stuck flags in swamp/river when actually moving (checked in `scratch/stuck.py` by biome)
- [ ] 12-seed mean survival and kills not worse than baseline beyond noise

**Verification:**
- [ ] `python scratch/stuck.py 3 1200`; `python evaluate.py`; rows in `tasks/results.md`

**Dependencies:** Task 1
**Files:** `src/utils/controllers/hivemind_policy.py`
**Scope:** S

## Task 4: One-corner detour for absolute targets

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
- [ ] Overall stuck fraction down ≥ 70 % vs Task 1 baseline (seeds 1, 3, 6)
- [ ] 12-seed `evaluate.py` mean / kills not worse than the committed baseline beyond noise
- [ ] Tasks 2–4 each committed separately with their numbers

## Task 5: Wrap up

**Description:** Re-record the replay trajectory with the accepted policy, run all tests, log final numbers.

**Acceptance criteria:**
- [ ] `python tests/test_policy_equivalence.py record` then all three tests print ok
- [ ] Final rows in `tasks/results.md`; commit

**Verification:**
- [ ] `for t in tests/*.py: python $t`

**Dependencies:** Checkpoint A
**Files:** `scratch/trajectory_seed3_300s.pkl`, `tasks/results.md`
**Scope:** XS

## Checkpoint: Complete
- [ ] Stuck fraction and 12-seed score both logged; agents no longer visibly run against obstacles in
      `python local_playground.py`
