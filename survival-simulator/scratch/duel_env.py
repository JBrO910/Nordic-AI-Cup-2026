"""Randomized 1-v-1 evasion env on real maps (obstacles + biomes kept, trees/fruit/random predators removed).

Episode: one agent, one awake predator placed at random distance/angle. Reward = -energy spent / 100 per tick, -5 on
death. Ends when the agent dies, the predator rests, the predator has been > 350 px away for 30 ticks, or 300 ticks.
`python scratch/duel_env.py [n]` prints the served rule's baseline on n (default 300) duels — the number to beat.
"""
import sys, math, random
sys.path.insert(0, ".")
import pygame; pygame.init()
import numpy as np
from src.core import SimulationCore
from src.elements.predator import Predator
from src.utils.DTOs import ActionRequest
from src.utils.controllers.flee_net import featurize, decode, N_DIR, OBS_DIM

SEEDS = list(range(1, 13))
MAX_TICKS, FAR, FAR_TICKS, DEATH = 300, 350, 30, 5.0


class DuelEnv:
    def __init__(self, seed):
        self.sim = SimulationCore(seed=seed, starting_trees=0, starting_fruits=0)
        env = self.env = self.sim.env
        env.spawn_predator = env.spawn_fruit = env.spawn_tree = lambda *a, **k: None
        env.fruits, env.fruits_dict, env.trees = [], {}, []
        env._update_fruit_grid(); env._update_tree_grid()
        for a in list(env.agents)[1:]:
            env.kill_agent(a)
        self.agent = env.agents[0]

    def _free(self, x, y, r=12):
        return self.env._is_position_free(x - r, y - r, 2 * r, 2 * r)

    def reset(self, rng):
        env, ag = self.env, self.agent
        env.predators = []
        if ag not in env.agents:  # eaten last episode
            env.agents.append(ag); env.agents_dict[ag.agent_id] = ag
        while True:
            ag.x, ag.y = rng.uniform(40, env.width - 40), rng.uniform(40, env.height - 40)
            if self._free(ag.x, ag.y):
                break
        ag.direction = rng.uniform(-math.pi, math.pi)
        ag.energy = rng.uniform(40, 400)
        ag.age = 0.0
        if rng.random() < 0.3:  # occasional mutated traits, as in a real population
            ag.speed = min(20, 10 * rng.uniform(0.7, 1.3)); ag.sprint_speed = min(40, 20 * rng.uniform(0.7, 1.3))
            ag.cone_angle = min(math.pi / 2, math.pi / 3 * rng.uniform(0.7, 1.3))
        else:
            ag.speed, ag.sprint_speed, ag.cone_angle = 10.0, 20.0, math.pi / 3
        while True:  # start at the moment of first sighting: in the vision cone (or hearing radius), not occluded
            if rng.random() < 0.8:
                d, ang = rng.uniform(40, ag.vision_radius), ag.direction + rng.uniform(-ag.cone_angle / 2, ag.cone_angle / 2)
            else:
                d, ang = rng.uniform(30, ag.hearing_radius), rng.uniform(-math.pi, math.pi)
            px, py = ag.x + d * math.cos(ang), ag.y + d * math.sin(ang)
            if not (40 < px < env.width - 40 and 40 < py < env.height - 40 and self._free(px, py)):
                continue
            p = Predator(px, py, rng=env.rng)
            p.energy, p.resting, p.direction = rng.uniform(50, 200), False, math.atan2(ag.y - py, ag.x - px)
            env.predators = [p]
            env._update_agent_grid(); env._update_predator_grid()
            e0 = ag.energy
            self.state = self.sim.step([])
            if env.agents and any(o["type"] == "Predator" for o in self.state["observations"][0]["observations"]):
                break
            ag.energy = e0
            if ag not in env.agents:  # eaten during the probe step
                env.agents.append(ag); env.agents_dict[ag.agent_id] = ag
        self.pred, self.ticks, self.far, self.spent = p, 0, 0, 0.0
        self.pred_world, self.last_rel = (px, py), 0.0
        return self._observe()

    def _observe(self):
        a = self.state["observations"][0]
        preds = [o for o in a["observations"] if o["type"] == "Predator"]
        seen = bool(preds)
        ag = self.agent
        if seen:
            p = min(preds, key=lambda o: o["distance"])
            self.pred_world = (ag.x + p["distance"] * math.cos(ag.direction + p["angle"]),
                               ag.y + p["distance"] * math.sin(ag.direction + p["angle"]))
            self.last_rel = p["rel_dir"]
        dx, dy = self.pred_world[0] - ag.x, self.pred_world[1] - ag.y
        ang = (math.atan2(dy, dx) - ag.direction + math.pi) % (2 * math.pi) - math.pi
        self.last_pred = (math.hypot(dx, dy), ang, self.last_rel)  # what the served policy reconstructs from m["pred"]
        self.status, self.seen = a, seen
        return featurize(a, self.last_pred, seen)

    def step(self, move):
        """move = (dist, direction, turn) as the served policy emits them. Returns (obs, reward, done)."""
        a, e0 = self.status, self.agent.energy
        req = ActionRequest(agent_id=a["agent_id"], move_distance=float(move[0]), move_direction=float(move[1]),
                            turn_angle=float(move[2]), spawn_agent=False)
        self.state = self.sim.step([(a["agent_id"], req)])
        self.ticks += 1
        if not self.env.agents:
            self.spent += e0
            return None, -DEATH, True
        self.spent += e0 - self.agent.energy
        reward = -(e0 - self.agent.energy) / 100
        self.far = self.far + 1 if math.hypot(self.pred.x - self.agent.x, self.pred.y - self.agent.y) > FAR else 0
        done = self.pred.resting or self.far >= FAR_TICKS or self.ticks >= MAX_TICKS
        return self._observe(), reward, done


def run_episode(env, i, make_policy):
    """One duel with common random numbers (episode i is always the same setup). Policy: fn(agent_status, env) -> move."""
    rng = random.Random(i)
    policy = make_policy()
    obs = env.reset(rng)
    total, done = 0.0, False
    while not done:
        obs, r, done = env.step(policy(env.status, env))
        total += r
    return dict(i=i, dead=obs is None, spent=env.spent, ticks=env.ticks, reward=total)


_envs = {}


def _env_for(i):
    """Per-process cached env for episode i (maps cycle through SEEDS)."""
    seed = SEEDS[i % len(SEEDS)]
    if seed not in _envs:
        _envs[seed] = DuelEnv(seed)
    return _envs[seed]


def _worker(args):
    i, make_policy = args
    return run_episode(_env_for(i), i, make_policy)


def evaluate_policy(make_policy, n=300, workers=None):
    """Mean over n fixed duel setups: dict(reward, death_rate, spent). `make_policy` must be picklable (module-level)."""
    from multiprocessing import Pool
    with Pool(workers) as pool:
        rows = pool.map(_worker, [(i, make_policy) for i in range(n)])
    return dict(reward=sum(r["reward"] for r in rows) / n, death_rate=sum(r["dead"] for r in rows) / n,
                spent=sum(r["spent"] for r in rows) / n, ticks=sum(r["ticks"] for r in rows) / n)


def served_rule():
    """The policy that is actually served, run on the duel state (spawning disabled)."""
    from src.utils.controllers.simple_policy import Hivemind
    hm = Hivemind()

    def act(a, env):
        step = {"sim_time": env.env.time, "score": 0.0, "agent_status": [a]}
        r = hm.decide(step)[0]
        return r.move_distance, r.move_direction, r.turn_angle
    return act


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    print("served rule:", evaluate_policy(served_rule, n))
