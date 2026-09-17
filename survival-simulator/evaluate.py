"""Headless multi-seed evaluator. Usage: python evaluate.py --seeds 1 2 3 [--policy dummy|hivemind] [--max-time 3000]"""
import argparse, random, sys, time
from multiprocessing import Pool


def run_seed(args):
    seed, policy_name, max_time = args
    import pygame; pygame.init()
    from src.core import SimulationCore
    sim = SimulationCore(seed=seed)

    if policy_name == "dummy":
        from src.utils.controllers.dummy_agent_policy import action_decision
        rng = random.Random(seed)
        def decide(state):
            return [(o["agent_id"], action_decision(o, rng)) for o in state["observations"]]
    else:
        from src.utils.controllers.hivemind_policy import Hivemind
        hm = Hivemind()
        def decide(state):
            step = {"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]}
            return [(a.agent_id, a) for a in hm.decide(step)]

    t0 = time.time()
    actions, peak, eaten = [], 0, 0.0
    state = sim.step(actions)
    while state["num_agents"] > 0 and sim.env.time <= max_time:
        actions = decide(state)
        prev_score = state["score"]
        state = sim.step(actions)
        peak = max(peak, state["num_agents"])
        if state["score"] < prev_score:
            eaten += prev_score - state["score"]
    return dict(seed=seed, score=state["score"], survived=sim.env.time, peak_pop=peak,
                predators=len(sim.env.predators), eaten_penalty=eaten, wall=time.time() - t0)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    p.add_argument("--policy", default="hivemind")
    p.add_argument("--max-time", type=float, default=3000)
    p.add_argument("--workers", type=int, default=None)
    a = p.parse_args()
    with Pool(a.workers) as pool:
        results = pool.map(run_seed, [(s, a.policy, a.max_time) for s in a.seeds])
    for r in results:
        print(f"seed {r['seed']:>6} | score {r['score']:8.2f} | survived {r['survived']:7.1f}s | peak pop {r['peak_pop']:3d} | preds {r['predators']:2d} | eaten -{r['eaten_penalty']:.2f} | {r['wall']:.0f}s")
    n = len(results)
    print(f"MEAN score {sum(r['score'] for r in results)/n:.2f} | survived {sum(r['survived'] for r in results)/n:.1f}s | min survived {min(r['survived'] for r in results):.1f}s")
