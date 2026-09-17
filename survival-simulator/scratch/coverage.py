"""Map coverage: python scratch/coverage.py <seed> [t=300] [module:Class]
At time t: known trees that match a real tree (within 30 px) / real trees, known landmarks, cells visited, population."""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def measure(seed=3, t_eval=300.0, policy="src.utils.controllers.hivemind_policy:Hivemind"):
    import pygame; pygame.init()
    import importlib
    from src.core import SimulationCore
    mod, name = policy.split(":")
    hm = getattr(importlib.import_module(mod), name)()
    sim = SimulationCore(seed=seed); env = sim.env
    state = sim.step([])
    while state["num_agents"] > 0 and env.time < t_eval:
        acts = hm.decide({"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]})
        state = sim.step([(a.agent_id, a) for a in acts])
    real = [(tr.x, tr.y) for tr in env.trees]
    matched = sum(1 for x, y in real if any(math.hypot(k[0] - x, k[1] - y) < 30 for k in hm.trees))
    return dict(seed=seed, t=env.time, real_trees=len(real), known_matching=matched,
                coverage=matched / max(len(real), 1), landmarks=sum(len(v) for v in hm.landmarks.values()),
                cells=len(hm.cell_seen), pop=state["num_agents"])


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    t = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
    r = measure(seed, t, *(sys.argv[3:4]))
    print(f"seed {r['seed']} t={r['t']:.0f} | tree coverage {r['coverage']:.0%} ({r['known_matching']}/{r['real_trees']}) "
          f"| landmarks {r['landmarks']} | cells visited {r['cells']} | pop {r['pop']}")
