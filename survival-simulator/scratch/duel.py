"""Controlled duel: one agent vs one awake predator. Reports survival, ticks, energy spent."""
import sys, math, pygame, random; pygame.init()
sys.path.insert(0, ".")
from src.core import SimulationCore
from src.utils.controllers.hivemind_policy import Hivemind

def duel(dist, rel_angle, pred_energy=100, agent_energy=300, ticks=400, seed=1, verbose=False):
    sim = SimulationCore(seed=seed, starting_trees=0, starting_fruits=0)
    env = sim.env
    for a in list(env.agents)[1:]: env.kill_agent(a)
    env.spawn_predator = lambda *a, **k: None   # no random predators
    env.obstacles = env.obstacles[:4]           # boundaries only
    env.edges = set()
    for o in env.obstacles:
        env.edges.update([((o.x, o.y), (o.x + o.width, o.y)), ((o.x + o.width, o.y), (o.x + o.width, o.y + o.height)),
                          ((o.x, o.y + o.height), (o.x + o.width, o.y + o.height)), ((o.x, o.y), (o.x, o.y + o.height))])
    env._update_obstacle_grid(); env._update_edge_grid()
    env.fruits = []; env.fruits_dict = {}; env._update_fruit_grid(); env.trees = []; env._update_tree_grid()
    env.spawn_fruit = lambda *a, **k: None; env.spawn_tree = lambda *a, **k: None
    ag = env.agents[0]; ag.x, ag.y, ag.direction = 800, 600, 0.0; ag.energy = agent_energy
    env._update_agent_grid()
    px, py = ag.x + dist * math.cos(rel_angle), ag.y + dist * math.sin(rel_angle)
    from src.elements.predator import Predator
    p = Predator(px, py, rng=env.rng); p.energy = pred_energy; p.resting = False
    p.direction = math.atan2(ag.y - py, ag.x - px)   # facing the agent
    env.predators.append(p); env._update_predator_grid()
    hm = Hivemind(); state = sim.step([]); e0 = ag.energy; log = []
    for t in range(ticks):
        acts = hm.decide({"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]})
        m = hm.mem.get(ag.agent_id, {})
        log.append((t, m.get("mode"), round(math.hypot(p.x-ag.x, p.y-ag.y)), round(ag.energy), round(p.energy), p.resting))
        for a in acts: a.spawn_agent = False
        state = sim.step([(a.agent_id, a) for a in acts])
        if not env.agents: return dict(dead=True, tick=t, log=log)
        if p.resting and math.hypot(p.x-ag.x, p.y-ag.y) > 100: return dict(dead=False, tick=t, spent=round(e0 - ag.energy), log=log)
    return dict(dead=False, tick=ticks, spent=round(e0 - ag.energy), log=log)

if __name__ == "__main__":
    for dist in (230, 150, 80, 45):
        for ang in (0.0, 1.5, 3.0):
            r = duel(dist, ang)
            print(f"dist {dist:3d} angle {ang:.1f}: {'DEAD at tick '+str(r['tick']) if r['dead'] else 'survived, spent '+str(r['spent'])+' energy, '+str(r['tick'])+' ticks'}")
    r = duel(230, 0.0)
    for row in r["log"][:60:3]: print(row)

def trace(dist, ang, agent_energy=300):
    import src.utils.controllers.hivemind_policy as hp
    sim = SimulationCore(seed=1, starting_trees=0); env = sim.env
    for a in list(env.agents)[1:]: env.kill_agent(a)
    env.spawn_predator = lambda *a, **k: None
    env.obstacles = env.obstacles[:4]; env.edges = set()
    for o in env.obstacles:
        env.edges.update([((o.x, o.y), (o.x + o.width, o.y)), ((o.x + o.width, o.y), (o.x + o.width, o.y + o.height)),
                          ((o.x, o.y + o.height), (o.x + o.width, o.y + o.height)), ((o.x, o.y), (o.x, o.y + o.height))])
    env._update_obstacle_grid(); env._update_edge_grid()
    env.fruits = []; env.fruits_dict = {}; env._update_fruit_grid(); env.trees = []; env._update_tree_grid()
    env.spawn_fruit = lambda *a, **k: None; env.spawn_tree = lambda *a, **k: None
    ag = env.agents[0]; ag.x, ag.y, ag.direction = 800, 600, 0.0; ag.energy = agent_energy; env._update_agent_grid()
    from src.elements.predator import Predator
    p = Predator(ag.x + dist * math.cos(ang), ag.y + dist * math.sin(ang), rng=env.rng); p.energy = 100; p.resting = False
    p.direction = math.atan2(ag.y - p.y, ag.x - p.x); env.predators.append(p); env._update_predator_grid()
    hm = Hivemind(); hm._mem(ag.agent_id)["scan_left"] = 0
    state = sim.step([])
    for t in range(40):
        o = state["observations"][0]; preds = [x for x in o["observations"] if x["type"] == "Predator"]
        acts = hm.decide({"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]})
        a = acts[0]; a.spawn_agent = False; m = hm.mem[ag.agent_id]
        pobs = f"seen d={preds[0]['distance']:.0f} ang={preds[0]['angle']:.2f} rel_dir={preds[0]['rel_dir']:.2f}" if preds else "not seen"
        print(f"t={t:2d} biome={env.biome_map[int(ag.x), int(ag.y)].type[:5]:5s}/{env.biome_map[int(p.x), int(p.y)].type[:5]:5s} true d={math.hypot(p.x-ag.x, p.y-ag.y):5.1f} agE={ag.energy:5.0f} pE={p.energy:5.1f} | {pobs} | {m['mode']:8s} move={a.move_distance:4.1f} dir={a.move_direction:5.2f} turn={a.turn_angle:5.2f} | agent hdg={ag.direction:5.2f} pred hdg={p.direction:5.2f}")
        state = sim.step([(a.agent_id, a) for a in acts])
        if not env.agents: print("DEAD"); break

if __name__ == "__main__" and len(sys.argv) > 1:
    trace(float(sys.argv[1]), float(sys.argv[2]))
