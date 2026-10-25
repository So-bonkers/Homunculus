"""nvdiffrast.torch stand-in (ROCm): rasterize() for flat 2D layouts (no depth test: UV charts do not overlap) and interpolate(), vectorised in torch.
Convention as nvdiffrast: pixel centres at ((x + 0.5) / W * 2 - 1, (y + 0.5) / H * 2 - 1), row 0 at clip y = -1; rast[..., 0:2] = barycentric weights of the triangle's first two vertices, rast[..., 2] = z/w, rast[..., 3] = triangle index + 1 (0 = empty)."""
import torch
class RasterizeCudaContext:
    def __init__(self, *a, **k): pass
RasterizeGLContext = RasterizeCudaContext
def rasterize(ctx, pos, tri, resolution, ranges=None, grad_db=False):
    H, W = resolution; dev = pos.device; P = pos[0]; tri = tri.long(); out = torch.zeros(1, H, W, 4, device=dev)
    xy = P[:, :2] / P[:, 3:4]; px = (xy[:, 0] + 1) * 0.5 * W - 0.5; py = (xy[:, 1] + 1) * 0.5 * H - 0.5; z = P[:, 2] / P[:, 3]
    for s in range(0, tri.shape[0], 20000):
        t = tri[s:s + 20000]; X = px[t]; Y = py[t]
        x0 = X.min(1).values.ceil().clamp(0, W - 1).long(); x1 = X.max(1).values.floor().clamp(0, W - 1).long(); y0 = Y.min(1).values.ceil().clamp(0, H - 1).long(); y1 = Y.max(1).values.floor().clamp(0, H - 1).long()
        bw = (x1 - x0 + 1).clamp(min=0); bh = (y1 - y0 + 1).clamp(min=0); n = bw * bh; keep = n > 0
        if not keep.any(): continue
        ti = torch.repeat_interleave(torch.nonzero(keep)[:, 0], n[keep]); start = torch.cumsum(n[keep], 0) - n[keep]; loc = torch.arange(int(n[keep].sum()), device=dev) - torch.repeat_interleave(start, n[keep])
        cx = x0[ti] + loc % bw[ti]; cy = y0[ti] + loc // bw[ti]; fx = cx.float(); fy = cy.float()
        ax, ay, bx, by, qx, qy = X[ti, 0], Y[ti, 0], X[ti, 1], Y[ti, 1], X[ti, 2], Y[ti, 2]
        den = (by - qy) * (ax - qx) + (qx - bx) * (ay - qy); ok = den.abs() > 1e-12; den = torch.where(ok, den, torch.ones_like(den))
        w0 = ((by - qy) * (fx - qx) + (qx - bx) * (fy - qy)) / den; w1 = ((qy - ay) * (fx - qx) + (ax - qx) * (fy - qy)) / den; w2 = 1 - w0 - w1
        e = -1e-5; inside = ok & (w0 >= e) & (w1 >= e) & (w2 >= e)
        if not inside.any(): continue
        ti, cx, cy, w0, w1 = ti[inside], cx[inside], cy[inside], w0[inside], w1[inside]; g = t[ti]; zz = w0 * z[g[:, 0]] + w1 * z[g[:, 1]] + (1 - w0 - w1) * z[g[:, 2]]
        out[0, cy, cx] = torch.stack([w0, w1, zz, (ti + s + 1).float()], 1)          # global triangle index (+1), not the index inside this batch
    return out, None
def interpolate(attr, rast, tri, rast_db=None, diff_attrs=None):
    A = attr[0] if attr.dim() == 3 else attr; tri = tri.long(); id_ = rast[..., 3].long() - 1; m = id_ >= 0; out = torch.zeros(rast.shape[:3] + (A.shape[-1],), device=A.device, dtype=A.dtype)
    t = tri[id_[m]]; w0 = rast[..., 0][m][:, None]; w1 = rast[..., 1][m][:, None]
    out[m] = w0 * A[t[:, 0]] + w1 * A[t[:, 1]] + (1 - w0 - w1) * A[t[:, 2]]; return out, None
