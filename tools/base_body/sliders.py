"""Slider definitions from the stock target names: opposite targets are paired into one bipolar slider (-1 .. +1), single shapes stay unipolar (0 .. 1), left and right stay separate (the fit ties them softly).
    defs(names) -> list of dicts {name, group, side, lo, hi, neg: target index or -1, pos: target index or -1}
Pairs: decr/incr, down/up, in/out, backward/forward, compress/uncompress, concave/convex (the first is the negative end)."""
PAIRS = [("decr", "incr"), ("down", "up"), ("in", "out"), ("backward", "forward"), ("compress", "uncompress"), ("concave", "convex")]
def defs(names):
    idx = {n: i for i, n in enumerate(names)}; used = set(); out = []
    for n in names:
        if n in used: continue
        d, rest = n.split("/", 1); stem, _, suf = rest.rpartition("-"); pair = next((p for p in PAIRS if suf in p), None)
        side = "l" if stem.startswith("l-") else "r" if stem.startswith("r-") else ""
        if pair:
            a, b = f"{d}/{stem}-{pair[0]}", f"{d}/{stem}-{pair[1]}"
            if a in idx and b in idx and a not in used:
                used.update((a, b)); out.append(dict(name=f"{d}/{stem}", group=d, side=side, lo=-1.0, hi=1.0, neg=idx[a], pos=idx[b])); continue
        used.add(n); sd = "l" if rest.endswith("-l") or side == "l" else "r" if rest.endswith("-r") or side == "r" else ""
        out.append(dict(name=n, group=d, side=sd, lo=0.0, hi=1.0, neg=-1, pos=idx[n]))
    return out
