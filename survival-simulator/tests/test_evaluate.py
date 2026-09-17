"""Harness self-check: python tests/test_evaluate.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import evaluate


def test_load_policy_and_run():
    for spec in ("src.utils.controllers.dummy_agent_policy:dummy", "src.utils.controllers.hivemind_policy:Hivemind"):
        r = evaluate.run_seed((1, spec, 20.0))
        assert r["survived"] > 0 and "kills" in r and "score" in r, r
        assert isinstance(r["kills"], int)


def test_seed_list_repeat():
    jobs = evaluate.jobs([1, 2], "x", 5.0, repeat=2)
    assert [j[0] for j in jobs] == [1, 2, 1, 2]
    assert evaluate.DEFAULT_SEEDS == list(range(1, 13))


if __name__ == "__main__":
    test_seed_list_repeat()
    test_load_policy_and_run()
    print("ok")
