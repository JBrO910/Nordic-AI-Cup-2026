"""Fruit economy: python scratch/economy.py <seed> [max_time=1200] [module:Class] -> eaten vs rotted fruit energy."""
import importlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
seed = int(sys.argv[1]); max_time = float(sys.argv[2]) if len(sys.argv) > 2 else 1200.0
policy = sys.argv[3] if len(sys.argv) > 3 else "src.utils.controllers.hivemind_policy:Hivemind"
import pygame; pygame.init()
from src.core import SimulationCore
mod, name = policy.split(":"); hm = getattr(importlib.import_module(mod), name)()
sim = SimulationCore(seed=seed); env = sim.env
eaten = rotted = 0.0; orig = env.remove_fruit
def remove_fruit(f):
    global eaten, rotted
    if f.age > 100: rotted += f.energy
    else: eaten += f.energy
    orig(f)
env.remove_fruit = remove_fruit
state = sim.step([])
while state["num_agents"] > 0 and env.time <= max_time:
    acts = hm.decide({"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]})
    state = sim.step([(a.agent_id, a) for a in acts])
print(f"seed {seed} {policy.split('.')[-1]} survived {env.time:.0f}s | eaten {eaten:.0f} rotted {rotted:.0f} | capture {eaten/max(eaten+rotted,1):.1%}")
