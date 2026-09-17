"""(1+lambda) evolution search over simple_policy's flee constants on the duel objective (common random numbers).
python scratch/tune_flee.py [generations] [n_duels]   -> prints the best constants; paste them into simple_policy.py."""
import sys, math, random
sys.path.insert(0, ".")
import duel_env
import src.utils.controllers.simple_policy as sp

SPACE = dict(CHARGE_DIST=(40, 200), CHARGE_RELEASE=(40, 300), SEEN_DIST=(20, 150), SEEN_ANGLE=(0.2, math.pi),
             FLEE_SPEED=(0.0, 1.0), FLEE_MEMORY=(0, 60))


def score(params, n):
    for k, v in params.items():
        setattr(sp, k, v)
    rows = [duel_env.run_episode(duel_env._env_for(i), i, duel_env.served_rule) for i in range(n)]
    return sum(r["reward"] for r in rows) / n, sum(r["dead"] for r in rows) / n, sum(r["spent"] for r in rows) / n


def _worker(args):
    params, n = args
    return params, score(params, n)


def mutate(p, rng, sigma=0.15):
    q = {k: min(hi, max(lo, v + rng.gauss(0, sigma * (hi - lo)))) for k, (lo, hi) in SPACE.items() for v in [p[k]]}
    q["CHARGE_RELEASE"] = max(q["CHARGE_RELEASE"], q["CHARGE_DIST"])
    q["FLEE_MEMORY"] = int(round(q["FLEE_MEMORY"]))
    return q


if __name__ == "__main__":
    from multiprocessing import Pool
    gens, n = int(sys.argv[1]) if len(sys.argv) > 1 else 20, int(sys.argv[2]) if len(sys.argv) > 2 else 300
    rng = random.Random(0)
    parent = {k: getattr(sp, k) for k in SPACE}
    with Pool() as pool:
        (_, base), (_, base2) = pool.map(_worker, [(parent, n), (parent, n)])
        print(f"baseline {base}  repeat {base2}  (noise check)")
        best = base
        for g in range(gens):
            cands = [mutate(parent, rng) for _ in range(22)]
            res = pool.map(_worker, [(c, n) for c in cands])
            c, s = max(res, key=lambda r: r[1][0])
            if s[0] > best[0]:
                parent, best = c, s
            print(f"gen {g:2d} best {best[0]:.3f} death {best[1]:.3f} spent {best[2]:.1f} | "
                  + " ".join(f"{k}={v:.2f}" for k, v in parent.items()), flush=True)
    print("BEST", parent, best)
