# Implementation Plan: Stop agents running into obstacles

## Overview
Agents visibly shove against obstacles. The simulator never blocks a move — `environment.py:541-552` rotates the
requested direction in 10° steps until the step is clear, so an agent pushing at a wall slides along it, and in a
concave spot (two obstacles touching, or an obstacle against the boundary) the alternating ±10° search makes it
jitter in place. The controller (`src/utils/controllers/hivemind_policy.py`) makes this worse in four ways:

1. `_blocked()` only knows edges inside the 60° vision cone, so fruit *heard* through a wall behind/beside the agent
   is not filtered (`_eat`, line ~389) and the agent never turns toward heard fruit < 60 px (line ~401): it pushes
   into the wall until the fruit rots (up to 50 s).
2. `_relocate_to_tree` and `_go_to_claim` walk a straight line to an absolute target with no obstacle awareness.
3. Only `_walk()` bounces off walls, and only off edges in the cone (`WALL_TURN_DIST`).
4. Nothing detects "I'm not moving": dead-reckoning assumes the commanded move happened; the next landmark fix snaps
   the estimate back; the loop repeats every tick. Only `_go_to_claim` has a 40-tick stuck timer.

The learned landmark map (`self.landmarks`, exact absolute obstacle edges) makes all four fixable for localized
agents without pathfinding: exact line-of-walk blockage tests (`_blocked_abs`), a stuck signal from the fix snap-back,
and one-corner detours.

Previous plan (measurement / simplification / predator kills) was discarded by the user on 2026-09-17; the harness
(`evaluate.py`, 12 seeds, `--policy`, kills column) and `tests/test_policy_equivalence.py` from it remain the
verification tools.

## Architecture Decisions
- **Measure first.** A scratch script with true simulator positions defines "stuck" (commanded move > 0, actual
  displacement < 1 px) and reports the stuck fraction per mode. Every fix must move this number.
- **Use what we have.** No pathfinding, no new data structures: `_blocked_abs` + landmark endpoints for detours,
  the fix snap-back for stuck detection.
- **Behaviour changes are measured twice:** stuck fraction (must drop) and `python evaluate.py` 12-seed mean /
  kills (must not get worse beyond the ~±120 noise). The replay test is re-recorded after each accepted change.
- **Unlocalized agents keep today's behaviour** (they cannot use landmarks); they are a minority after the first
  minute.

## Dependency graph
```
T1 stuck metric (scratch/stuck.py)
 ├── T2 heard-through-wall fruit (exact blockage) ─┐
 ├── T3 stuck detector + target blacklist ─────────┼── Checkpoint A (stuck fraction, 12-seed score)
 └── T4 one-corner detour for absolute targets ────┘
        └── T5 re-record replay trajectory, commit
```

## Task List

### Phase 1: Measure
- [x] Task 1: `scratch/stuck.py` — stuck fraction per mode on seeds 1, 3, 6 (baseline row in `tasks/results.md`)

### Phase 2: Fixes (one ablation each, in order of expected impact)
- [ ] Task 2: Heard-through-wall fruit — localized agents filter fruit and claims with `_blocked_abs`; turn toward
      heard fruit before walking
- [ ] Task 3: Stuck detector — landmark fix snaps position back ≥ 60 % of the commanded move for 5 ticks →
      drop target/claim, blacklist it 200 ticks, hop perpendicular to the wall
- [ ] Task 4: One-corner detour — when the straight line to a tree/fruit target crosses a landmark edge, aim for
      the nearer endpoint (+15 px clearance) first

### Checkpoint A
- [ ] Stuck fraction down ≥ 70 % vs Task 1 baseline on the same seeds
- [ ] 12-seed `evaluate.py` mean and kills not worse than the committed baseline beyond noise
- [ ] Each fix committed separately with its numbers

### Phase 3: Wrap up
- [ ] Task 5: Re-record `scratch/trajectory_seed3_300s.pkl`, all tests green, results logged

### Checkpoint: Complete
- [ ] `tasks/results.md` has baseline + per-fix stuck fractions and 12-seed scores

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Fix reduces stuck ticks but agents then wander more and eat less | Med | Score gate at Checkpoint A; keep detours to one corner, never long routes |
| Stuck detector misfires on legitimate slow movement (swamp 0.5×, river 0.3×) | Med | Compare snap-back to the *biome-adjusted* commanded move |
| Landmark map incomplete early in the game | Low | Falls back to today's cone-only behaviour when no landmark is near |
| 12-seed runs are slow (~25–45 min) | Low | Use `scratch/run_detached.ps1` (one process per seed, `--workers 1`) |

## Open Questions
- None blocking. The simulator's deflection behaviour is fixed (evaluation uses the same code), so all fixes live in
  the controller.
