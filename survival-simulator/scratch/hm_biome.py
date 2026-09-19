"""Heuristic hivemind controller.

Every agent is localized in absolute map coordinates: a sighting of a boundary wall edge (the only
edges >= 1000 px long) gives exact heading + position; localized agents localize the agents they see.
All sightings feed one shared world map (fruits, trees, predators) that every agent plans against.

Per agent priority (see _plan): flee predators > eat visible fruit > finish a scan > walk to the claimed map
fruit > forage (stay near trees, keep spread out, relocate/explore when the patch is quiet) > sit and scan.
"""
import math
import os
import random
from src.utils.DTOs import ActionRequest
from src.utils.controllers import flee_net

W, H, WALL = 1600, 1200, 30

# ---- tunables ----
CHARGE_DIST = 92         # predator closer than this charges -> sprint away
CHARGE_RELEASE = 110     # ...until it is this far again
FLEE_MEMORY = 20         # ticks to keep fleeing a predator we lost sight of
POP_CAP = [(0, 12), (1800, 12), (2400, 8)]   # (sim_time, cap)
RESERVE = [(0, 150), (600, 120)]   # never breed below the 20 % sprint lock (100) + margin                 # keep this much after spawning
RESERVE_FREE = 60        # ...when the map shows an unoccupied fruiting tree
DUMP_OVERSHOOT = 4       # old-age dumps may exceed the cap by this many
SCAN_EVERY_ALERT = 10
OLD_AGE, OLD_DUMP_ENERGY = 55, 250
HOP_AFTER = 150          # ticks without seeing fruit -> go somewhere else
CELL = 300               # exploration grid cell size
HOP_TICKS = 20           # length of a hop (x walk speed = distance)
HOP_MIN_ENERGY = 40
WALL_TURN_DIST = 45
LOC_OK = 12              # position error (px) below which we trust the absolute estimate
FRUIT_REACH = 200        # walk to a known fruit up to this far
HOME_REACH = 320         # relocate to a tree up to this far when none is near
NEAR_TREE = 50           # a known tree this close = stay put
GROVE_R = 120            # trees within this of a spot all feed it
GROVE_VALUE = 80         # px of walking one extra fruiting tree is worth
BAD_BIOME = {"river": 300, "desert": 120}   # px of walking a tree/claim in a kill zone costs (kill ratio 2.1-2.7x there)
FRUIT_RATE = {"forest": 1.0, "grassland": 1.0, "swamp": 0.8, "desert": 0.5, "river": 0.0}   # per-tree fruit odds by biome
SPREAD_DIST = 110        # idle agents keep at least this far apart
SPREAD_LATE = 300        # ...from t=600: one agent per tree, predators only ever find one of us
SCAN_EVERY = [(0, 30), (600, 15)]                # ticks between scans while sitting; a predator crosses its 250 px vision in 23 ticks
FRUIT_TTL, TREE_TTL, FRUITING_TTL = 500, 600, 400
RIPEN, HUNGRY = 200, 0.30     # a fruit is worth 20 energy when it spawns and 60 after 20 s: wait unless below HUNGRY of max
STUCK_SNAPS = 5          # consecutive ticks the pose fix undoes our commanded move -> we are pushing on a wall
STUCK_SNAP_FRACTION = 0.6
BLACKLIST_TICKS = 200    # how long an unreachable target stays off-limits
BIOME_PENALTY = {"swamp": 0.5, "desert": 0.8, "river": 0.3}
FLEE_NET = flee_net.load() if os.path.exists(flee_net.WEIGHTS) else None   # learned evasion (scratch/train_flee.py); None = hand rule


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
        self.fruits = []      # [x, y, last_seen, ripe_tick] (ripe_tick 0 = age unknown, eat now)
        self.gone = []        # fruit records pruned recently: a re-sighting inherits their ripe_tick
        self.trees = []       # [x, y, last_seen, fruit_seen]
        self.predators = []   # [x, y, last_seen]
        self.claims = {}      # agent_id -> index into self.fruits
        self.landmarks = {}   # round(edge length, 4) -> [(ax1, ay1, ax2, ay2, abs_dir), ...]
        self.cell_seen = {}   # (i, j) -> tick a localized agent last stood in that cell
        self.terrain = {}     # (x//40, y//40) -> biome name, learned from localized agents' own biome

    def _mem(self, aid):
        m = self.mem.get(aid)
        if m is None:
            m = self.mem[aid] = dict(x=0.0, y=0.0, h=0.0, err=1e9, pred=None, pred_tick=-10**9, scan_left=5,
                                     next_scan=self.rng.randint(20, 60), fruit_tick=self.tick,
                                     hop_until=0, hop_dir=0.0, prev_energy=None, expected_drop=0.0,
                                     aging=False, wall_cooldown=0, sprinting=False, mode="",
                                     target=None, target_xy=None, last_step=0.0, stuck=0, blacklist=[])
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
            m["last_step"] = real
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
            self._fix_pose(a, m, edges)
            if m["err"] <= 1:
                self._learn_landmarks(m, edges)
        self._propagate_fixes(agents)

    def _fix_pose(self, a, m, edges):
        """Adopt the best pose fix visible this tick: a boundary wall first, else a learned landmark."""
        fixes = [f for f in map(fix_from_edge, edges) if f]
        best = min(fixes, key=lambda f: f[3]) if fixes else self._fix_from_landmarks(edges, m)
        if best and best[3] < m["err"]:
            self._note_snapback(a, m, best[0], best[1], m["last_step"])
            m["x"], m["y"], m["h"], m["err"] = best

    def _note_snapback(self, a, m, fx, fy, step):
        """A pose fix that undoes most of last tick's commanded move means the wall took it: after STUCK_SNAPS
        such ticks give the target up, blacklist it, and hop sideways along the wall."""
        snap = math.hypot(m["x"] - fx, m["y"] - fy)
        m["stuck"] = m["stuck"] + 1 if step > 2 and snap >= STUCK_SNAP_FRACTION * step else 0
        if m["stuck"] < STUCK_SNAPS:
            return
        if m["target_xy"] is not None:
            m["blacklist"].append((m["target_xy"][0], m["target_xy"][1], self.tick + BLACKLIST_TICKS))
        self.claims.pop(a["agent_id"], None)
        m["target"], m["target_xy"], m["stuck"] = None, None, 0
        wall_dir = math.atan2(m["y"] - fy, m["x"] - fx)  # the direction we were being pushed back from
        m["hop_dir"] = wall_dir + self.rng.choice((-1, 1)) * math.pi / 2
        m["hop_until"] = self.tick + 15

    def _is_blacklisted(self, m, x, y):
        m["blacklist"] = [b for b in m["blacklist"] if b[2] > self.tick]
        return any(math.hypot(b[0] - x, b[1] - y) < 25 for b in m["blacklist"])

    def _learn_landmarks(self, m, edges):
        """An exactly localized agent records every obstacle edge it sees in absolute coordinates."""
        for (rx1, ry1), (rx2, ry2) in edges:
            L = math.hypot(rx2 - rx1, ry2 - ry1)
            if L >= 1000:
                continue  # boundary wall, handled by fix_from_edge
            seg = (*self._to_world(m, rx1, ry1), *self._to_world(m, rx2, ry2))
            lst = self.landmarks.setdefault(round(L, 4), [])
            if not any(abs(seg[0] - l[0]) < 0.5 and abs(seg[1] - l[1]) < 0.5 for l in lst):
                lst.append(seg + (math.atan2(seg[3] - seg[1], seg[2] - seg[0]),))   # absolute direction, precomputed

    def _propagate_fixes(self, agents):
        """A well-localized agent fixes the position and heading of every agent it sees."""
        for a in agents:
            m = self._mem(a["agent_id"])
            if m["err"] > LOC_OK:
                continue
            for o in a["observations"]:
                if o["type"] != "Agent" or o["id"] not in self.mem:
                    continue
                om = self.mem[o["id"]]
                if om["err"] <= m["err"] + 5:
                    continue
                om["x"], om["y"] = self._polar_to_world(m, o["distance"], o["angle"])
                om["h"] = wrap(math.atan2(m["y"] - om["y"], m["x"] - om["x"]) - o["rel_dir"])
                om["err"] = m["err"] + 5

    @staticmethod
    def _to_world(m, rx, ry):
        """Agent-frame (x forward, y left) point -> absolute point."""
        ch, sh = math.cos(m["h"]), math.sin(m["h"])
        return m["x"] + rx * ch - ry * sh, m["y"] + rx * sh + ry * ch

    @staticmethod
    def _polar_to_world(m, d, ang):
        """Observation (distance, relative angle) -> absolute point."""
        return m["x"] + d * math.cos(m["h"] + ang), m["y"] + d * math.sin(m["h"] + ang)

    def _fix_from_landmarks(self, edges, m):
        """Pose from learned obstacle edges. Same-length siblings (and corner-grazed far edges) are
        disambiguated by consistency with our estimate, or by two edges agreeing when unlocalized."""
        localized = m["err"] < 80
        mh, mx, my, reach = m["h"], m["x"], m["y"], m["err"] + 15
        cands = []
        for ei, ((rx1, ry1), (rx2, ry2)) in enumerate(edges):
            L = math.hypot(rx2 - rx1, ry2 - ry1)
            rdir = math.atan2(ry2 - ry1, rx2 - rx1)
            for ax1, ay1, ax2, ay2, adir in self.landmarks.get(round(L, 4), ()):
                h = wrap(adir - rdir)
                if localized and abs(wrap(h - mh)) >= 0.02:   # cheap heading test first: most landmarks fail it
                    continue
                ox, oy = rx1 * math.cos(h) - ry1 * math.sin(h), rx1 * math.sin(h) + ry1 * math.cos(h)
                cands.append((ax1 - ox, ay1 - oy, h, ei))
        if not cands:
            return None
        if localized:
            ok = [c for c in cands if math.hypot(c[0] - mx, c[1] - my) < reach]
            if ok:
                c = min(ok, key=lambda c: math.hypot(c[0] - mx, c[1] - my))
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
            edges = [o["coords"] for o in a["observations"] if o["type"] == "Edge"]
            self.cell_seen[(int(m["x"] // CELL), int(m["y"] // CELL))] = self.tick
            self.terrain[(int(m["x"] // 40), int(m["y"] // 40))] = a["biome"]
            self._prune_unseen(a, m, edges)
            self._record_sightings(a, m, edges)
        self.fruits = [f for f in self.fruits if self.tick - f[2] < FRUIT_TTL]
        self.gone = [g for g in self.gone if self.tick - g[4] < 100]
        if self.tick % 5 == 0:   # pose history for the freshness test: where have we looked in the last 30 s
            for a in agents:
                m = self._mem(a["agent_id"])
                if m["err"] <= LOC_OK:
                    m.setdefault("watch", []).append((self.tick, m["x"], m["y"], m["h"], a["hearing_radius"] - 8,
                                                      a["vision_range"] - 15, a["vision_angle"] / 2 - 0.08))
                    del m["watch"][:-60]
        self.trees = [tr for tr in self.trees if self.tick - tr[2] < TREE_TTL]
        self.predators = [p for p in self.predators if self.tick - p[2] < 100]

    def _prune_unseen(self, a, m, edges):
        """Map entries this agent should perceive (hearing, or unblocked in its cone) but doesn't are gone."""
        hear = a["hearing_radius"] - 8
        def perceivable(px, py):
            d = math.hypot(px - m["x"], py - m["y"])
            if d <= hear:
                return True
            ang = wrap(math.atan2(py - m["y"], px - m["x"]) - m["h"])
            return (d <= a["vision_range"] - 15 and abs(ang) < a["vision_angle"] / 2 - 0.08
                    and not self._blocked(d, ang, edges))
        self.gone += [f + [self.tick] for f in self.fruits if perceivable(f[0], f[1])]
        self.fruits = [f for f in self.fruits if not perceivable(f[0], f[1])]
        self.trees = [tr for tr in self.trees if not perceivable(tr[0], tr[1])]

    def _record_sightings(self, a, m, edges):
        """Add this tick's fruit, tree and predator observations to the shared map; mark trees with fruit near."""
        hear = a["hearing_radius"] - 8
        seen_fruit = []
        for o in a["observations"]:
            if o["type"] not in ("Fruit", "Tree", "Predator"):
                continue
            wx, wy = self._polar_to_world(m, o["distance"], o["angle"])
            if o["type"] == "Fruit":
                if o["distance"] < hear + 8 and self._blocked(o["distance"], o["angle"], edges):
                    continue  # heard through a wall: unreachable, keep it out of the map
                rec = self._upsert(self.fruits, wx, wy, 8, [wx, wy, self.tick, None])
                if rec[3] is None:   # first sighting: fresh if some agent could perceive the spot a tick ago
                    old = next((g for g in self.gone if math.hypot(g[0] - wx, g[1] - wy) < 8), None)
                    last = None if old else self._watched(wx, wy)
                    rec[3] = old[3] if old else (last + RIPEN if last is not None else 0)
                seen_fruit.append((wx, wy))
            elif o["type"] == "Tree":
                self._upsert(self.trees, wx, wy, 25, [wx, wy, self.tick, -10**9])[2] = self.tick
            else:
                self._upsert(self.predators, wx, wy, 40, [wx, wy, self.tick])
        for fx, fy in seen_fruit:
            for tr in self.trees:
                if math.hypot(tr[0] - fx, tr[1] - fy) < 80:
                    tr[3] = self.tick

    def _watched(self, x, y):
        """Last tick (within 30 s) at which some localized agent could perceive (x, y) and saw no fruit there:
        a fruit appearing there now is younger than that. None if nobody looked."""
        last = None
        for m in self.mem.values():
            for t, wx, wy, wh, hear, vis, half in reversed(m.get("watch", ())):
                if last is not None and t <= last:
                    break
                d = math.hypot(x - wx, y - wy)
                if d <= hear or (d <= vis and abs(wrap(math.atan2(y - wy, x - wx) - wh)) < half):
                    last = t
                    break
        return last

    def _ripe(self, i, at_tick):
        return self.fruits[i][3] <= at_tick

    @staticmethod
    def _upsert(lst, x, y, radius, rec):
        for r in lst:
            if math.hypot(r[0] - x, r[1] - y) < radius:
                r[2] = rec[2]
                return r
        lst.append(rec)
        return rec

    def _assign(self, agents):
        """Claim map fruit for localized, non-dying agents: greedy nearest-first, one fruit per agent."""
        self.claims = {}
        loc = [(a, self.mem[a["agent_id"]]) for a in agents
               if self.mem[a["agent_id"]]["err"] <= LOC_OK and not self.mem[a["agent_id"]]["aging"]]
        pairs = sorted((math.hypot(f[0] - m["x"], f[1] - m["y"]), a["agent_id"], i)
                       for a, m in loc for i, f in enumerate(self.fruits))
        taken = set()
        for d, aid, i in pairs:
            if d > (350 if self.tick >= 6000 else FRUIT_REACH) or aid in self.claims or i in taken                     or self._is_blacklisted(self.mem[aid], self.fruits[i][0], self.fruits[i][1]):
                continue
            hungry = self.energy[aid] < HUNGRY * next(x["max_energy"] for x, _ in loc if x["agent_id"] == aid)
            if not hungry and (not self._ripe(i, self.tick + d / 10) or self._biome_at(*self.fruits[i][:2]) in BAD_BIOME):
                continue
            self.claims[aid] = i
            taken.add(i)

    # ---------------- reproduction ----------------
    def _choose_spawners(self, agents, t):
        n = len(agents)
        cap = interp(t, POP_CAP)
        reserve = interp(t, RESERVE)
        # a fruiting tree nobody sits at = room for one more mouth: breed cheaply
        loc = [m for m in self.mem.values() if m["err"] <= LOC_OK]
        free = sum(1 for tr in self.trees if self.tick - tr[3] < FRUITING_TTL
                   and not any(math.hypot(tr[0] - m["x"], tr[1] - m["y"]) < self._spread() for m in loc))
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
            m["pred_obs"] = (m["x"] + p["distance"] * math.cos(m["h"] + p["angle"]),
                             m["y"] + p["distance"] * math.sin(m["h"] + p["angle"]), p["rel_dir"])  # last known position
            self.last_predator_tick = self.tick
            if FLEE_NET is not None:
                m["scan_left"], m["mode"] = 0, "flee"
                return flee_net.act(FLEE_NET, a, (p["distance"], p["angle"], p["rel_dir"]), True, self._map_preds(m, preds))
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
            if FLEE_NET is not None:
                dx, dy = m["pred_obs"][0] - m["x"], m["pred_obs"][1] - m["y"]
                return flee_net.act(FLEE_NET, a, (math.hypot(dx, dy), wrap(math.atan2(dy, dx) - m["h"]), m["pred_obs"][2]), False, self._map_preds(m, preds))
            return speed, self._flee_dir(m, wrap(m["pred"] + math.pi - m["h"])), 0.0
        return None

    def _map_preds(self, m, preds):
        """(distance, relative angle) of fresh map predators this agent does not see itself (for the flee net)."""
        if m["err"] > LOC_OK:
            return ()
        out = []
        for px, py, pt in self.predators:
            if self.tick - pt > 30:
                continue
            d = math.hypot(px - m["x"], py - m["y"])
            ang = wrap(math.atan2(py - m["y"], px - m["x"]) - m["h"])
            if d < 400 and not any(abs(o["distance"] - d) < 40 and abs(wrap(o["angle"] - ang)) < 0.4 for o in preds):
                out.append((d, ang))
        return out

    def _eat(self, a, m, fruits, edges):
        """Walk to visible fruit (ignoring fruit only heard through a wall). Localized agents follow their
        claim instead unless the fruit is very close. Dying agents never walk."""
        fruits = [f for f in fruits if not self._blocked(f["distance"], f["angle"], edges)]
        if fruits:
            m["fruit_tick"] = self.tick
        if m["err"] <= LOC_OK and a["energy"] >= HUNGRY * a["max_energy"]:
            fruits = [f for f in fruits if self._ripe_at(m, f)]
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

    def _ripe_at(self, m, f):
        """A visible fruit is edible now unless the map knows it is still unripe."""
        wx, wy = self._polar_to_world(m, f["distance"], f["angle"])
        rec = next((r for r in self.fruits if math.hypot(r[0] - wx, r[1] - wy) < 8), None)
        return rec is None or rec[3] <= self.tick

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
        if claim is None:
            return None
        tx, ty = self.fruits[claim][:2]
        d = math.hypot(tx - m["x"], ty - m["y"])
        m["target"], m["target_xy"] = claim, (tx, ty)
        if d <= 4:
            return None
        m["fruit_tick"] = self.tick
        rel = wrap(math.atan2(ty - m["y"], tx - m["x"]) - m["h"])
        m["mode"] = "tofruit"
        rel = self._steer(m, rel)
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
        if d_crowd < self._spread() and richer and a["energy"] > HOP_MIN_ENERGY and self.tick >= m["hop_until"]:
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
            if d > (600 if self.tick >= 6000 else HOME_REACH) or (near_tree and d < NEAR_TREE) or self._is_blacklisted(m, tr[0], tr[1]):
                continue
            if any(math.hypot(tr[0] - om["x"], tr[1] - om["y"]) < self._spread() for oid, om in self.mem.items()
                   if oid != a["agent_id"] and om["err"] <= LOC_OK):
                continue
            score = d - GROVE_VALUE * self._grove_value(tr) + BAD_BIOME.get(self._biome_at(tr[0], tr[1]), 0)
            if best is None or score < best[0]:
                best = (score, tr)
        if not best:
            return None
        tx, ty = best[1][0], best[1][1]
        d = math.hypot(tx - m["x"], ty - m["y"])
        rel = wrap(math.atan2(ty - m["y"], tx - m["x"]) - m["h"])
        m["fruit_tick"], m["target_xy"] = self.tick, (tx, ty)
        m["mode"] = "totree"
        rel = self._steer(m, rel)
        return min(a["speed"], d - 15), rel, rel if abs(rel) > 0.5 else 0.0

    def _spread(self):
        return SPREAD_LATE if self.tick >= 6000 else SPREAD_DIST

    def _grove_value(self, spot):
        """Expected fruit rate around a spot: known trees within GROVE_R, each weighted by how recently it fruited."""
        total = 0.0
        for tr in self.trees:
            if math.hypot(tr[0] - spot[0], tr[1] - spot[1]) < GROVE_R:
                age = self.tick - tr[3]
                total += (1.0 if age < FRUITING_TTL else (0.3 if age < 3 * FRUITING_TTL else 0.1)) * FRUIT_RATE.get(self._biome_at(tr[0], tr[1]), 1.0)
        return total

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
                    b = self._biome_at(cx, cy)
                    if b == "river":
                        continue
                    score = d - min(stale, 2000) * 0.3 + (300 if b == "desert" else 0)
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
        rel = self._steer(m, wrap(m["hop_dir"] - m["h"]))
        return a["speed"], rel, rel if abs(rel) > 0.3 else 0.0

    # ---------------- helpers ----------------
    def _biome_at(self, x, y):
        return self.terrain.get((int(x // 40), int(y // 40)))

    def _steer(self, m, rel):
        """Walking: the smallest deflection from `rel` whose next 40 px do not enter a known river/desert cell."""
        if m["err"] > LOC_OK:
            return rel
        for k in (0, 1, -1, 2, -2):
            r = rel + k * 0.5
            ang = m["h"] + r
            if self._biome_at(m["x"] + 40 * math.cos(ang), m["y"] + 40 * math.sin(ang)) not in BAD_BIOME:
                return wrap(r)
        return rel

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
            for ax1, ay1, ax2, ay2, _ in segs:
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
