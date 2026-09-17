"""Stuck metric: python scratch/stuck.py <seed> <max_time> [module:Class]
"stuck" = the agent commanded move_distance > 0 but its true displacement projected on the intended direction is
< 30 % of the commanded (biome-adjusted) step: it is pushing on, or sliding along, an obstacle.
Reports the stuck fraction of moving agent-ticks, per policy mode, per biome, and the longest stuck streak."""
import collections, math, os, sys
PENALTY = {"swamp": 0.5, "desert": 0.8, "river": 0.3}
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def measure(seed=3, max_time=1200.0, policy="src.utils.controllers.hivemind_policy:Hivemind"):
    import pygame; pygame.init()
    import importlib
    from src.core import SimulationCore
    mod, name = policy.split(":")
    hm = getattr(importlib.import_module(mod), name)()
    sim = SimulationCore(seed=seed); env = sim.env
    state = sim.step([])
    moving = collections.Counter(); stuck = collections.Counter(); biome_moving = collections.Counter(); biome_stuck = collections.Counter()
    streak = collections.defaultdict(int); longest = (0, "")
    while state["num_agents"] > 0 and env.time <= max_time:
        acts = hm.decide({"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]})
        before = {a.agent_id: (a.x, a.y, env.biome_map[int(a.x), int(a.y)].type, a.direction) for a in env.agents}
        modes = {aid: hm.mem[aid]["mode"] for aid in before}
        state = sim.step([(a.agent_id, a) for a in acts])
        after = {a.agent_id: (a.x, a.y) for a in env.agents}
        for act in acts:
            aid = act.agent_id
            if act.move_distance <= 0 or aid not in after:
                continue
            x0, y0, biome, heading = before[aid]
            want = heading + act.move_direction
            step = min(act.move_distance, 40) * PENALTY.get(biome, 1.0)
            progress = ((after[aid][0] - x0) * math.cos(want) + (after[aid][1] - y0) * math.sin(want)) / max(step, 1e-9)
            mode = modes[aid]
            moving[mode] += 1; biome_moving[biome] += 1
            if progress < 0.3:
                stuck[mode] += 1; biome_stuck[biome] += 1
                streak[aid] += 1
                if streak[aid] > longest[0]:
                    longest = (streak[aid], mode)
            else:
                streak[aid] = 0
    total = sum(moving.values())
    return dict(seed=seed, stuck_fraction=sum(stuck.values()) / max(total, 1), moving_ticks=total,
                by_mode={k: (stuck[k] / v, v) for k, v in moving.most_common()},
                by_biome={k: (biome_stuck[k] / v, v) for k, v in biome_moving.items()},
                longest_streak=longest, survived=env.time)


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    max_time = float(sys.argv[2]) if len(sys.argv) > 2 else 1200.0
    r = measure(seed, max_time, *(sys.argv[3:4]))
    print(f"seed {r['seed']} survived {r['survived']:.0f}s | stuck {r['stuck_fraction']:.1%} of {r['moving_ticks']} moving agent-ticks "
          f"| longest streak {r['longest_streak'][0]} ticks in '{r['longest_streak'][1]}'")
    print("by mode :", {k: f"{f:.1%} of {n}" for k, (f, n) in r["by_mode"].items()})
    print("by biome:", {k: f"{f:.1%} of {n}" for k, (f, n) in r["by_biome"].items()})
