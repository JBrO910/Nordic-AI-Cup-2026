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
- [x] Task 2 (rejected by gate, reverted): Heard-through-wall fruit — localized agents filter fruit and claims with `_blocked_abs`; turn toward
      heard fruit before walking
- [x] Task 3: Stuck detector — landmark fix snaps position back ≥ 60 % of the commanded move for 5 ticks →
      drop target/claim, blacklist it 200 ticks, hop perpendicular to the wall
- [x] Task 4 (rejected by gate, reverted): One-corner detour — when the straight line to a tree/fruit target crosses a landmark edge, aim for
      the nearer endpoint (+15 px clearance) first

### Checkpoint A
- [x] Stuck fraction down ≥ 70 % vs Task 1 baseline on the same seeds (Task 3: 47/68/79 %)
- [x] 12-seed `evaluate.py` mean and kills not worse than the committed baseline beyond noise
- [x] Each fix committed separately with its numbers

### Phase 3: Wrap up
- [x] Task 5: Re-record `scratch/trajectory_seed3_300s.pkl`, all tests green, results logged

### Checkpoint: Complete
- [x] `tasks/results.md` has baseline + per-fix stuck fractions and 12-seed scores

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

---

# Phase 4 (appended 2026-09-17): early exploration, grove preference, less early wandering

## Findings that motivate it
- "Sprinting at the beginning": measured 0.0 % sprint ticks for t < 200 s (seed 3). What is visible is walking at
  full walk speed in 30–39 % of agent-ticks. Energy cost is per pixel (0.05/px) regardless of speed, so the lever
  is walking *less*, not slower.
- 94 % of rotted fruit is never seen by any agent (earlier coverage measurement); early game is the cheapest time
  to map trees, landmarks and terrain (food abundant, predators rare).
- Fruit spawns ≤ 60 px from each fruiting tree at 0.1/s independently, so a spot within reach of k fruiting trees
  yields k× the intake. `_relocate_to_tree` scores single trees; it should score spots.

## Dependency graph
```
Obstacle tasks (2–5) ──► T6 early survey ──► T7 grove preference ──► T8 less early wandering ──► Checkpoint B
```

## Task List
- [x] Task 6 (skipped: coverage already 76–83 % at t=300): Early survey — while t < 300 s, localized, energy > 120 and no fruit in sight: walk to the stalest
      grid cell instead of sitting. Metric: known trees / real trees at t=300 (world-map coverage) + 12-seed score.
- [x] Task 7: Grove preference — `_relocate_to_tree` scores candidates by fruiting trees within 120 px (recency
      weighted) minus distance. Metric: fruit eaten/rotted ratio + 12-seed score.
- [ ] Task 8: Less early wandering — only if movement cost is still > 1 energy/s per agent for t < 300 after T6/T7:
      raise the spread threshold and hop patience during that window. Metric: cost-by-mode attribution + score.

### Checkpoint B
- [ ] Coverage at t=300 up, eaten/rotted ratio up, 12-seed mean not worse beyond noise; each task its own commit.

---

# Phase 5 (appended 2026-09-17): predator-aware population cap

## Findings that motivate it
- `POP_CAP` is purely time-based (12 → 4). A sitting scanner covers ~125 k px² for 1 energy/s; 20 spread-out agents
  cover the whole map, cheaper than walking. Early food (~200 energy/s map-wide) affords it.
- Spawns are energy-gated (energy > 100 + reserve; child starts at 75), so a higher cap only pays together with the
  existing cheap-breed rule (`RESERVE_FREE` when an unoccupied fruiting tree is known).
- Predator spawn law: expected count ≈ 0.01·t; P(≥1) = 50 % at t≈120 s, 90 % at t≈215 s. Sightings live in
  `self.predators`. Trigger the reduction on first sighting *or* t ≥ 250, whichever first.
- There is no cull: "reduce" = stop breeding; the population declines through aging within ~2 min.
- Risk: more agents → more kills (−energy/100 each, and a kill refuels the predator). Score gate catches it.

## Dependency graph
```
Phase 4 (T6–T8) ──► T9 predator-aware cap ──► T10 schedule ablation ──► Checkpoint C
```

## Task List
- [ ] Task 9: Predator-aware cap — `_pop_cap(t)`: 20 until first predator sighting or t ≥ 250; 12 until a second
      distinct predator (two sightings ≥ 300 px apart) or t ≥ 600; then the current schedule. Unit-tested with
      synthetic sightings. Metrics: peak population, coverage at t=300, kills, 12-seed score.
- [ ] Task 10: Schedule ablation — early cap 16 / 20 / 24 on 12 seeds; keep the best, log all three.

### Checkpoint C
- [ ] Coverage at t=300 up vs Phase 4, kills not up beyond noise, 12-seed mean not worse; commits with numbers.
