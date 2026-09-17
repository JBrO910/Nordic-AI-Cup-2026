"""Energy cost by behaviour mode: python scratch/costmode.py <seed> <max_time> -> per agent-second by mode."""
import collections, importlib, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
seed = int(sys.argv[1]); max_time = float(sys.argv[2])
import pygame; pygame.init()
from src.core import SimulationCore
from src.utils.controllers.hivemind_policy import Hivemind, move_cost
sim = SimulationCore(seed=seed); hm = Hivemind(); state = sim.step([])
cost = collections.Counter(); ticks = collections.Counter(); agent_ticks = 0
while state["num_agents"] > 0 and sim.env.time <= max_time:
    obs = {o["agent_id"]: o for o in state["observations"]}
    acts = hm.decide({"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]})
    for act in acts:
        mode = hm.mem[act.agent_id]["mode"]; c, _ = move_cost(obs[act.agent_id], act.move_distance)
        cost[mode] += c + min(math.pi, abs(act.turn_angle)) / (2 * math.pi); ticks[mode] += 1; agent_ticks += 1
    state = sim.step([(a.agent_id, a) for a in acts])
total = sum(cost.values()) / agent_ticks * 10
print(f"seed {seed} t<={max_time:.0f}: movement+turn {total:.2f} energy/s per agent (living is 1.00) | " +
      " ".join(f"{k} {v/agent_ticks*10:.2f}" for k, v in cost.most_common()))
