"""Heuristic hivemind controller.

Every agent is localized in absolute map coordinates: a sighting of a boundary wall edge (the only
edges >= 1000 px long) gives exact heading + position; localized agents localize the agents they see.
All sightings feed one shared world map (fruits, trees, predators) that every agent plans against.

Per agent priority: threat > visible fruit > assigned world fruit > fruiting tree > sit & scan (hop if starving).
"""
import math
import random
from src.utils.DTOs import ActionRequest

W, H, WALL = 1600, 1200, 30

# ---- tunables ----
CHARGE_DIST = 92         # predator closer than this charges -> sprint away
CHARGE_RELEASE = 110     # ...until it is this far again
FLEE_MEMORY = 20         # ticks to keep fleeing a predator we lost sight of
POP_CAP = [(0, 12), (400, 12), (1000, 7), (1800, 5), (2400, 4)]   # (sim_time, cap)
RESERVE = [(0, 150), (1800, 80)]                 # keep this much after spawning
RESERVE_FREE = 60        # ...when the map shows an unoccupied fruiting tree
DUMP_OVERSHOOT = 4       # old-age dumps may exceed the cap by this many
SCAN_EVERY_ALERT = 20
OLD_AGE, OLD_DUMP_ENERGY = 55, 250
HOP_AFTER = 150          # ticks without seeing fruit -> go somewhere else
CELL = 300               # exploration grid cell size
HOP_TICKS = 20           # length of a hop (x walk speed = distance)
HOP_MIN_ENERGY = 40
SHARE_DIST = 40          # another agent this close = we share a patch
WALL_TURN_DIST = 45
LOC_OK = 12              # position error (px) below which we trust the absolute estimate
FRUIT_REACH = 200        # walk to a known fruit up to this far
HOME_REACH = 320         # relocate to a tree up to this far when none is near
NEAR_TREE = 50           # a known tree this close = stay put
SPREAD_DIST = 110        # idle agents keep at least this far apart
SCAN_EVERY = [(0, 30), (1500, 25)]               # ticks between scans while sitting
FRUIT_TTL, TREE_TTL, FRUITING_TTL = 500, 600, 400
STUCK_TICKS = 40
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


def fix_from_edge(coords):
    """Absolute (x, y, heading) from a boundary-wall edge seen in the agent frame, else None."""
    (rx1, ry1), (rx2, ry2) = coords
    L = math.hypot(rx2 - rx1, ry2 - ry1)
    if L < 1000:
        return None
    horizontal = L > 1400
    h = -math.atan2(ry2 - ry1, rx2 - rx1) + (0 if horizontal else math.pi / 2)
    ox = rx1 * math.cos(h) - ry1 * math.sin(h)  # edge start point, absolute offset from us
    oy = rx1 * math.sin(h) + ry1 * math.cos(h)
    if horizontal:
        sx, sy = 0, (WALL if oy < 0 else H - WALL)
    else:
        sx, sy = (WALL if ox < 0 else W - WALL), 0
    return sx - ox, sy - oy, wrap(h), 0.0


