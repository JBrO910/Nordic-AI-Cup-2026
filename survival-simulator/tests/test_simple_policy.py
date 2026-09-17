"""python tests/test_simple_policy.py — version-3 reconstruction sanity check."""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import evaluate

PATH = os.path.join(ROOT, "src", "utils", "controllers", "simple_policy.py")


def test_size_and_no_world_map():
    src = open(PATH, encoding="utf-8").read()
    assert len(src.splitlines()) <= 300, "must stay a small local policy"
    assert "landmark" not in src and "fix_from_edge" not in src


def test_runs_seeds():
    for seed in (1, 2, 3):
        r = evaluate.run_seed((seed, "src.utils.controllers.simple_policy:Hivemind", 60.0))
        assert r["survived"] >= 60, r


if __name__ == "__main__":
    test_size_and_no_world_map(); test_runs_seeds(); print("ok")
