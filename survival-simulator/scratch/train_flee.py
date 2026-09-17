"""PPO for the evasion sub-policy on DuelEnv. Rollouts: pool workers run whole episodes with a numpy copy of the
weights; the update runs in the parent (torch, CPU). Best fixed-setup eval is saved to
src/utils/controllers/flee_weights.npz (numpy forward pass at serve time, no torch).
python scratch/train_flee.py [iterations] [resume]   (resume: continue from the saved weights)"""
import sys, random, time
sys.path.insert(0, ".")
import numpy as np
import duel_env
from src.utils.controllers.flee_net import OBS_DIM, HEADS, WEIGHTS, forward, decode, act as net_act

HID = 64
TRAIN_BASE = 10_000  # training setups never overlap the 0..n eval setups


def net_policy(W):
    """make_policy-compatible factory (called inside the worker)."""
    def make():
        return lambda a, env: net_act(W, a, env.last_pred, env.seen)
    return make


def _rollout(args):
    W, first, count = args
    rng = np.random.default_rng(first)
    obs_l, act_l, rew_l, done_l = [], [], [], []
    for i in range(first, first + count):
        env = duel_env._env_for(i)
        obs = env.reset(random.Random(TRAIN_BASE + i))
        done = False
        while not done:
            logits = forward(W, obs)
            a = tuple(int(rng.choice(n, p=np.exp(l - l.max()) / np.exp(l - l.max()).sum())) for n, l in zip(HEADS, logits))
            move = decode(a, env.status, env.last_pred)
            nobs, r, done = env.step(move)
            obs_l.append(obs); act_l.append(a); rew_l.append(r); done_l.append(done)
            obs = nobs if nobs is not None else obs
    return np.array(obs_l, np.float32), np.array(act_l, np.int64), np.array(rew_l, np.float32), np.array(done_l, bool)


def _eval(args):
    W, first, count = args
    return [duel_env.run_episode(duel_env._env_for(i), i, net_policy(W)) for i in range(first, first + count)]


if __name__ == "__main__":
    import torch, torch.nn as nn
    from multiprocessing import Pool
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    torch.manual_seed(0)
    WORKERS, EPS_PER_WORKER, N_EVAL = 20, 24, 300
    GAMMA, LAM, CLIP, EPOCHS, MB, LR, ENT = 0.99, 0.95, 0.2, 4, 4096, 2e-4, 0.01

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.l1, self.l2 = nn.Linear(OBS_DIM, HID), nn.Linear(HID, HID)
            self.heads = nn.ModuleList([nn.Linear(HID, n) for n in HEADS])
            self.v = nn.Linear(HID, 1)

        def forward(self, x):
            h = torch.tanh(self.l2(torch.tanh(self.l1(x))))
            return [hd(h) for hd in self.heads], self.v(h).squeeze(-1)

        def numpy(self):
            W = {"W1": self.l1.weight.T, "b1": self.l1.bias, "W2": self.l2.weight.T, "b2": self.l2.bias}
            for k, hd in enumerate(self.heads):
                W[f"Wh{k}"], W[f"bh{k}"] = hd.weight.T, hd.bias
            return {k: v.detach().numpy().astype(np.float32).copy() for k, v in W.items()}

    def logp_ent(logits, acts):
        lp, ent = 0.0, 0.0
        for k, l in enumerate(logits):
            d = torch.distributions.Categorical(logits=l)
            lp = lp + d.log_prob(acts[:, k]); ent = ent + d.entropy()
        return lp, ent

    net = Net(); opt = torch.optim.Adam(net.parameters(), lr=LR)
    if len(sys.argv) > 2 and sys.argv[2] == "resume":
        W0 = np.load(WEIGHTS)
        with torch.no_grad():
            net.l1.weight.copy_(torch.from_numpy(W0["W1"].T)); net.l1.bias.copy_(torch.from_numpy(W0["b1"]))
            net.l2.weight.copy_(torch.from_numpy(W0["W2"].T)); net.l2.bias.copy_(torch.from_numpy(W0["b2"]))
            for k, hd in enumerate(net.heads):
                hd.weight.copy_(torch.from_numpy(W0[f"Wh{k}"].T)); hd.bias.copy_(torch.from_numpy(W0[f"bh{k}"]))
    best, ep_counter = -1e9, 0
    with Pool(WORKERS) as pool:
        for it in range(iters):
            t0 = time.time()
            W = net.numpy()
            parts = pool.map(_rollout, [(W, ep_counter + w * EPS_PER_WORKER, EPS_PER_WORKER) for w in range(WORKERS)])
            ep_counter += WORKERS * EPS_PER_WORKER
            obs = torch.from_numpy(np.concatenate([p[0] for p in parts]))
            acts = torch.from_numpy(np.concatenate([p[1] for p in parts]))
            rews = np.concatenate([p[2] for p in parts]); dones = np.concatenate([p[3] for p in parts])
            with torch.no_grad():
                logits, vals = net(obs)
                old_lp, _ = logp_ent(logits, acts)
            vals = vals.numpy()
            adv, last = np.zeros_like(rews), 0.0   # GAE; episodes are concatenated, `dones` marks the last step of each
            for t in reversed(range(len(rews))):
                nv = 0.0 if dones[t] else vals[t + 1]
                delta = rews[t] + GAMMA * nv - vals[t]
                last = delta + GAMMA * LAM * (0.0 if dones[t] else last)
                adv[t] = last
            ret = torch.from_numpy(adv + vals); adv = torch.from_numpy(adv)
            adv = (adv - adv.mean()) / (adv.std() + 1e-8)
            n = len(rews)
            for _ in range(EPOCHS):
                for idx in torch.randperm(n).split(MB):
                    logits, v = net(obs[idx])
                    lp, ent = logp_ent(logits, acts[idx])
                    ratio = torch.exp(lp - old_lp[idx])
                    pl = -torch.min(ratio * adv[idx], torch.clamp(ratio, 1 - CLIP, 1 + CLIP) * adv[idx]).mean()
                    loss = pl + 0.5 * ((v - ret[idx]) ** 2).mean() - ENT * ent.mean()
                    opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(net.parameters(), 0.5); opt.step()
            n_eps = int(dones.sum())
            msg = f"it {it:3d} steps {n:6d} eps {n_eps:3d} mean_ep_reward {rews.sum() / n_eps:7.3f} deaths {(rews <= -duel_env.DEATH).sum() / n_eps:.3f} {time.time() - t0:4.1f}s"
            if it % 10 == 9:
                W = net.numpy()
                per = N_EVAL // WORKERS
                rows = sum(pool.map(_eval, [(W, w * per, per) for w in range(WORKERS)]), [])
                m = len(rows)
                ev = dict(reward=sum(r["reward"] for r in rows) / m, death_rate=sum(r["dead"] for r in rows) / m,
                          spent=sum(r["spent"] for r in rows) / m)
                msg += f" | EVAL reward {ev['reward']:.3f} death {ev['death_rate']:.3f} spent {ev['spent']:.1f}"
                if ev["reward"] > best:
                    best = ev["reward"]; np.savez(WEIGHTS, **W); msg += " *saved*"
            print(msg, flush=True)
