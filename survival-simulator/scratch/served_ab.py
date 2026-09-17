"""Served policy on the duel objective, hand rule vs learned net (same 300 setups)."""
import sys; sys.path.insert(0, "."); sys.path.insert(0, "scratch")
import duel_env, src.utils.controllers.simple_policy as sp
def rule(): sp.FLEE_NET = None; return duel_env.served_rule()
def net(): return duel_env.served_rule()
if __name__ == "__main__":
    for mk in (rule, net):
        print(mk.__name__, duel_env.evaluate_policy(mk, 300))
