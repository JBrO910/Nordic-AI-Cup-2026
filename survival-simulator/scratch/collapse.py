"""Why does the colony die? python scratch/collapse.py <seed> -> per-100 s window: pop, trees, fruit on map, predators,
deaths split into eaten / starved-young / starved-old (age > max_age), births, mean energy fill."""
import sys, collections; sys.path.insert(0, ".")
import pygame; pygame.init()
from src.core import SimulationCore
from src.utils.controllers.hivemind_policy import Hivemind
seed = int(sys.argv[1])
sim = SimulationCore(seed=seed); env = sim.env; pol = Hivemind()
W = collections.OrderedDict()
def w(t):
    k = int(t // 100) * 100
    return W.setdefault(k, dict(eaten=0, starved=0, aged=0, births=0, fill=[], pop=[], trees=[], fruit=[], preds=[]))
state = sim.step([])
seen = {a.agent_id: a for a in env.agents}
while state["num_agents"] > 0 and env.time <= 3000:
    t = env.time; x = w(t)
    if int(round(t * 10)) % 100 == 0:
        x["fill"].append(sum(a.energy / a.max_energy for a in env.agents) / len(env.agents))
        x["pop"].append(len(env.agents)); x["trees"].append(len(env.trees)); x["fruit"].append(len(env.fruits)); x["preds"].append(len(env.predators))
    step = {"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]}
    acts = pol.decide(step)
    s0 = state["score"]
    state = sim.step([(a.agent_id, a) for a in acts])
    now = {a.agent_id: a for a in env.agents}
    eaten_tick = state["score"] < s0
    for aid, a in seen.items():
        if aid not in now:
            if eaten_tick: x["eaten"] += 1
            elif a.age > a.max_age: x["aged"] += 1
            else: x["starved"] += 1
    x["births"] += sum(1 for aid in now if aid not in seen)
    seen = now
print(f"seed {seed} died at t={env.time:.0f}")
print("  t     pop trees fruit preds fill | eaten starved aged births")
for k, x in W.items():
    m = lambda v: sum(v) / max(1, len(v))
    print(f"{k:5d} {m(x['pop']):5.1f} {m(x['trees']):5.1f} {m(x['fruit']):5.1f} {m(x['preds']):5.1f} {m(x['fill']):4.0%} | {x['eaten']:5d} {x['starved']:7d} {x['aged']:4d} {x['births']:6d}")
