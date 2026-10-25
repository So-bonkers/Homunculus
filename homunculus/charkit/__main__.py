"""charkit: one reference picture of a character -> the parts of a character kit (clean head, clean body, base body and every garment/shoe/hair/accessory as its own picture and
TRELLIS.2 mesh, placed on a dressed reference and assembled), with local judges making the routine calls and a review queue for the rest. Stages and rules: docs/CHARKIT.md.

    .venv/bin/python -m homunculus.charkit PICTURE --name NAME [--from STAGE] [--until STAGE] [--only STAGE] [--panel] [--describe FILE.json] [--dressed-ref GLB] [--thumb-engine workbench|cycles]
    .venv/bin/python -m homunculus.charkit PICTURE --name ren --dry-run [--dry-run-cpu] [--fixture homunculus/charkit/fixtures/ren_dryrun.json] [--fresh]

--dry-run: no GPU at all. Ren's recorded outputs stand in for the heavy jobs (fixture "artifacts") and the judges are replaced by recorded answers (fixture "answers"); the numeric gates,
the re-roll / review logic, the state and the file plumbing run for real, under kits/_charkit_test/NAME and runs/_charkit_test/NAME. --dry-run-cpu also runs the CPU-only jobs
(background cut on the CPU, Cycles-on-CPU thumbnails, placement ICP, poke test). --fresh: start the state anew (the old charkit.json is kept with a time suffix).
A finished stage is skipped on a re-run unless --from/--only name it (or an earlier stage)."""
import argparse, json, os, sys, time
from .. import config as C
from . import pipeline, stages, judge, jobs

def main():
    S = list(stages.STAGES)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("picture"); ap.add_argument("--name", required=True)
    ap.add_argument("--from", dest="frm", choices=S); ap.add_argument("--until", choices=S); ap.add_argument("--only", choices=S)
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--dry-run-cpu", action="store_true"); ap.add_argument("--fixture"); ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--kit-dir"); ap.add_argument("--run-dir"); ap.add_argument("--panel", action="store_true", help="all three judges of config.JUDGES vote (default: Qwen3.8 alone, config.SHEET_JUDGES)")
    ap.add_argument("--describe", help="a JSON description of the character (the shape of prompts.DESCRIBE's answer) instead of asking the judges")
    ap.add_argument("--dressed-ref", help="the dressed reference model to place items on (default: the TRELLIS model of the clean body picture)")
    ap.add_argument("--thumb-engine", choices=["workbench", "cycles"], default="workbench"); a = ap.parse_args()
    dry = a.dry_run or a.dry_run_cpu
    kit_dir = a.kit_dir or (C.ROOT / "kits/_charkit_test" / a.name if dry else None); run_dir = a.run_dir or (C.RUNS / "_charkit_test" / a.name if dry else None)
    if a.fresh and kit_dir and os.path.exists(os.path.join(kit_dir, "charkit.json")):
        old = os.path.join(kit_dir, "charkit.json"); os.rename(old, old.replace(".json", time.strftime("_%Y%m%d-%H%M%S.json")))
        if os.path.exists(os.path.join(kit_dir, "needs_review.json")): os.rename(os.path.join(kit_dir, "needs_review.json"), os.path.join(kit_dir, time.strftime("needs_review_%Y%m%d-%H%M%S.json")))
    K = pipeline.Kit(os.path.abspath(a.picture), a.name, kit_dir, run_dir, dry=dry)
    if os.path.abspath(K.state["input"]) != os.path.abspath(a.picture): sys.exit(f"{K.sp} is for {K.state['input']}; use another --name or --fresh")
    K.opts = {"describe": a.describe, "dressed_ref": a.dressed_ref, "thumb_engine": "cycles" if a.dry_run_cpu else a.thumb_engine}
    if dry:
        fx = json.load(open(a.fixture or os.path.join(os.path.dirname(__file__), "fixtures", f"{a.name}_dryrun.json")))
        K.judge = judge.StubJudge(K, fx); K.jobs = jobs.ReplayJobs(K, fx, cpu=a.dry_run_cpu)
        if not a.dressed_ref and fx.get("artifacts", {}).get("dressed_ref"): K.opts["dressed_ref"] = str(C.ROOT / fx["artifacts"]["dressed_ref"])
        K.log(f"=== DRY RUN{' (CPU jobs for real)' if a.dry_run_cpu else ''}: {K.dir} / {K.run}; no GPU, recorded outputs and answers from {a.fixture or fx.get('name', 'fixture')}")
    else:
        K.judge = judge.Judge(K, C.JUDGES if a.panel else C.SHEET_JUDGES); K.jobs = jobs.Jobs(K)
    K.save()
    todo = [a.only] if a.only else S[S.index(a.frm) if a.frm else 0: S.index(a.until) + 1 if a.until else None]
    force = set(todo) if (a.only or a.frm) else set()
    ok = pipeline.run(K, stages.STAGES, todo, force)
    rev = K.open_reviews(); K.log(f"=== {'finished' if ok else 'stopped'}: {len(rev)} open review entries ({K.rp})"); sys.exit(0 if ok else 1)

if __name__ == "__main__": main()
