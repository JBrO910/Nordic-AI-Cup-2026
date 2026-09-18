"""Full-game rollouts for the flee net: the served hivemind policy plays a real game while flee_net.act is patched to
sample from the net and log (obs, action); rewards/dones come from agent_status deltas (-energy/100 per flee tick,
-5 when a fleeing agent is eaten). One game ~ one PPO batch (flee ticks are ~14 % of agent-ticks).
python scratch/game_env.py [seed] [max_time]  -> smoke run with buffer sanity checks."""
import sys
sys.path.insert(0, "."); sys.path.insert(0, "scratch")
import numpy as np
import pygame; pygame.init()
from src.core import SimulationCore
from src.utils.controllers import flee_net, hivemind_policy
from ppo import sample_action

DEATH, STARVE = 5.0, 5.0   # death penalty; an agent that vanished with energy < STARVE starved, no penalty


def play_game(W, seed, max_time=3000.0, sample=True, rng_seed=0):
    """Returns dict(obs, acts, rews, dones, survived, kills, steps). Buffers are per agent, concatenated agent by agent."""
    rng = np.random.default_rng(rng_seed)
    buf, called = {}, set()          # aid -> (obs, act, rew, done lists); agents whose net acted this tick

    def act(W_, a, pred, seen):
        obs = flee_net.featurize(a, pred, seen)
        action = sample_action(W_, obs, rng) if sample else flee_net.greedy(W_, obs)
        if sample:
            b = buf.setdefault(a["agent_id"], ([], [], [], []))
            b[0].append(obs); b[1].append(action); called.add(a["agent_id"])
        return flee_net.decode(action, a, pred)

    orig_act, orig_net = flee_net.act, hivemind_policy.FLEE_NET
    flee_net.act, hivemind_policy.FLEE_NET = act, W
    try:
        sim = SimulationCore(seed=seed)
        pol = hivemind_policy.Hivemind()
        state = sim.step([])
        kills = 0
        while state["num_agents"] > 0 and sim.env.time <= max_time:
            prev = {a["agent_id"]: a["energy"] for a in state["observations"]}
            called.clear()
            step = {"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]}
            acts = pol.decide(step)
            prev_score = state["score"]
            state = sim.step([(x.agent_id, x) for x in acts])
            if state["score"] < prev_score:
                kills += 1
            now = {a["agent_id"]: a["energy"] for a in state["observations"]}
            for aid, b in buf.items():
                if len(b[2]) < len(b[0]):           # the step taken this tick gets its reward now
                    if aid in now:
                        b[2].append(-(prev[aid] - now[aid]) / 100); b[3].append(False)
                    else:                            # gone: eaten (penalty) or starved / aged out (no penalty)
                        b[2].append(-DEATH if prev[aid] >= STARVE else 0.0); b[3].append(True)
                elif b[3] and not b[3][-1] and aid not in called:   # flee run ended: the net was not asked this tick
                    b[3][-1] = True
        for b in buf.values():          # game over: close whatever is still open
            if b[3]:
                b[3][-1] = True
    finally:
        flee_net.act, hivemind_policy.FLEE_NET = orig_act, orig_net
    order = sorted(buf)
    obs = np.array([o for aid in order for o in buf[aid][0]], np.float32).reshape(-1, flee_net.OBS_DIM)
    acts = np.array([x for aid in order for x in buf[aid][1]], np.int64).reshape(-1, len(flee_net.HEADS))
    rews = np.array([x for aid in order for x in buf[aid][2]], np.float32)
    dones = np.array([x for aid in order for x in buf[aid][3]], bool)
    return dict(obs=obs, acts=acts, rews=rews, dones=dones, survived=sim.env.time, kills=kills, steps=len(obs))


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    mt = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    r = play_game(flee_net.load(), seed, mt, rng_seed=seed)
    o, a, rw, d = r["obs"], r["acts"], r["rews"], r["dones"]
    assert len(o) == len(a) == len(rw) == len(d), (len(o), len(a), len(rw), len(d))
    assert len(d) == 0 or d[-1], "last step must close an episode"
    eps, deaths = int(d.sum()), int((rw <= -DEATH).sum())
    print(f"seed {seed} t={r['survived']:.0f} flee steps {r['steps']} episodes {eps} deaths {deaths} kills {r['kills']} "
          f"mean ep reward {rw.sum() / max(eps, 1):.3f} mean ep len {len(o) / max(eps, 1):.1f}")
