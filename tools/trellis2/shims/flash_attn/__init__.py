"""Stand-in for flash-attn's variable-length functions on ROCm (RDNA3 has no flash-attn build): the same signatures, computed with torch's scaled_dot_product_attention.
Sequences are padded to the longest one with a key-padding mask (one call), so many short windows cost one batched call. Exact, not approximate."""
import torch, torch.nn.functional as F
__version__ = "2.7.3-sdpa-shim"
def _varlen(q, k, v, cu_q, cu_k, max_q, max_k, softmax_scale=None, causal=False):
    B = cu_q.numel() - 1; H, D = q.shape[1], q.shape[2]
    if B == 1:
        o = F.scaled_dot_product_attention(q.transpose(0, 1)[None], k.transpose(0, 1)[None], v.transpose(0, 1)[None], scale=softmax_scale, is_causal=causal)
        return o[0].transpose(0, 1)
    lq = (cu_q[1:] - cu_q[:-1]).long(); lk = (cu_k[1:] - cu_k[:-1]).long(); dev = q.device
    def pad(x, lens, cu, L):
        pos = torch.arange(L, device=dev)[None, :]; valid = pos < lens[:, None]; out = x.new_zeros(B, L, x.shape[1], x.shape[2])
        idx = (cu[:-1].long()[:, None] + pos)[valid]; out[valid] = x[idx]; return out, valid
    Q, vq = pad(q, lq, cu_q, int(max_q)); K, vk = pad(k, lk, cu_k, int(max_k)); V, _ = pad(v, lk, cu_k, int(max_k))
    mask = vk[:, None, None, :]
    o = F.scaled_dot_product_attention(Q.transpose(1, 2), K.transpose(1, 2), V.transpose(1, 2), attn_mask=mask, scale=softmax_scale, is_causal=causal)
    return o.transpose(1, 2)[vq]
def flash_attn_varlen_func(q, k, v, cu_seqlens_q, cu_seqlens_k, max_seqlen_q, max_seqlen_k, dropout_p=0.0, softmax_scale=None, causal=False, **kw):
    return _varlen(q, k, v, cu_seqlens_q, cu_seqlens_k, max_seqlen_q, max_seqlen_k, softmax_scale, causal)
def flash_attn_varlen_kvpacked_func(q, kv, cu_seqlens_q, cu_seqlens_k, max_seqlen_q, max_seqlen_k, dropout_p=0.0, softmax_scale=None, causal=False, **kw):
    return _varlen(q, kv[:, 0], kv[:, 1], cu_seqlens_q, cu_seqlens_k, max_seqlen_q, max_seqlen_k, softmax_scale, causal)
def flash_attn_varlen_qkvpacked_func(qkv, cu_seqlens, max_seqlen, dropout_p=0.0, softmax_scale=None, causal=False, **kw):
    return _varlen(qkv[:, 0], qkv[:, 1], qkv[:, 2], cu_seqlens, cu_seqlens, max_seqlen, max_seqlen, softmax_scale, causal)
def flash_attn_func(q, k, v, dropout_p=0.0, softmax_scale=None, causal=False, **kw):     # [B, L, H, D]
    return F.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2), scale=softmax_scale, is_causal=causal).transpose(1, 2)
def flash_attn_qkvpacked_func(qkv, dropout_p=0.0, softmax_scale=None, causal=False, **kw): return flash_attn_func(qkv[:, :, 0], qkv[:, :, 1], qkv[:, :, 2], softmax_scale=softmax_scale, causal=causal)
def flash_attn_kvpacked_func(q, kv, dropout_p=0.0, softmax_scale=None, causal=False, **kw): return flash_attn_func(q, kv[:, :, 0], kv[:, :, 1], softmax_scale=softmax_scale, causal=causal)
