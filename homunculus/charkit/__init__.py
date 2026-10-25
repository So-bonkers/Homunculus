"""charkit: the staged, resumable character-kit pipeline (reference picture -> clean head and body -> kit pictures -> TRELLIS.2 meshes -> placed and assembled), with local judges
for the routine calls and a review queue (kits/<name>/needs_review.json) for the rest. Run it as `python -m homunculus.charkit`; the stages are in stages.py, the rules in docs/CHARKIT.md.
Modules: pipeline (state, GPU lock phases, review queue, runner), stages, gates (numeric checks), judge (VLM batching, JSON parsing, stub), jobs (heavy jobs, replay), prompts."""
