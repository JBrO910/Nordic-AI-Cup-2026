"""Kills by biome vs agent-ticks by biome: python scratch/biome_kills.py <seed> [tmax] [module:Class]"""
import sys, collections, importlib; sys.path.insert(0, ".")
import pygame; pygame.init()
from src.core import SimulationCore
seed = int(sys.argv[1]); tmax = float(sys.argv[2]) if len(sys.argv) > 2 else 1500.0
spec = sys.argv[3] if len(sys.argv) > 3 else "src.utils.controllers.hivemind_policy:Hivemind"
Hivemind = getattr(importlib.import_module(spec.split(":")[0]), spec.split(":")[1])
sim = SimulationCore(seed=seed); env = sim.env; pol = Hivemind(); state = sim.step([])
ticks, kills = collections.Counter(), collections.Counter(); last = {}
while state["num_agents"] > 0 and env.time <= tmax:
    for o in state["observations"]:
        ticks[o["biome"]] += 1; last[o["agent_id"]] = o["biome"]
    acts = pol.decide({"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]})
    s0 = state["score"]; ids = set(last)
    state = sim.step([(a.agent_id, a) for a in acts])
    if state["score"] < s0:
        for aid in ids - {o["agent_id"] for o in state["observations"]}:
            kills[last[aid]] += 1
    last = {aid: b for aid, b in last.items() if aid in {o["agent_id"] for o in state["observations"]}}
T, K = sum(ticks.values()), sum(kills.values())
print(f"seed {seed} died {env.time:.0f}; kills {K}")
for b in sorted(ticks, key=lambda b: -ticks[b]):
    print(f"  {b:10s} time {ticks[b]/T:5.1%}  kills {kills[b]/max(K,1):5.1%}  ratio {(kills[b]/max(K,1))/(ticks[b]/T):.2f}")
