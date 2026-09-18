"""Late game: where do agents spend ticks, and how far is uneaten fruit from them / from the shared map's knowledge?
python scratch/latefruit.py <seed> [t0=700]"""
import sys, math, collections; sys.path.insert(0, ".")
import pygame; pygame.init()
from src.core import SimulationCore
from src.utils.controllers.hivemind_policy import Hivemind
seed = int(sys.argv[1]); t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 700.0
sim = SimulationCore(seed=seed); env = sim.env; pol = Hivemind()
modes = collections.Counter(); dist_near = []; dist_known = []; known_frac = []; sprint_ok = []; n = 0
state = sim.step([])
while state["num_agents"] > 0 and env.time <= 3000:
    step = {"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]}
    acts = pol.decide(step)
    if env.time >= t0:
        modes.update(m["mode"] for m in pol.mem.values())
        if int(round(env.time * 10)) % 50 == 0 and env.fruits:
            for f in env.fruits:
                dist_near.append(min(math.hypot(a.x - f.x, a.y - f.y) for a in env.agents))
            known = getattr(pol, "fruits", None)
            if known:
                pts = [(k[0], k[1]) if isinstance(k, (tuple, list)) else (k["x"], k["y"]) if isinstance(k, dict) else None for k in (known.values() if isinstance(known, dict) else known)]
                pts = [p for p in pts if p]
                known_frac.append(sum(1 for f in env.fruits if any(math.hypot(p[0]-f.x, p[1]-f.y) < 30 for p in pts)) / len(env.fruits))
            sprint_ok.append(sum(1 for a in env.agents if a.energy > 0.2 * a.max_energy + 5) / len(env.agents))
    state = sim.step([(a.agent_id, a) for a in acts])
tot = sum(modes.values())
print(f"seed {seed} died t={env.time:.0f}; ticks from t>={t0:.0f}:")
print("  modes:", ", ".join(f"{k} {v/tot:.0%}" for k, v in modes.most_common(8)))
dn = sorted(dist_near); 
print(f"  fruit->nearest agent: median {dn[len(dn)//2]:.0f} px, 25% {dn[len(dn)//4]:.0f}, 75% {dn[3*len(dn)//4]:.0f}, share within 150 px {sum(d<150 for d in dn)/len(dn):.0%}")
if known_frac: print(f"  share of map fruit known to the hivemind: {sum(known_frac)/len(known_frac):.0%}")
print(f"  agents able to sprint: {sum(sprint_ok)/len(sprint_ok):.0%}")
