"""PPO core shared by the duel trainer and the in-game trainer: torch Net <-> numpy weights, GAE, clipped update."""
import numpy as np
import torch, torch.nn as nn
from src.utils.controllers.flee_net import OBS_DIM, HEADS, forward

HID = 64


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

    def load_numpy(self, W0):
        with torch.no_grad():
            self.l1.weight.copy_(torch.from_numpy(W0["W1"].T)); self.l1.bias.copy_(torch.from_numpy(W0["b1"]))
            self.l2.weight.copy_(torch.from_numpy(W0["W2"].T)); self.l2.bias.copy_(torch.from_numpy(W0["b2"]))
            for k, hd in enumerate(self.heads):
                hd.weight.copy_(torch.from_numpy(W0[f"Wh{k}"].T)); hd.bias.copy_(torch.from_numpy(W0[f"bh{k}"]))


def logp_ent(logits, acts):
    lp, ent = 0.0, 0.0
    for k, l in enumerate(logits):
        d = torch.distributions.Categorical(logits=l)
        lp = lp + d.log_prob(acts[:, k]); ent = ent + d.entropy()
    return lp, ent


def sample_action(W, obs, rng):
    """One MultiDiscrete action from the numpy net (rollout side)."""
    out = []
    for n, l in zip(HEADS, forward(W, obs)):
        p = np.exp(l - l.max()); out.append(int(rng.choice(n, p=p / p.sum())))
    return tuple(out)


def ppo_update(net, opt, obs, acts, rews, dones, gamma=0.99, lam=0.95, clip=0.2, epochs=4, mb=4096, ent_coef=0.01):
    """obs (N,OBS_DIM) f32, acts (N,3) i64, rews (N,) f32, dones (N,) bool; episodes concatenated, dones marks each last step."""
    obs, acts = torch.from_numpy(obs), torch.from_numpy(acts)
    with torch.no_grad():
        logits, vals = net(obs)
        old_lp, _ = logp_ent(logits, acts)
    vals = vals.numpy()
    adv, last = np.zeros_like(rews), 0.0
    for t in reversed(range(len(rews))):
        nv = 0.0 if dones[t] else vals[t + 1]
        delta = rews[t] + gamma * nv - vals[t]
        last = delta + gamma * lam * (0.0 if dones[t] else last)
        adv[t] = last
    ret = torch.from_numpy(adv + vals); adv = torch.from_numpy(adv)
    adv = (adv - adv.mean()) / (adv.std() + 1e-8)
    for _ in range(epochs):
        for idx in torch.randperm(len(rews)).split(mb):
            logits, v = net(obs[idx])
            lp, ent = logp_ent(logits, acts[idx])
            ratio = torch.exp(lp - old_lp[idx])
            pl = -torch.min(ratio * adv[idx], torch.clamp(ratio, 1 - clip, 1 + clip) * adv[idx]).mean()
            loss = pl + 0.5 * ((v - ret[idx]) ** 2).mean() - ent_coef * ent.mean()
            opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(net.parameters(), 0.5); opt.step()
