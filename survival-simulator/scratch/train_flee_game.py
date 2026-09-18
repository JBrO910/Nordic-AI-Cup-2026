"""PPO for the flee net on full games (scratch/game_env.py): each iteration 20 workers play one real game each with
sampled flee actions, the update runs in the parent. Every EVAL_EVERY iterations the greedy net plays 24 games; the best
mean survived is saved. python scratch/train_flee_game.py [iterations] [init.npz] [out.npz]"""
import sys, time
sys.path.insert(0, "."); sys.path.insert(0, "scratch")
import numpy as np
from multiprocessing import Pool
from src.utils.controllers.flee_net import WEIGHTS
import game_env

WORKERS, SEEDS, EVAL_EVERY, EVAL_SEEDS = 20, list(range(1, 25)), int(__import__("os").environ.get("EVAL_EVERY", 10)), list(range(1, 25))
GAME_TIMEOUT = 1500   # s wall for one map() of games; a hung worker costs one iteration, not the night


def _play(args):
    W, seed, rng_seed, sample = args
    r = game_env.play_game(W, seed, 3000.0, sample=sample, rng_seed=rng_seed)
    return r if sample else (r["survived"], r["kills"])


if __name__ == "__main__":
    import torch
    from ppo import Net, ppo_update
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    init = sys.argv[2] if len(sys.argv) > 2 else WEIGHTS
    out = sys.argv[3] if len(sys.argv) > 3 else "scratch/flee_weights_game.npz"
    torch.manual_seed(0)
    net = Net(); net.load_numpy(dict(np.load(init)))
    opt = torch.optim.Adam(net.parameters(), lr=1e-4)
    best, pool = -1.0, Pool(WORKERS)
    print(f"init {init} -> {out}, {iters} iters x {WORKERS} games", flush=True)
    for it in range(iters):
        t0 = time.time()
        W = net.numpy()
        jobs = [(W, SEEDS[(it * WORKERS + w) % len(SEEDS)], it * 1000 + w, True) for w in range(WORKERS)]
        try:
            games = pool.map_async(_play, jobs).get(timeout=GAME_TIMEOUT)
        except Exception as e:   # multiprocessing.TimeoutError or a worker crash: rebuild the pool, skip the iteration
            print(f"it {it:3d} rollout failed ({type(e).__name__}); rebuilding pool", flush=True)
            pool.terminate(); pool = Pool(WORKERS)
            continue
        games = [g for g in games if g["steps"] > 0]
        obs = np.concatenate([g["obs"] for g in games]); acts = np.concatenate([g["acts"] for g in games])
        rews = np.concatenate([g["rews"] for g in games]); dones = np.concatenate([g["dones"] for g in games])
        ppo_update(net, opt, obs, acts, rews, dones)
        n_eps, deaths = int(dones.sum()), int((rews <= -game_env.DEATH).sum())
        surv = sum(g["survived"] for g in games) / len(games)
        msg = (f"it {it:3d} steps {len(rews):6d} eps {n_eps:4d} ep_reward {rews.sum() / max(n_eps, 1):7.3f} "
               f"deaths/ep {deaths / max(n_eps, 1):.3f} sampled survived {surv:6.0f} {time.time() - t0:5.0f}s")
        if it % EVAL_EVERY == EVAL_EVERY - 1:
            W = net.numpy()
            try:
                ev = pool.map_async(_play, [(W, s, 0, False) for s in EVAL_SEEDS]).get(timeout=GAME_TIMEOUT)
                m = sum(s for s, k in ev) / len(ev); kills = sum(k for s, k in ev) / len(ev)
                msg += f" | EVAL survived {m:6.0f} kills {kills:5.1f}"
                if m > best:
                    best = m; np.savez(out, **W); msg += " *saved*"
            except Exception as e:
                msg += f" | EVAL failed ({type(e).__name__})"; pool.terminate(); pool = Pool(WORKERS)
        print(msg, flush=True)
