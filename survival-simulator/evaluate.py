"""Headless multi-seed evaluator — the only accepted measure of progress.

Usage: python evaluate.py [--seeds 1 2 ...] [--policy module:Class] [--repeat N] [--max-time 3000] [--workers N]
`--policy` names a module and either a class with decide(step)->list[ActionRequest] (e.g. ...hivemind_policy:Hivemind)
or the dummy function ...dummy_agent_policy:dummy.
"""
import argparse, importlib, random, time
from multiprocessing import Pool

DEFAULT_SEEDS = list(range(1, 13))
DEFAULT_POLICY = "src.utils.controllers.hivemind_policy:Hivemind"


def load_policy(spec, seed):
    """Return decide(state) -> [(agent_id, ActionRequest)] for a 'module:Name' spec."""
    mod_name, name = spec.split(":")
    mod = importlib.import_module(mod_name)
    if name == "dummy":
        rng = random.Random(seed)
        return lambda state: [(o["agent_id"], mod.action_decision(o, rng)) for o in state["observations"]]
    policy = getattr(mod, name)()
    def decide(state):
        step = {"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]}
        return [(a.agent_id, a) for a in policy.decide(step)]
    return decide


def run_seed(args):
    seed, policy_spec, max_time = args
    import pygame; pygame.init()
    from src.core import SimulationCore
    sim = SimulationCore(seed=seed)
    decide = load_policy(policy_spec, seed)
    t0 = time.time()
    peak, eaten, kills = 0, 0.0, 0
    state = sim.step([])
    while state["num_agents"] > 0 and sim.env.time <= max_time:
        actions = decide(state)
        prev_score, prev_n = state["score"], state["num_agents"]
        state = sim.step(actions)
        peak = max(peak, state["num_agents"])
        if state["score"] < prev_score:  # only predator kills lower the score
            eaten += prev_score - state["score"]
            kills += max(1, prev_n - state["num_agents"])
    return dict(seed=seed, score=state["score"], survived=sim.env.time, peak_pop=peak,
                predators=len(sim.env.predators), eaten_penalty=eaten, kills=kills, wall=time.time() - t0)


def jobs(seeds, policy_spec, max_time, repeat=1):
    return [(s, policy_spec, max_time) for _ in range(repeat) for s in seeds]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    p.add_argument("--policy", default=DEFAULT_POLICY)
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--max-time", type=float, default=3000)
    p.add_argument("--workers", type=int, default=None)
    a = p.parse_args()
    with Pool(a.workers) as pool:
        results = pool.map(run_seed, jobs(a.seeds, a.policy, a.max_time, a.repeat))
    for r in results:
        print(f"seed {r['seed']:>3} | score {r['score']:8.2f} | survived {r['survived']:7.1f}s | peak pop {r['peak_pop']:3d} "
              f"| preds {r['predators']:2d} | kills {r['kills']:3d} (-{r['eaten_penalty']:.1f}) | {r['wall']:.0f}s")
    n = len(results)
    print(f"POLICY {a.policy} | MEAN score {sum(r['score'] for r in results)/n:.1f} | MEAN survived "
          f"{sum(r['survived'] for r in results)/n:.1f}s | MIN survived {min(r['survived'] for r in results):.1f}s "
          f"| kills/run {sum(r['kills'] for r in results)/n:.1f}")
