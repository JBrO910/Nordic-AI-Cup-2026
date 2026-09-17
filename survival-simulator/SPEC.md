# SPEC — Survival simulator controller (Nordic AI Cup 2026)

## Goal
An HTTP agent controller (`agent_server.py` → `POST /predict`) that keeps the herbivore species alive for the full
3000 simulated seconds (30 000 ticks) across the three preset evaluation seeds, then minimises energy lost to
predators. Score ≈ seconds survived (max 3000) + fruit_energy/1000 per fruit − eaten_agent_energy/100 per kill.

## Constraints (from the simulator code, not the README)
- Tick 0.1 s. Living cost 0.1/tick. Walk 0.05/px, sprint 0.5/px above walk speed. Turn |angle|/2π (≤ 0.5).
  Spawn 100 (child gets 75). Sprint is locked below 20 % of max_energy. Aging: once age > hidden max_age (60–120 s),
  extra 0.01·age per tick — no agent lives past ~180 s, so the species must reproduce continuously.
- `move_direction` is relative to heading (README says absolute; code wins).
- Food decays exponentially: ~84 trees at t<300 → ~3 at t=3000. Fruit 20→60 energy over 20 s, rots at 50 s, spawns
  ≤ 60 px from a tree. Predators accumulate (~0.01·t), never despawn, chase only the closest agent they perceive,
  charge if the agent looks away or is within 90 px, otherwise circle; no memory.
- Server must answer each tick within 10 s (600 s cumulative); one process serves three consecutive games —
  controller state resets when `sim_time` decreases.
- Simulator is nondeterministic run-to-run (object-id set ordering); scores on one seed vary.

## Deliverables
- A controller module exposing `class ... : decide(step: dict) -> list[ActionRequest]` wired into `agent_server.py`.
- `evaluate.py`: headless multi-seed harness (mean / min survival / kills) — the only accepted measure of progress.
- `tasks/results.md`: every measured run (policy, commit, seeds, mean, min, kills).

## Acceptance
- 12-seed mean survival and kill count improve over the committed baseline beyond the measured noise floor.
- Chosen policy ≤ 300 lines after Phase 1 (`tasks/plan.md`), or a documented reason why not.
- End-to-end server run matches the headless score and resets cleanly between games.

## Out of scope
- Learned / RL controllers; changes to the simulator itself.
