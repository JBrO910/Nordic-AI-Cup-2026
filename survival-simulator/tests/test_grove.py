"""python tests/test_grove.py — relocation prefers a spot next to several fruiting trees over a lone one."""
import math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from src.utils.controllers.hivemind_policy import Hivemind


def agent():
    return dict(agent_id=0, energy=200.0, biome="forest", age=10.0, speed=10.0, sprint_speed=20.0, hearing_radius=50.0,
                vision_angle=math.pi / 3, vision_range=200.0, max_energy=500.0, observations=[])


def setup():
    hm = Hivemind(); hm.tick = 1000
    m = hm._mem(0); m["x"], m["y"], m["h"], m["err"] = 500.0, 500.0, 0.0, 0.0
    m["fruit_tick"] = 0  # patch has been quiet: relocate
    fruiting = hm.tick - 10
    hm.trees = [[300.0, 500.0, hm.tick, fruiting],                       # lone tree, 200 px west
                [700.0, 500.0, hm.tick, fruiting], [740.0, 530.0, hm.tick, fruiting], [720.0, 460.0, hm.tick, fruiting]]  # grove, 200 px east
    return hm, m


def test_grove_beats_lone_tree_at_equal_distance():
    hm, m = setup()
    dist, rel, turn = hm._relocate_to_tree(agent(), m)
    assert abs(rel) < 0.3, f"expected to head east (rel≈0), got rel={rel:.2f}"  # heading 0 = +x = toward the grove


def test_lone_fruiting_tree_beats_barren_grove():
    hm, m = setup()
    for tr in hm.trees[1:]:
        tr[3] = -10**9  # grove never showed fruit
    dist, rel, turn = hm._relocate_to_tree(agent(), m)
    assert abs(abs(rel) - math.pi) < 0.3, f"expected to head west, got rel={rel:.2f}"


if __name__ == "__main__":
    test_grove_beats_lone_tree_at_equal_distance(); test_lone_fruiting_tree_beats_barren_grove(); print("ok")
