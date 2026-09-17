# Implementation Plan: Higher score via measurement, simplification, then targeted fixes

## Overview
The controller (`src/utils/controllers/hivemind_policy.py`, 565 lines) scores the same as the 150-line version 3
did (6-seed means 930–1180, all within the ~±120 noise band; run-to-run nondeterminism in the sim adds more).
Two losses have been constant across every version: ~30 predator kills per run (`eaten −30…−77`) and late-game
starvation. Plan: (0) make the score measurable, (1) pick the simpler of two bases by A/B and strip everything that
doesn't pay, (2) fix predator kills with one measured change at a time, (3) late-game food, (4) ship.

Spec: `README.md` + `~/.claude/plans/read-the-readme-of-purring-wozniak.md` (mechanics extracted from code).

## Architecture Decisions
- **One number to steer by:** 12 seeds (`1..12`), reported as mean / min survival / total kills. Two runs of the
  same policy define the noise floor; a change counts only if it beats the floor.
- **Ablation, not intuition:** every removal or addition is a flag or a separate module compared on the same
  12 seeds. `evaluate.py --policy <module:Class>` selects the controller.
- **Two candidate bases, measured:** `simple_policy.py` = reconstruction of version 3 (local tree memory, sprint
  hysteresis, capped dumps; ~200 lines) vs current `hivemind_policy.py`. Whichever wins on 12 seeds is the base;
  the other is kept in git for reference only.
- **Keep what is verified and cheap:** the boundary/landmark localization is exact (1e-13 px) and ~60 lines; it
  stays only if the ablation shows the shared map pays. Terrain map and obstacle geometry ride on it.
- **Commit after each measured win** with the 12-seed numbers in the message; never lose a good version again.

## Dependency graph
```
T1 harness (12 seeds, --policy, --repeat, kills column)
 ├── T2 noise floor
 ├── T3 reconstruct simple_policy.py ── T4 A/B choose base
 │                                          └── T5..T7 strip mechanisms (one ablation each)
 │                                                 └── Checkpoint B
 │                                                       ├── T8 kill post-mortem → T9/T10/T11 predator fixes
 │                                                       └── T12 late-game food
 │                                                             └── T13 ship (server wiring, latency, 3-run reset)
```

## Task List

### Phase 0: Measurement
- [x] Task 1: `evaluate.py` — `--policy module:Class`, `--repeat N`, 12-seed default, kills column
- [ ] Task 2: Noise floor — run current policy twice on 12 seeds, record spread in `tasks/results.md`
- [x] Task 3: Reconstruct version 3 as `src/utils/controllers/simple_policy.py`
- [ ] Task 4: A/B simple vs hivemind on 12 seeds → choose base, commit both

### Checkpoint A
- [ ] `tasks/results.md` has noise floor + both bases; base chosen with a number, not a feeling

### Phase 1: Simplify the base (each task = one ablation; keep only if score does not drop below floor)
- [ ] Task 5: Collapse the three dispersal rules (spread / hop / share-richest-leaves) into one
- [ ] Task 6: Collapse target logic (claims / near-tree / stale-cell / stuck) into "nearest visible fruit, else sit,
      else one relocation rule"; delete duplicate `SCAN_EVERY`
- [ ] Task 7: Ablate localization + shared map as a whole (flag). Keep only if it beats the floor.

### Checkpoint B
- [ ] Base ≤ 300 lines, 12-seed score ≥ Checkpoint A base, committed

### Phase 2: Predator kills (currently ~30/run; target < 15)
- [ ] Task 8: Kill post-mortem on 3 seeds with `scratch/deaths.py` → one table: first-seen distance, energy,
      could-sprint, mode, biome, ticks fled. Pick the top cause.
- [ ] Task 9: Energy floor — never spawn below `0.2·max + 120`; sprint lock is death (14/24 kills couldn't sprint)
- [ ] Task 10: Ambush reduction — scan interval from predator count (≈0.01·t) and, if base keeps landmarks, sit
      with back to an obstacle edge
- [ ] Task 11: Terrain-aware flee (river/swamp) — only if base keeps localization; else skip

### Checkpoint C
- [ ] Kills < 15/run on 12 seeds, mean survival up vs Checkpoint B, committed

### Phase 3: Late-game food
- [ ] Task 12: Population cap from observed tree count (capacity ≈ fruiting trees); ablate `POP_CAP` schedule

### Phase 4: Ship
- [ ] Task 13: Wire `agent_server.py` to the chosen policy; run `simulation_server.py` twice against one server
      process (reset on `sim_time` decrease); `/predict` latency < 50 ms

### Checkpoint: Complete
- [ ] 12-seed mean recorded in `tasks/results.md`; server end-to-end verified; final commit tagged

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| 12-seed runs take ~30–60 min per policy | Med | `--workers` = cores; run ablations in background; batch two ablations per run |
| Version 3 reconstruction differs from the 1178 run | Low | It is a baseline, not a target; any faithful ~200-line local policy serves |
| Sim nondeterminism hides 5 % gains | Med | Only chase changes expected to be worth ≥ 100 s (kills, starvation); accept ties as "simpler wins" |
| Simplifying removes the thing that made late game work | Med | Ablate one mechanism per run; revert on drop |
| Evaluation seeds differ from the hidden preset seeds | Low | 12 random seeds; never tune to a single seed |

## Open Questions
- Team preference: keep iterating on `hivemind_policy.py` in parallel with this plan, or freeze it until
  Checkpoint A? (Parallel edits will invalidate the A/B.)
