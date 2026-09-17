"""python tests/test_stuck_metric.py — the stuck metric script exposes measure() with the agreed shape."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scratch"))
import stuck


def test_measure_shape():
    r = stuck.measure(seed=3, max_time=40.0)
    assert 0.0 <= r["stuck_fraction"] <= 1.0
    assert isinstance(r["by_mode"], dict) and all(0.0 <= v[0] <= 1.0 for v in r["by_mode"].values())
    assert r["longest_streak"][0] >= 0 and isinstance(r["longest_streak"][1], str)
    assert "by_biome" in r


if __name__ == "__main__":
    test_measure_shape(); print("ok")
