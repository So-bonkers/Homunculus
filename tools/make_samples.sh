#!/usr/bin/env bash
# Sample GIFs for the README: blender renders frames of a preset clip, ffmpeg makes the GIF.  tools/make_samples.sh
set -e; cd "$(dirname "$0")/.."; T=$(mktemp -d)
gif() { # clip.glb out.gif
  rm -rf "$T/f"; blender -b --python tools/render_clip.py -- "$(realpath "$1")" "$T/f" 360 2 >/dev/null 2>&1
  ffmpeg -loglevel error -y -framerate 15 -i "$T/f/f%03d.png" -vf "split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4" -loop 0 "$2"; }
pid() { python3 -c "import hashlib,sys;print(hashlib.sha1(sys.argv[1].encode()).hexdigest()[:10])" "$1"; }
mkdir -p docs/media
while IFS='|' read -r slug prompt; do
  for m in male female; do gif "homunculus/static/presets/clips/$m/$(pid "$prompt")_1.glb" "docs/media/${slug}_$m.gif"; done
done <<'L'
walk|walks forward
spinning-kick|does a spinning kick
hip-hop|dances hip hop, bouncing and swinging the arms
salsa|dances salsa, stepping side to side and swaying the hips
sword|slashes forward with a sword
jump|jumps forward
L
# a finished pipeline run (picture -> textured rigged character -> text-driven clips): pass the run folder
if [ -n "${1:-}" ]; then for f in "$1"/09_animate/clips/*_1_tex.glb; do n=$(basename "$f" _003024_1_tex.glb | sed 's/an_object_//'); gif "$f" "docs/media/run_${n:0:24}.gif"; done; fi
