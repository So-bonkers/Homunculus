#!/bin/sh
# fit the base body to every character listed (one mesh path per line): tools/base_body/fit_all.sh LIST.txt [parallel]
cd "$(dirname "$0")/../.."
cat "$1" | xargs -P "${2:-4}" -I{} sh -c 'f={}; n=$(echo $f | sed "s|runs/\([^/]*\)/.*|\1|"); [ -f runs/base_fits/$n/fit.npz ] || gvhmr/.venv/bin/python tools/base_body/fit_base.py $f runs/base_fits/$n --iters 120 --offset-iters 120 > runs/base_fits/$n.log 2>&1'
