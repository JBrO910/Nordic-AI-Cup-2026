"""Replay a recorded trajectory through the policy and require byte-identical actions.
Record (with the reference policy): python tests/test_policy_equivalence.py record
Check:                               python tests/test_policy_equivalence.py
"""
import os, pickle, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
TRAJ = os.path.join(ROOT, "scratch", "trajectory_seed3_300s.pkl")


def record(seed=3, max_time=300.0):
    import pygame; pygame.init()
    from src.core import SimulationCore
    from src.utils.controllers.hivemind_policy import Hivemind
    sim, hm, steps = SimulationCore(seed=seed), Hivemind(), []
    state = sim.step([])
    while state["num_agents"] > 0 and sim.env.time <= max_time:
        step = {"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]}
        actions = hm.decide(step)
        steps.append((step, [a.dict() for a in actions]))
        state = sim.step([(a.agent_id, a) for a in actions])
    pickle.dump(steps, open(TRAJ, "wb"))
    print(f"recorded {len(steps)} steps")


def test_replay_matches():
    from src.utils.controllers.hivemind_policy import Hivemind
    steps = pickle.load(open(TRAJ, "rb"))
    hm = Hivemind()
    for i, (step, expected) in enumerate(steps):
        got = [a.dict() for a in hm.decide(step)]
        assert got == expected, f"divergence at step {i}: {got[:1]} != {expected[:1]}"
    print(f"ok: {len(steps)} steps identical")


if __name__ == "__main__":
    record() if "record" in sys.argv else test_replay_matches()
