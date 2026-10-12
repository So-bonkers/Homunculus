"""ComfyUI custom node (copied into ComfyUI/custom_nodes by gpu.comfy_start): works around a segmentation fault on AMD/ROCm.

ComfyUI switches cuDNN (MIOpen on ROCm) off at import. With it off, PyTorch's fallback for a 3D convolution whose kernel equals its stride and its input size (the Qwen3-VL / Qwen3.5-VL vision
patch embedding: every sample is one patch) SEGFAULTS, which killed ComfyUI the first time a Qwen-Image 2.1 graph encoded a reference picture (TextEncodeQwenImage21). That convolution is exactly a
matrix multiply, so it is done as one: same numbers (max difference 5e-6 on values around 0.5), no native convolution kernel. Every other 3D convolution is untouched.
"""
import torch
import torch.nn.functional as F

_orig_conv3d = F.conv3d


def _conv3d(input, weight, bias=None, stride=1, padding=0, dilation=1, groups=1):
    k = tuple(weight.shape[2:])
    st = (stride,) * 3 if isinstance(stride, int) else tuple(stride)
    pd = (padding,) * 3 if isinstance(padding, int) else padding
    dl = (dilation,) * 3 if isinstance(dilation, int) else tuple(dilation)
    if (isinstance(pd, tuple) and all(p == 0 for p in pd) and dl == (1, 1, 1) and groups == 1 and st == k and input.dim() == 5 and tuple(input.shape[2:]) == k):
        out = input.reshape(input.shape[0], -1) @ weight.reshape(weight.shape[0], -1).t()
        if bias is not None: out = out + bias
        return out.reshape(input.shape[0], weight.shape[0], 1, 1, 1)
    return _orig_conv3d(input, weight, bias, stride, padding, dilation, groups)


if getattr(torch.version, "hip", None):
    F.conv3d = _conv3d

NODE_CLASS_MAPPINGS = {}
