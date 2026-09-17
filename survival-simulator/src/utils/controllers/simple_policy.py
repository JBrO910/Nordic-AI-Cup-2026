"""Version-3 local policy (reconstruction). Per-agent dead-reckoned frame, local tree memory, no shared map.
Priority: threat > eat visible fruit > reproduce > camp at a known tree > explore > scan."""
import math
import random
from src.utils.DTOs import ActionRequest

CHARGE_DIST, CHARGE_RELEASE = 92, 110   # sprint when a predator that sees us is inside 92 px, until it is past 110
FLEE_MEMORY = 20
CAMP_R = 12
TREE_TTL, NO_FRUIT_GIVEUP, REVISIT, FRUITING_TTL = 600, 200, 600, 400
POP_CAP = [(0, 12), (600, 12), (1800, 5)]
RESERVE = [(0, 150), (1800, 80)]
DUMP_OVERSHOOT = 4
SCAN_EVERY, SCAN_EVERY_ALERT = [(0, 80), (1500, 30)], 20
OLD_AGE, OLD_DUMP_ENERGY = 55, 250
WALL_TURN_DIST = 45
BIOME_PENALTY = {"swamp": 0.5, "desert": 0.8, "river": 0.3}


def interp(t, pts):
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return pts[-1][1]


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def move_cost(a, dist):
    """Mirror environment.update_entity_position energy accounting. Returns (cost, capped_dist)."""
    dist = min(max(dist, 0.0), a["sprint_speed"])
    if a["energy"] < a["max_energy"] / 5 and dist > a["speed"]:
        dist = a["speed"]
    if dist <= a["speed"]:
        return dist * 0.05, dist
    return a["speed"] * 0.05 + (dist - a["speed"]) * 0.5, dist


def fitness(a):
    return (2 * a["speed"] / 20 + 2 * a["hearing_radius"] / 100 + a["vision_range"] / 400
            + a["vision_angle"] / (math.pi / 2) + a["max_energy"] / 1000)


