"""Post-mortem for eaten agents: how were they caught?"""
import sys, math, pygame, collections; pygame.init()
sys.path.insert(0, ".")
from src.core import SimulationCore
from src.utils.controllers.hivemind_policy import Hivemind
seed = int(sys.argv[1]); tmax = float(sys.argv[2])
sim = SimulationCore(seed=seed); hm = Hivemind(); env = sim.env
state = sim.step([]); hist = collections.defaultdict(list); prev_score = 0; rows = []
while state["num_agents"] > 0 and env.time <= tmax:
    obs = {o["agent_id"]: o for o in state["observations"]}
    acts = hm.decide({"sim_time": state["sim_time"], "score": state["score"], "agent_status": state["observations"]})
    for a in env.agents:
        m = hm.mem[a.agent_id]; o = obs[a.agent_id]
        preds = [p for p in o["observations"] if p["type"] == "Predator"]
        truep = min((math.hypot(p.x - a.x, p.y - a.y) for p in env.predators if not p.resting), default=9999)
        hist[a.agent_id].append((m["mode"], round(a.energy), len(preds), round(min((p["distance"] for p in preds), default=-1)), round(truep)))
    ids = {a.agent_id for a in env.agents}
    state = sim.step([(a.agent_id, a) for a in acts])
    if state["score"] < prev_score:
        for d in ids - {a.agent_id for a in env.agents}:
            h = hist[d]
            first = next((i for i, x in enumerate(h) if x[2] > 0), None)   # first tick a predator was observed
            seen_at = h[first] if first is not None else None
            approach = next((i for i, x in enumerate(h) if x[4] < 250), None)  # true predator within 250
            flee_ticks = sum(1 for x in h[-200:] if x[0].startswith("flee"))
            rows.append(dict(t=round(env.time), id=d, energy_at_death=h[-1][1], mode_before=h[first-1][0] if first else h[-1][0],
                             first_seen_dist=seen_at[3] if seen_at else None, energy_when_seen=seen_at[1] if seen_at else None,
                             ticks_unseen_within_250=(first - approach) if (first is not None and approach is not None) else None,
                             flee_ticks=flee_ticks, npreds=max(x[2] for x in h[-100:])))
    prev_score = state["score"]
print(f"kills: {len(rows)} by t={env.time:.0f}")
c = collections.Counter()
for r in rows:
    print(r)
    c["never_saw_it"] += r["first_seen_dist"] is None
    c["seen_first_at_<60"] += (r["first_seen_dist"] or 999) < 60
    c["could_not_sprint(<105)"] += (r["energy_when_seen"] or 999) < 105
    c["was_sitting/scanning"] += r["mode_before"] in ("sit", "scan")
print(dict(c))