class Hivemind:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.reset()

    def reset(self):
        self.mem = {}
        self.tick = 0
        self.last_time = -1.0
        self.last_predator_tick = -10**9
        self.energy = {}
        self.fruits = []      # [x, y, last_seen]
        self.trees = []       # [x, y, last_seen, fruit_seen]
        self.predators = []   # [x, y, last_seen]
        self.claims = {}      # agent_id -> ("fruit"|"tree", index)
        self.landmarks = {}   # round(edge length, 4) -> [(ax1, ay1, ax2, ay2), ...]
        self.cell_seen = {}   # (i, j) -> tick a localized agent last stood in that cell
        self.terrain = {}     # (x//40, y//40) -> biome name, learned from localized agents' own biome

    def _mem(self, aid):
        m = self.mem.get(aid)
        if m is None:
            m = self.mem[aid] = dict(x=0.0, y=0.0, h=0.0, err=1e9, pred=None, pred_tick=-10**9, scan_left=5,
                                     next_scan=self.rng.randint(20, 60), fruit_tick=self.tick,
                                     hop_until=0, hop_dir=0.0, prev_energy=None, expected_drop=0.0,
                                     aging=False, wall_cooldown=0, sprinting=False, mode="",
                                     target=None, target_d=1e9, target_tick=0)
        return m

    # ---------------- main entry ----------------
    def decide(self, step):
        t = step["sim_time"]
        if t < self.last_time:
            self.reset()
        self.last_time = t
        self.tick += 1
        agents = step["agent_status"]
        alive = {a["agent_id"] for a in agents}
        for aid in list(self.mem):
            if aid not in alive:
                del self.mem[aid]
        self.energy = {a["agent_id"]: a["energy"] for a in agents}

        self._localize(agents)
        self._update_world(agents)
        self._assign(agents)
        spawners = self._choose_spawners(agents, t)

        actions = []
        for a in agents:
            m = self._mem(a["agent_id"])
            self._detect_aging(a, m)
            dist, direction, turn = self._plan(a, m, t)
            spawn = a["agent_id"] in spawners and a["energy"] > 100 and not m["mode"].startswith("flee")
            if spawn:
                dist = 0.0  # stand still while investing
            cost, real = move_cost(a, dist)
            m["expected_drop"] = 0.1 + cost + min(math.pi, abs(turn)) / (2 * math.pi) + (100 if spawn else 0)
            real *= BIOME_PENALTY.get(a["biome"], 1.0)
            m["x"] += real * math.cos(m["h"] + direction)
            m["y"] += real * math.sin(m["h"] + direction)
            m["err"] += 0.2 * real  # obstacle deflection is invisible to us
            m["h"] += turn  # heading is exact (turns are applied verbatim)
            m["prev_energy"] = a["energy"]
            actions.append(ActionRequest(agent_id=a["agent_id"], move_distance=float(dist),
                                         move_direction=float(direction), turn_angle=float(turn), spawn_agent=spawn))
        return actions

    # ---------------- localization & world model ----------------
    def _localize(self, agents):
        for a in agents:
            m = self._mem(a["agent_id"])
            edges = [o["coords"] for o in a["observations"] if o["type"] == "Edge"]
            best = None
            for c in edges:
                f = fix_from_edge(c)
                if f and (best is None or f[3] < best[3]):
                    best = f
            if best is None:
                best = self._fix_from_landmarks(edges, m)
            if best and best[3] < m["err"]:
                m["x"], m["y"], m["h"], m["err"] = best
            if m["err"] <= 1:  # learn obstacle edges as landmarks (exactness spreads out from the walls)
                ch, sh = math.cos(m["h"]), math.sin(m["h"])
                for (rx1, ry1), (rx2, ry2) in edges:
                    L = math.hypot(rx2 - rx1, ry2 - ry1)
                    if L >= 1000:
                        continue
                    seg = (m["x"] + rx1 * ch - ry1 * sh, m["y"] + rx1 * sh + ry1 * ch,
                           m["x"] + rx2 * ch - ry2 * sh, m["y"] + rx2 * sh + ry2 * ch)
                    lst = self.landmarks.setdefault(round(L, 4), [])
                    if not any(abs(seg[0] - l[0]) < 0.5 and abs(seg[1] - l[1]) < 0.5 for l in lst):
                        lst.append(seg)
        for a in agents:  # propagate: a well-localized agent fixes the agents it sees
            m = self._mem(a["agent_id"])
            if m["err"] > LOC_OK:
                continue
            for o in a["observations"]:
                if o["type"] != "Agent" or o["id"] not in self.mem:
                    continue
                om = self.mem[o["id"]]
                if om["err"] <= m["err"] + 5:
                    continue
                ang = m["h"] + o["angle"]
                om["x"] = m["x"] + o["distance"] * math.cos(ang)
                om["y"] = m["y"] + o["distance"] * math.sin(ang)
                om["h"] = wrap(math.atan2(m["y"] - om["y"], m["x"] - om["x"]) - o["rel_dir"])
                om["err"] = m["err"] + 5

    def _fix_from_landmarks(self, edges, m):
        """Pose from learned obstacle edges. Same-length siblings (and corner-grazed far edges) are
        disambiguated by consistency with our estimate, or by two edges agreeing when unlocalized."""
        cands = []
        for ei, ((rx1, ry1), (rx2, ry2)) in enumerate(edges):
            L = math.hypot(rx2 - rx1, ry2 - ry1)
            rdir = math.atan2(ry2 - ry1, rx2 - rx1)
            for ax1, ay1, ax2, ay2 in self.landmarks.get(round(L, 4), ()):
                h = wrap(math.atan2(ay2 - ay1, ax2 - ax1) - rdir)
                ox, oy = rx1 * math.cos(h) - ry1 * math.sin(h), rx1 * math.sin(h) + ry1 * math.cos(h)
                cands.append((ax1 - ox, ay1 - oy, h, ei))
        if not cands:
            return None
        if m["err"] < 80:
            ok = [c for c in cands if abs(wrap(c[2] - m["h"])) < 0.02
                  and math.hypot(c[0] - m["x"], c[1] - m["y"]) < m["err"] + 15]
            if ok:
                c = min(ok, key=lambda c: math.hypot(c[0] - m["x"], c[1] - m["y"]))
                return c[0], c[1], c[2], 0.5
            return None
        for i, c in enumerate(cands):  # unlocalized: two different edges must agree
            for d in cands[i + 1:]:
                if c[3] != d[3] and abs(wrap(c[2] - d[2])) < 0.01 and math.hypot(c[0] - d[0], c[1] - d[1]) < 2:
                    return c[0], c[1], c[2], 0.5
        return None

    def _update_world(self, agents):
        for a in agents:
            m = self._mem(a["agent_id"])
            if m["err"] > LOC_OK:
                continue
            obs = a["observations"]
            edges = [o["coords"] for o in obs if o["type"] == "Edge"]
            self.cell_seen[(int(m["x"] // CELL), int(m["y"] // CELL))] = self.tick
            self.terrain[(int(m["x"] // 40), int(m["y"] // 40))] = a["biome"]
            hear = a["hearing_radius"] - 8
            # things we should perceive (hearing, or unblocked in the vision cone) but don't are gone
            def perceivable(px, py):
                d = math.hypot(px - m["x"], py - m["y"])
                if d <= hear:
                    return True
                ang = wrap(math.atan2(py - m["y"], px - m["x"]) - m["h"])
                return (d <= a["vision_range"] - 15 and abs(ang) < a["vision_angle"] / 2 - 0.08
                        and not self._blocked(d, ang, edges))
            self.fruits = [f for f in self.fruits if not perceivable(f[0], f[1])]
            self.trees = [tr for tr in self.trees if not perceivable(tr[0], tr[1])]
            seen_fruit = []
            for o in obs:
                if o["type"] in ("Fruit", "Tree", "Predator"):
                    ang = m["h"] + o["angle"]
                    wx, wy = m["x"] + o["distance"] * math.cos(ang), m["y"] + o["distance"] * math.sin(ang)
                    if o["type"] == "Fruit":
                        if o["distance"] < hear + 8 and self._blocked(o["distance"], o["angle"], edges):
                            continue  # heard through a wall: unreachable, keep it out of the map
                        self._upsert(self.fruits, wx, wy, 8, [wx, wy, self.tick])
                        seen_fruit.append((wx, wy))
                    elif o["type"] == "Tree":
                        rec = self._upsert(self.trees, wx, wy, 25, [wx, wy, self.tick, -10**9])
                        rec[2] = self.tick
                    else:
                        self._upsert(self.predators, wx, wy, 40, [wx, wy, self.tick])
            for fx, fy in seen_fruit:
                for tr in self.trees:
                    if math.hypot(tr[0] - fx, tr[1] - fy) < 80:
                        tr[3] = self.tick
        self.fruits = [f for f in self.fruits if self.tick - f[2] < FRUIT_TTL]
        self.trees = [tr for tr in self.trees if self.tick - tr[2] < TREE_TTL]
        self.predators = [p for p in self.predators if self.tick - p[2] < 100]

    @staticmethod
    def _upsert(lst, x, y, radius, rec):
        for r in lst:
            if math.hypot(r[0] - x, r[1] - y) < radius:
                r[2] = rec[2]
                return r
        lst.append(rec)
        return rec

    def _assign(self, agents):
        """Fruit: greedy nearest-first, one per agent, short reach. Home: a sticky tree per agent,
        spaced out so the colony forms a lattice of scanners."""
        self.claims = {}
        loc = [(a, self.mem[a["agent_id"]]) for a in agents
               if self.mem[a["agent_id"]]["err"] <= LOC_OK and not self.mem[a["agent_id"]]["aging"]]
        pairs = sorted((math.hypot(f[0] - m["x"], f[1] - m["y"]), a["agent_id"], i)
                       for a, m in loc for i, f in enumerate(self.fruits))
        taken = set()
        for d, aid, i in pairs:
            if d > FRUIT_REACH or aid in self.claims or i in taken:
                continue
            self.claims[aid] = ("fruit", i)
            taken.add(i)

    # ---------------- reproduction ----------------
    def _choose_spawners(self, agents, t):
        n = len(agents)
        cap = interp(t, POP_CAP)
        reserve = interp(t, RESERVE)
        # a fruiting tree nobody sits at = room for one more mouth: breed cheaply
        loc = [m for m in self.mem.values() if m["err"] <= LOC_OK]
        free = sum(1 for tr in self.trees if self.tick - tr[3] < FRUITING_TTL
                   and not any(math.hypot(tr[0] - m["x"], tr[1] - m["y"]) < SPREAD_DIST for m in loc))
        if free:
            reserve = RESERVE_FREE
        chosen = set()
        dumpers = []
        for a in agents:
            m = self._mem(a["agent_id"])
            floor = 0.2 * a["max_energy"] + 20
            old = a["age"] > OLD_AGE and a["energy"] > max(OLD_DUMP_ENERGY, 100 + floor)
            if (m["aging"] and a["energy"] > 100) or old:
                dumpers.append(a)  # dying anyway: convert energy to children
        dumpers.sort(key=lambda a: a["energy"], reverse=True)
        for a in dumpers[:max(0, int(cap) + DUMP_OVERSHOOT - n)]:
            chosen.add(a["agent_id"])
        able = [a for a in agents if a["agent_id"] not in chosen
                and a["energy"] > 100 + max(reserve, 0.2 * a["max_energy"] + 20)]
        able.sort(key=fitness, reverse=True)
        room = int(cap) - n - len(chosen)
        if n == 1 and able:
            room = max(room, 1)
        for a in able[:max(room, 0)]:
            chosen.add(a["agent_id"])
        return chosen

    def _detect_aging(self, a, m):
        if m["prev_energy"] is None or m["aging"]:
            return
        drop = m["prev_energy"] - a["energy"]
        if a["age"] > 60 and drop > m["expected_drop"] + 0.3:
            m["aging"] = True

    # ---------------- per-agent movement ----------------
    def _plan(self, a, m, t):
        """Priority chain; each tier returns (move_distance, move_direction_rel, turn_angle) or None to pass."""
        obs = a["observations"]
        preds = [o for o in obs if o["type"] == "Predator"]
        fruits = [o for o in obs if o["type"] == "Fruit"]
        edges = [o["coords"] for o in obs if o["type"] == "Edge"]
        return (self._flee(a, m, preds)
                or self._eat(a, m, fruits, edges)
                or self._scan_step(a, m)
                or self._go_to_claim(a, m)
                or self._forage(a, m, obs, edges)
                or self._sit(a, m, t))

    def _flee(self, a, m, preds):
        """Face the closest predator (slightly off-centre so it pivots instead of charging), back away from all."""
        speed, sprint = a["speed"], a["sprint_speed"]
        if preds:
            p = min(preds, key=lambda o: o["distance"])
            m["pred"], m["pred_tick"] = wrap(m["h"] + p["angle"]), self.tick  # absolute bearing
            self.last_predator_tick = self.tick
            fx = fy = 0.0
            for o in preds:
                w = 1.0 / max(o["distance"], 1.0)
                fx -= w * math.cos(o["angle"])
                fy -= w * math.sin(o["angle"])
            away = self._flee_dir(m, math.atan2(fy, fx))
            seen_by_it = p["distance"] < 60 or abs(p["rel_dir"]) < math.pi / 6 + 0.15
            limit = CHARGE_RELEASE if m["sprinting"] else CHARGE_DIST
            can_sprint = a["energy"] > 0.2 * a["max_energy"] + 5
            m["sprinting"] = seen_by_it and p["distance"] < limit and can_sprint
            m["scan_left"] = 0
            m["mode"] = "flee"
            return (sprint if m["sprinting"] else speed), away, p["angle"] - 0.35
        if m["pred"] is not None and self.tick - m["pred_tick"] < FLEE_MEMORY:
            m["mode"] = "flee_mem"
            return speed, self._flee_dir(m, wrap(m["pred"] + math.pi - m["h"])), 0.0
        return None

    def _eat(self, a, m, fruits, edges):
        """Walk to visible fruit (ignoring fruit only heard through a wall). Localized agents follow their
        claim instead unless the fruit is very close. Dying agents never walk."""
        fruits = [f for f in fruits if not self._blocked(f["distance"], f["angle"], edges)]
        if fruits:
            m["fruit_tick"] = self.tick
        nearest = min((f["distance"] for f in fruits), default=None)
        if m["aging"] and not (nearest is not None and nearest < 60):
            m["mode"] = "aging"
            return 0.0, 0.0, 0.0
        if fruits and (m["err"] > LOC_OK or nearest < 70):
            f = min(fruits, key=lambda o: o["distance"])
            m["scan_left"] = 0
            m["hop_until"] = 0
            m["mode"] = "eat"
            turn = f["angle"] if f["distance"] > 60 and abs(f["angle"]) > 0.6 else 0.0
            return min(a["speed"], f["distance"] + 2), f["angle"], turn
        return None

    def _scan_step(self, a, m):
        """Continue a 360-degree scan in progress."""
        if m["scan_left"] <= 0:
            return None
        m["scan_left"] -= 1
        m["mode"] = "scan"
        return 0.0, 0.0, a["vision_angle"]

    def _go_to_claim(self, a, m):
        """Walk to the world-map fruit assigned to us; drop it if we stop getting closer."""
        claim = self.claims.get(a["agent_id"])
        if not claim:
            return None
        tx, ty = self.fruits[claim[1]][:2]
        d = math.hypot(tx - m["x"], ty - m["y"])
        if claim != m["target"]:
            m["target"], m["target_d"], m["target_tick"] = claim, d, self.tick
        elif d < m["target_d"] - 5:
            m["target_d"], m["target_tick"] = d, self.tick
        elif self.tick - m["target_tick"] > STUCK_TICKS:
            self.fruits.pop(claim[1])
            self.claims = {}
            m["target"] = None
        if not m["target"] or d <= 4:
            return None
        m["fruit_tick"] = self.tick
        rel = wrap(math.atan2(ty - m["y"], tx - m["x"]) - m["h"])
        m["mode"] = "tofruit"
        return min(a["speed"], d - 2), rel, rel if abs(rel) > 0.5 else 0.0

    def _forage(self, a, m, obs, edges):
        """Stay where trees are, keep the colony spread out, relocate or explore when the patch is quiet."""
        if m["err"] <= LOC_OK:
            r = self._keep_spread(a, m, edges) or self._relocate_to_tree(a, m)
            if r:
                return r
        if self.tick < m["hop_until"]:
            m["mode"] = "hop"
            return self._walk(a, m, edges)
        if self.tick - m["fruit_tick"] > HOP_AFTER and a["energy"] > HOP_MIN_ENERGY:
            return self._explore(a, m, obs, edges)
        return None

    def _keep_spread(self, a, m, edges):
        """If a poorer idle agent sits within SPREAD_DIST, the richer one walks away for 15 ticks."""
        crowd = [(math.hypot(om["x"] - m["x"], om["y"] - m["y"]), oid) for oid, om in self.mem.items()
                 if oid != a["agent_id"] and om["err"] <= LOC_OK and om["mode"] in ("sit", "scan", "")]
        d_crowd, oid = min(crowd) if crowd else (1e9, None)
        richer = oid is not None and (self.energy[oid], -oid) < (a["energy"], -a["agent_id"])
        if d_crowd < SPREAD_DIST and richer and a["energy"] > HOP_MIN_ENERGY and self.tick >= m["hop_until"]:
            om = self.mem[oid]
            m["hop_until"] = self.tick + 15
            m["hop_dir"] = math.atan2(m["y"] - om["y"], m["x"] - om["x"]) + self.rng.uniform(-0.4, 0.4)
        if self.tick < m["hop_until"]:
            m["mode"] = "spread"
            return self._walk(a, m, edges)
        return None

    def _relocate_to_tree(self, a, m):
        """No tree nearby (or the patch went quiet): walk to the best unoccupied tree within reach."""
        near_tree = any(math.hypot(tr[0] - m["x"], tr[1] - m["y"]) < NEAR_TREE for tr in self.trees)
        if near_tree and self.tick - m["fruit_tick"] < HOP_AFTER:
            return None
        best = None
        for tr in self.trees:
            d = math.hypot(tr[0] - m["x"], tr[1] - m["y"])
            if d > HOME_REACH or (near_tree and d < NEAR_TREE):
                continue
            if any(math.hypot(tr[0] - om["x"], tr[1] - om["y"]) < SPREAD_DIST for oid, om in self.mem.items()
                   if oid != a["agent_id"] and om["err"] <= LOC_OK):
                continue
            score = d + (0 if self.tick - tr[3] < FRUITING_TTL else 100)
            if best is None or score < best[0]:
                best = (score, tr)
        if not best:
            return None
        tx, ty = best[1][0], best[1][1]
        d = math.hypot(tx - m["x"], ty - m["y"])
        rel = wrap(math.atan2(ty - m["y"], tx - m["x"]) - m["h"])
        m["fruit_tick"] = self.tick
        m["mode"] = "totree"
        return min(a["speed"], d - 15), rel, rel if abs(rel) > 0.5 else 0.0

    def _explore(self, a, m, obs, edges):
        """Nothing known nearby: localized agents head for the stalest grid cell, others hop blindly."""
        if m["err"] <= LOC_OK:
            best = None
            for i in range(W // CELL + 1):
                for j in range(H // CELL + 1):
                    cx, cy = min(i * CELL + CELL / 2, W - 60), min(j * CELL + CELL / 2, H - 60)
                    d = math.hypot(cx - m["x"], cy - m["y"])
                    if d < 100 or d > 600:
                        continue
                    stale = self.tick - self.cell_seen.get((i, j), -10**6)
                    score = d - min(stale, 2000) * 0.3
                    if best is None or score < best[0]:
                        best = (score, cx, cy)
            if best:
                m["hop_dir"] = math.atan2(best[2] - m["y"], best[1] - m["x"])
                m["hop_until"] = self.tick + int(math.hypot(best[1] - m["x"], best[2] - m["y"]) / a["speed"])
                m["fruit_tick"] = self.tick
                m["mode"] = "hop"
                return self._walk(a, m, edges)
        self._start_hop(a, m, obs)
        m["mode"] = "hop"
        return self._walk(a, m, edges)

    def _sit(self, a, m, t):
        """Sit still; start a scan on schedule; otherwise keep the cone on the nearest known predator."""
        m["next_scan"] -= 1
        if m["next_scan"] <= 0:
            alert = self.tick - self.last_predator_tick < 100
            m["next_scan"] = SCAN_EVERY_ALERT if alert else int(interp(t, SCAN_EVERY))
            m["scan_left"] = math.ceil(2 * math.pi / a["vision_angle"]) - 1
            m["mode"] = "scan"
            return 0.0, 0.0, a["vision_angle"]
        m["mode"] = "sit"
        if m["err"] <= LOC_OK and self.predators:
            px, py, _ = min(self.predators, key=lambda q: math.hypot(q[0] - m["x"], q[1] - m["y"]))
            if math.hypot(px - m["x"], py - m["y"]) < 450:
                rel = wrap(math.atan2(py - m["y"], px - m["x"]) - m["h"])
                if abs(rel) > 0.25:
                    return 0.0, 0.0, rel
        return 0.0, 0.0, 0.0

    def _start_hop(self, a, m, obs):
        """Head away from visible agents (or randomly) for a committed leg."""
        m["hop_until"] = self.tick + HOP_TICKS
        m["fruit_tick"] = self.tick
        others = [o for o in obs if o["type"] == "Agent"]
        if others:
            ax = sum(math.cos(o["angle"]) for o in others)
            ay = sum(math.sin(o["angle"]) for o in others)
            m["hop_dir"] = m["h"] + math.atan2(-ay, -ax) + self.rng.uniform(-0.5, 0.5)
        else:
            m["hop_dir"] = self.rng.uniform(-math.pi, math.pi)

    def _walk(self, a, m, edges):
        """Walk straight in hop_dir, bounce off walls, keep the cone pointed forward."""
        if m["wall_cooldown"] > 0:
            m["wall_cooldown"] -= 1
        if self._nearest_edge_dist(edges) < WALL_TURN_DIST and m["wall_cooldown"] == 0:
            m["hop_dir"] += self.rng.choice((-1, 1)) * self.rng.uniform(math.pi / 2, math.pi)
            m["wall_cooldown"] = 15
        rel = wrap(m["hop_dir"] - m["h"])
        return a["speed"], rel, rel if abs(rel) > 0.3 else 0.0

    # ---------------- helpers ----------------
    def _flee_dir(self, m, away_rel):
        """Pick the flee direction (relative) closest to `away_rel` whose next 60 px stay on walkable ground:
        no river/swamp cells, no boundary, no known obstacle edge in the way. Unlocalized agents just go away."""
        if m["err"] > LOC_OK:
            return away_rel
        best = None
        for k in (0, 1, -1, 2, -2, 3, -3, 4, -4):
            rel = away_rel + k * 0.35
            ang = m["h"] + rel
            cost = abs(k) * 0.5
            for step in (20, 40, 60):
                x, y = m["x"] + step * math.cos(ang), m["y"] + step * math.sin(ang)
                if not (WALL + 8 < x < W - WALL - 8 and WALL + 8 < y < H - WALL - 8):
                    cost += 10
                    break
                b = self.terrain.get((int(x // 40), int(y // 40)))
                cost += {"river": 6, "swamp": 3, "desert": 0.5}.get(b, 0)
            if self._blocked_abs(m["x"], m["y"], m["x"] + 60 * math.cos(ang), m["y"] + 60 * math.sin(ang)):
                cost += 10
            if best is None or cost < best[0]:
                best = (cost, rel)
        return best[1]

    def _blocked_abs(self, x1, y1, x2, y2):
        """Does the absolute segment cross any learned obstacle edge near it?"""
        for segs in self.landmarks.values():
            for ax1, ay1, ax2, ay2 in segs:
                if abs(ax1 - x1) > 200 or abs(ay1 - y1) > 200:
                    continue
                px, py, ex, ey = x2 - x1, y2 - y1, ax2 - ax1, ay2 - ay1
                den = px * ey - py * ex
                if abs(den) < 1e-9:
                    continue
                t = ((ax1 - x1) * ey - (ay1 - y1) * ex) / den
                u = ((ax1 - x1) * py - (ay1 - y1) * px) / den
                if 0 <= t <= 1 and 0 <= u <= 1:
                    return True
        return False

    @staticmethod
    def _blocked(d, ang, edges):
        """True if the straight walk to a point at (d, ang) crosses a visible edge (agent frame)."""
        px, py = d * math.cos(ang), d * math.sin(ang)
        for (x1, y1), (x2, y2) in edges:
            ex, ey = x2 - x1, y2 - y1
            den = px * ey - py * ex
            if abs(den) < 1e-9:
                continue
            t = (x1 * ey - y1 * ex) / den
            u = (x1 * py - y1 * px) / den
            if 0 <= t <= 1 and 0 <= u <= 1:
                return True
        return False

    @staticmethod
    def _nearest_edge_dist(edges):
        best = float("inf")
        for (x1, y1), (x2, y2) in edges:
            if x1 < 0 and x2 < 0:  # behind us, ignore
                continue
            dx, dy = x2 - x1, y2 - y1
            l2 = dx * dx + dy * dy
            u = 0.0 if l2 == 0 else max(0.0, min(1.0, -(x1 * dx + y1 * dy) / l2))
            best = min(best, math.hypot(x1 + u * dx, y1 + u * dy))
        return best
