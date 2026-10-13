# Homunculus web app

React 19 + TypeScript + Vite + Tailwind 4, a dark studio interface for the pipeline. The built files are committed in `homunculus/static/ui/`, so running Homunculus needs only Python; Node is needed only to change the interface.

```bash
cd web
npm install
npm run build        # type-checks and writes ../homunculus/static/ui/ (served at http://127.0.0.1:8765/ui)
npm run dev          # hot reload on :5173, the API proxied to the Python server on :8765
```

- `src/lib/api.ts`, `types.ts`: the server's HTTP API and JSON shapes (homunculus/server.py, api.py).
- `src/viewer/Viewer.ts`: the three.js viewer (every model scaled to 1.8 units tall, standing on y = 0: the Repair and Retexture brushes depend on this frame).
- `src/features/run/brush.ts`: brush strokes as spheres `[x, y, z, r]` in the model root's own coordinates, as the server expects.
- The animation prompt library is read at run time from `homunculus/static/prompt_library.js` (also used by `preset_clips.py`).
- An open app reloads itself when a new build appears (`version.json`).
- `src/features/tour/Tour.tsx`: the guided tour. Steps point at `data-tour="…"` attributes and say which page they are on; a step whose target is missing (no runs yet) is skipped. Offered once on the first visit (`localStorage` `homunculus_tour_offered` / `homunculus_tour_done`).
- `src/features/animate/`: the dance-from-video job view (`/api/video/<run>`, stages with estimates and reports) and `SyncPlayer`, where the reference video is the clock that poses the 3D clip every frame. Seeking needs HTTP Range answers, which `server.py` gives for run files.
