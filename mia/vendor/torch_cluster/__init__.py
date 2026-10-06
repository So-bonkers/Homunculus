"""Pure-PyTorch replacement for torch_cluster.fps (farthest point sampling)."""
import math, torch
def fps(src, batch=None, ratio=0.5, random_start=True, batch_size=None):
    if batch is None: batch = torch.zeros(src.shape[0], dtype=torch.long, device=src.device)
    out = []
    for b in torch.unique(batch, sorted=True):
        sel = torch.nonzero(batch == b, as_tuple=False).squeeze(1); P = src[sel].float(); n = P.shape[0]; m = max(1, int(math.ceil(ratio * n)))
        idx = torch.empty(m, dtype=torch.long, device=src.device); dist = torch.full((n,), float("inf"), device=src.device)
        cur = int(torch.randint(0, n, (1,)).item()) if random_start else 0
        for i in range(m):
            idx[i] = cur; d = ((P - P[cur]) ** 2).sum(1); dist = torch.minimum(dist, d); cur = int(torch.argmax(dist).item()) if i + 1 < m else cur
        out.append(sel[idx])
    return torch.cat(out)
