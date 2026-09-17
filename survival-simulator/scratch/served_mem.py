import sys; sys.path.insert(0, "."); sys.path.insert(0, "scratch")
import duel_env, src.utils.controllers.simple_policy as sp
def make20(): sp.FLEE_MEMORY = 20; return duel_env.served_rule()
def make60(): sp.FLEE_MEMORY = 60; return duel_env.served_rule()
def make150(): sp.FLEE_MEMORY = 150; return duel_env.served_rule()
if __name__ == "__main__":
    for mk in (make20, make60, make150):
        print(mk.__name__, duel_env.evaluate_policy(mk, 300))
