import sys, math, pygame; pygame.init()
sys.path.insert(0, ".")
from src.core import SimulationCore
from src.elements.predator import Predator
sim = SimulationCore(seed=1, starting_trees=0); env = sim.env
for a in list(env.agents)[1:]: env.kill_agent(a)
ag = env.agents[0]; ag.x, ag.y, ag.direction = 800, 600, 0.0; env._update_agent_grid()
p = Predator(800 + 230, 600, rng=env.rng); p.energy = 100; p.resting = False; p.direction = math.pi
env.predators.append(p); env._update_predator_grid()
la = env._get_local_agents(p); print("local agents:", len(la), "chunk pred", env.to_chunk(p.x, p.y), "chunk agent", env.to_chunk(ag.x, ag.y))
obs = p.observe(agents=la, edges=env._get_local_edges(p))
print("pred obs:", [o for o in obs if o["type"] == "Agent"])
print("signals:", p.step(obs))
