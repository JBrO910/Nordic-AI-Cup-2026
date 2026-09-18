"""Learned evasion sub-policy: fixed feature vector -> tiny MLP (numpy) -> (move_distance, move_direction, turn).
Trained by scratch/train_flee.py on scratch/duel_env.py; weights in flee_weights.npz next to this file."""
import math, os
import numpy as np

BIOME_PENALTY = {"swamp": 0.5, "desert": 0.8, "river": 0.3}
N_DIR = 8
HEADS = (3, N_DIR, 3)
OBS_DIM = 16
WEIGHTS = os.environ.get("FLEE_WEIGHTS", os.path.join(os.path.dirname(__file__), "flee_weights.npz"))


def nearest_edge(edges):
    """(distance, bearing) of the closest point on any visible edge, in the agent frame; (999, 0) if none."""
    best, bx, by = float("inf"), 0.0, 0.0
    for (x1, y1), (x2, y2) in edges:
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        u = 0.0 if l2 == 0 else max(0.0, min(1.0, -(x1 * dx + y1 * dy) / l2))
        px, py = x1 + u * dx, y1 + u * dy
        d = math.hypot(px, py)
        if d < best:
            best, bx, by = d, px, py
    return (best, math.atan2(by, bx)) if best < float("inf") else (999.0, 0.0)


def featurize(a, pred, seen):
    """OBS_DIM floats from a real agent_status dict. `pred` = (distance, angle, rel_dir) of the closest predator,
    or its last known values when not currently observed (`seen` False)."""
    d, ang, rel = pred
    ed, eang = nearest_edge([o["coords"] for o in a["observations"] if o["type"] == "Edge"])
    others = sorted(o["distance"] for o in a["observations"] if o["type"] == "Predator")[1 if seen else 0:]
    if others:  # second-closest visible predator (v2 feature; zero rows in v1 weights)
        o2 = next(o for o in a["observations"] if o["type"] == "Predator" and o["distance"] == others[0])
        d2, a2, p2 = min(o2["distance"], 400) / 250, o2["angle"], 1.0
    else:
        d2, a2, p2 = 400 / 250, 0.0, 0.0
    return np.array([min(d, 400) / 250, math.cos(ang), math.sin(ang), math.cos(rel), math.sin(rel),
                     a["energy"] / a["max_energy"], float(a["energy"] > 0.2 * a["max_energy"] + 5),
                     min(ed, 200) / 100, math.cos(eang), math.sin(eang),
                     BIOME_PENALTY.get(a["biome"], 1.0), float(seen),
                     d2, math.cos(a2) * p2, math.sin(a2) * p2, p2], dtype=np.float32)


def decode(action, a, pred):
    """MultiDiscrete (speed 0|walk|sprint, direction bin relative to predator bearing, turn 0|face|+cone) -> raw move."""
    s, k, t = action
    return (0.0, a["speed"], a["sprint_speed"])[s], pred[1] + k * 2 * math.pi / N_DIR, (0.0, pred[1], a["vision_angle"])[t]


def forward(W, x):
    """Per-head logits."""
    h = np.tanh(x @ W["W1"] + W["b1"])
    h = np.tanh(h @ W["W2"] + W["b2"])
    return [h @ W[f"Wh{k}"] + W[f"bh{k}"] for k in range(len(HEADS))]


def greedy(W, obs):
    return tuple(int(np.argmax(l)) for l in forward(W, obs))


def load():
    return dict(np.load(WEIGHTS))


def act(W, a, pred, seen):
    """(move_distance, move_direction, turn_angle) for one agent_status dict."""
    return decode(greedy(W, featurize(a, pred, seen)), a, pred)