class Hivemind:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.reset()

    def reset(self):
        self.mem, self.tick, self.last_time, self.last_predator_tick = {}, 0, -1.0, -10**9

    def _mem(self, aid):
        m = self.mem.get(aid)
        if m is None:
            m = self.mem[aid] = dict(x=0.0, y=0.0, h=0.0, trees={}, target=None, camp_fruit_tick=self.tick,
                                     pred=None, pred_tick=-10**9, scan_left=5, next_scan=self.rng.randint(20, 60),
                                     explore_dir=self.rng.uniform(-math.pi, math.pi), prev_energy=None,
                                     expected_drop=0.0, aging=False, wall_cooldown=0, sprinting=False, mode="")
        return m

    def decide(self, step):
        t = step["sim_time"]
        if t < self.last_time:
            self.reset()
        self.last_time, self.tick = t, self.tick + 1
        agents = step["agent_status"]
        alive = {a["agent_id"] for a in agents}
        for aid in list(self.mem):
            if aid not in alive:
                del self.mem[aid]
        spawners = self._choose_spawners(agents, t)
        actions = []
        for a in agents:
            m = self._mem(a["agent_id"])
            self._detect_aging(a, m)
            dist, direction, turn = self._plan(a, m, t)
            spawn = a["agent_id"] in spawners and a["energy"] > 100 and not m["mode"].startswith("flee")
            if spawn:
                dist = 0.0
            cost, real = move_cost(a, dist)
            m["expected_drop"] = 0.1 + cost + min(math.pi, abs(turn)) / (2 * math.pi) + (100 if spawn else 0)
            real *= BIOME_PENALTY.get(a["biome"], 1.0)
            m["x"] += real * math.cos(m["h"] + direction)
            m["y"] += real * math.sin(m["h"] + direction)
            m["h"] += turn
            m["prev_energy"] = a["energy"]
            actions.append(ActionRequest(agent_id=a["agent_id"], move_distance=float(dist),
                                         move_direction=float(direction), turn_angle=float(turn), spawn_agent=spawn))
        return actions

    def _choose_spawners(self, agents, t):
        n, cap, reserve = len(agents), interp(t, POP_CAP), interp(t, RESERVE)
        chosen, dumpers = set(), []
        for a in agents:
            m = self._mem(a["agent_id"])
            floor = 0.2 * a["max_energy"] + 20
            old = a["age"] > OLD_AGE and a["energy"] > max(OLD_DUMP_ENERGY, 100 + floor)
            if (m["aging"] and a["energy"] > 100) or old:
                dumpers.append(a)  # dying anyway: convert energy to children
        dumpers.sort(key=lambda a: a["energy"], reverse=True)
        chosen.update(a["agent_id"] for a in dumpers[:max(0, int(cap) + DUMP_OVERSHOOT - n)])
        able = [a for a in agents if a["agent_id"] not in chosen
                and a["energy"] > 100 + max(reserve, 0.2 * a["max_energy"] + 20)]
        able.sort(key=fitness, reverse=True)
        room = int(cap) - n - len(chosen)
        if n == 1 and able:
            room = max(room, 1)
        chosen.update(a["agent_id"] for a in able[:max(room, 0)])
        return chosen

    def _detect_aging(self, a, m):
        if m["prev_energy"] is not None and not m["aging"] and a["age"] > 60 \
                and m["prev_energy"] - a["energy"] > m["expected_drop"] + 0.3:
            m["aging"] = True

    def _plan(self, a, m, t):
        obs = a["observations"]
        preds = [o for o in obs if o["type"] == "Predator"]
        fruits = [o for o in obs if o["type"] == "Fruit"]
        trees = [o for o in obs if o["type"] == "Tree"]
        edges = [o["coords"] for o in obs if o["type"] == "Edge"]
        speed, sprint = a["speed"], a["sprint_speed"]
        can_sprint = a["energy"] > 0.2 * a["max_energy"] + 5

        # tree memory in own frame: merge re-sightings, remember fruit near a tree, drop trees we stand on but don't hear
        for o in trees:
            wx, wy = self._world(m, o["distance"], o["angle"])
            key = next((k for k, v in m["trees"].items() if math.hypot(v[0] - wx, v[1] - wy) < 60), None)
            rec = m["trees"].get(key) if key else None
            if rec:  # trees are static: pull our estimate back onto the tree frame
                m["x"] += (rec[0] - wx) * 0.5
                m["y"] += (rec[1] - wy) * 0.5
                wx, wy = rec[0], rec[1]
            fruit_near = any(self._dist(o, f) < 80 for f in fruits)
            m["trees"][key or (round(wx / 40), round(wy / 40))] = (
                wx, wy, self.tick, rec[3] if rec else -10**9, self.tick if fruit_near else (rec[4] if rec else -10**9))
        for key in [k for k, v in m["trees"].items() if self.tick - v[2] > TREE_TTL
                    or (self.tick - v[2] > 2 and math.hypot(v[0] - m["x"], v[1] - m["y"]) < a["hearing_radius"] - 10)]:
            del m["trees"][key]

        # 1. threat: face it, back away; sprint only inside the charge zone
        if preds:
            p = min(preds, key=lambda o: o["distance"])
            m["pred"], m["pred_tick"], self.last_predator_tick = self._world(m, p["distance"], p["angle"]), self.tick, self.tick
            fx = sum(-math.cos(o["angle"]) / max(o["distance"], 1.0) for o in preds)
            fy = sum(-math.sin(o["angle"]) / max(o["distance"], 1.0) for o in preds)
            seen_by_it = p["distance"] < 60 or abs(p["rel_dir"]) < math.pi / 6 + 0.15
            m["sprinting"] = seen_by_it and p["distance"] < (CHARGE_RELEASE if m["sprinting"] else CHARGE_DIST) and can_sprint
            m["scan_left"], m["mode"] = 0, "flee"
            return (sprint if m["sprinting"] else speed), math.atan2(fy, fx), p["angle"]
        if m["pred"] and self.tick - m["pred_tick"] < FLEE_MEMORY:
            m["mode"] = "flee_mem"
            return speed, wrap(self._rel_angle(m, m["pred"]) + math.pi), 0.0

        # 2. eat (ignore fruit we only hear through a wall); dying agents don't walk
        fruits = [f for f in fruits if not self._blocked(f["distance"], f["angle"], edges)]
        if m["aging"] and not (fruits and min(f["distance"] for f in fruits) < 60):
            m["mode"] = "aging"
            return 0.0, 0.0, 0.0
        if fruits:
            f = min(fruits, key=lambda o: o["distance"])
            m["camp_fruit_tick"], m["scan_left"], m["mode"] = self.tick, 0, "eat"
            return min(speed, f["distance"] + 2), f["angle"], f["angle"] if f["distance"] > 60 and abs(f["angle"]) > 0.6 else 0.0

        # 3. scan
        if m["scan_left"] > 0:
            m["scan_left"] -= 1
            m["mode"] = "scan"
            return 0.0, 0.0, a["vision_angle"]
        m["next_scan"] -= 1
        if m["next_scan"] <= 0:
            alert = self.tick - self.last_predator_tick < 100
            m["next_scan"] = SCAN_EVERY_ALERT if alert else int(interp(t, SCAN_EVERY))
            m["scan_left"], m["mode"] = math.ceil(2 * math.pi / a["vision_angle"]) - 1, "scan"
            return 0.0, 0.0, a["vision_angle"]

        # 4. camp at a known tree (fruiting ones first), rotate when it stops giving
        if m["target"] not in m["trees"]:
            m["target"] = None
        if m["target"] is None:
            cands = [(self.tick - v[4] > FRUITING_TTL, math.hypot(v[0] - m["x"], v[1] - m["y"]), k)
                     for k, v in m["trees"].items() if self.tick - v[3] > REVISIT]
            if cands:
                m["target"], m["camp_fruit_tick"] = min(cands)[2], self.tick
        if m["target"] is not None:
            tx, ty, seen, visit, fr = m["trees"][m["target"]]
            d = math.hypot(tx - m["x"], ty - m["y"])
            if d > CAMP_R:
                m["mode"] = "totree"
                return min(speed, d - CAMP_R), self._rel_angle(m, (tx, ty)), 0.0
            if self.tick - m["camp_fruit_tick"] > NO_FRUIT_GIVEUP:
                m["trees"][m["target"]] = (tx, ty, seen, self.tick, fr)
                m["target"] = None
            m["mode"] = "camp"
            return 0.0, 0.0, 0.0

        # 5. explore: straight line, bounce off walls
        if m["wall_cooldown"] > 0:
            m["wall_cooldown"] -= 1
        if self._nearest_edge_dist(edges) < WALL_TURN_DIST and m["wall_cooldown"] == 0:
            m["explore_dir"] += self.rng.choice((-1, 1)) * self.rng.uniform(math.pi / 2, math.pi)
            m["wall_cooldown"] = 15
        rel = wrap(m["explore_dir"] - m["h"])
        m["mode"] = "explore"
        return speed, rel, rel if abs(rel) > 0.3 else 0.0

    @staticmethod
    def _world(m, d, ang):
        return (m["x"] + d * math.cos(m["h"] + ang), m["y"] + d * math.sin(m["h"] + ang))

    @staticmethod
    def _rel_angle(m, p):
        return wrap(math.atan2(p[1] - m["y"], p[0] - m["x"]) - m["h"])

    @staticmethod
    def _dist(o1, o2):
        return math.hypot(o1["distance"] * math.cos(o1["angle"]) - o2["distance"] * math.cos(o2["angle"]),
                          o1["distance"] * math.sin(o1["angle"]) - o2["distance"] * math.sin(o2["angle"]))

    @staticmethod
    def _blocked(d, ang, edges):
        px, py = d * math.cos(ang), d * math.sin(ang)
        for (x1, y1), (x2, y2) in edges:
            ex, ey = x2 - x1, y2 - y1
            den = px * ey - py * ex
            if abs(den) < 1e-9:
                continue
            if 0 <= (x1 * ey - y1 * ex) / den <= 1 and 0 <= (x1 * py - y1 * px) / den <= 1:
                return True
        return False

    @staticmethod
    def _nearest_edge_dist(edges):
        best = float("inf")
        for (x1, y1), (x2, y2) in edges:
            if x1 < 0 and x2 < 0:
                continue
            dx, dy = x2 - x1, y2 - y1
            l2 = dx * dx + dy * dy
            u = 0.0 if l2 == 0 else max(0.0, min(1.0, -(x1 * dx + y1 * dy) / l2))
            best = min(best, math.hypot(x1 + u * dx, y1 + u * dy))
        return best
