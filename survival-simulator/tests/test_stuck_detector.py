"""python tests/test_stuck_detector.py — the pose snap-back stuck detector."""
import math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from src.utils.controllers.hivemind_policy import Hivemind, STUCK_SNAPS


def agent(aid=0, energy=200.0):
    return dict(agent_id=aid, energy=energy, biome="forest", age=10.0, speed=10.0, sprint_speed=20.0,
                hearing_radius=50.0, vision_angle=math.pi / 3, vision_range=200.0, max_energy=500.0, observations=[])


def test_snapback_marks_stuck_and_blacklists_target():
    hm = Hivemind(); a = agent(); m = hm._mem(0)
    m["x"], m["y"], m["h"], m["err"] = 100.0, 100.0, 0.0, 0.0
    m["target"] = 3; m["target_xy"] = (300.0, 100.0)
    for _ in range(STUCK_SNAPS):
        m["x"] += 10.0                     # dead-reckoning says we advanced 10 px...
        hm._note_snapback(a, m, 100.0, 100.0, 10.0)   # ...but the fix put us back where we were
    assert hm._is_blacklisted(m, 300.0, 100.0), "target position must be blacklisted"
    assert m["target"] is None and m["hop_until"] > hm.tick, "target dropped, hop started"


def test_real_movement_is_not_stuck():
    hm = Hivemind(); a = agent(); m = hm._mem(0)
    m["x"], m["y"], m["h"], m["err"] = 100.0, 100.0, 0.0, 0.0
    for _ in range(STUCK_SNAPS + 2):
        m["x"] += 10.0
        hm._note_snapback(a, m, m["x"] - 0.5, m["y"], 10.0)  # fix within 0.5 px: we really moved
    assert m["stuck"] == 0


def test_swamp_slow_movement_is_not_stuck():
    hm = Hivemind(); a = agent(); a["biome"] = "swamp"; m = hm._mem(0)
    m["x"], m["y"], m["h"], m["err"] = 100.0, 100.0, 0.0, 0.0
    for _ in range(STUCK_SNAPS + 2):
        m["x"] += 5.0                                   # biome-adjusted step is 5 px
        hm._note_snapback(a, m, m["x"] - 0.5, m["y"], 5.0)
    assert m["stuck"] == 0


if __name__ == "__main__":
    test_snapback_marks_stuck_and_blacklists_target(); test_real_movement_is_not_stuck(); test_swamp_slow_movement_is_not_stuck(); print("ok")
