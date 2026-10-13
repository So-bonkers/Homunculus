import * as React from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { GitFork } from "lucide-react";
import { api, useRuns } from "@/lib/api";
import type { RunDetail } from "@/lib/types";
import { Button, Dialog, Field, Input, Segmented, Select, Slider, Spinner, Switch, Textarea } from "@/components/ui";
import { FACES, FACE_SOURCES, LOOKS, NAME_RE, OUTFITS, REVIEWS, RIGGERS, TEXTURES, hintOf } from "@/lib/options";
import { FORKABLE, FORK_HINT, FORK_LABEL, FORK_OF, ORDER } from "@/lib/stages";
import { PresetPicker } from "@/features/PresetPicker";
import { cn } from "@/lib/utils";

export function ForkDialog({ run, open, onOpenChange, stage, look }: { run: string; open: boolean; onOpenChange: (v: boolean) => void; stage?: string | null; look?: string }) {
  const { data: d } = useQuery({ queryKey: ["run-once", run], enabled: open, staleTime: 0, queryFn: async () => (await fetch(`/api/run/${encodeURIComponent(run)}`, { cache: "no-store" })).json() as Promise<RunDetail> });
  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title={<span className="flex items-center gap-2"><GitFork className="size-4 text-accent" /> Restart {run} from a stage</span>}
      description="Only the finished stages before that point are copied; the original run stays untouched unless you restart it in place.">
      {!d ? <div className="flex items-center gap-3 py-8 text-[13px] text-ink-3"><Spinner /> Loading the run…</div> : <ForkForm d={d} stage={stage} look={look} close={() => onOpenChange(false)} />}
    </Dialog>
  );
}

function ForkForm({ d, stage, look, close }: { d: RunDetail; stage?: string | null; look?: string; close: () => void }) {
  const nav = useNavigate();
  const { data: runs } = useRuns();
  const o = d.options || {};
  const firstOpen = d.stages.find((s) => s.status !== "done" && s.status !== "skipped")?.key;
  const [F, setF] = React.useState(() => ({
    stage: (stage && FORK_OF[stage]) || (firstOpen && FORK_OF[firstOpen]) || "edit",
    mode: "new" as "new" | "same", name: "", notes: "",
    look: look || o.look || "asis", outfit: o.outfit || "keep", review: o.review || "override", grace: o.grace || 60,
    face_source: o.face_source || "original", texture: o.texture || "simple", face: o.face || "auto", face_redraw: o.face_redraw !== false,
    rigger: o.rigger || "mia", anim: (o.anim_prompts || []).join("\n"), zip: d.zip_on,
  }));
  const set = <K extends keyof typeof F>(k: K, v: (typeof F)[K]) => setF((f) => ({ ...f, [k]: v }));
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (F.name || !runs) return;
    const names = new Set(runs.map((r) => r.name)); let n = 1; while (names.has(`${d.name}_f${n}`)) n++;
    set("name", `${d.name}_f${n}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs]);

  const done = new Set(d.stages.filter((s) => s.status === "done").map((s) => s.key));
  const after = ORDER.indexOf(F.stage as any) > ORDER.indexOf("edit");
  const submit = async () => {
    const target = F.mode === "same" ? d.name : F.name.trim();
    if (F.mode === "new") {
      if (!NAME_RE.test(target)) return toast.error("Name: letters, digits, - and _ only.");
      if (runs?.some((r) => r.name === target)) return toast.error("That name is taken.");
    }
    setBusy(true);
    try {
      const r = await api.fork({
        run: d.name, name: target, stage: F.stage, notes: F.notes.trim(), look: F.look, rigger: F.rigger, anim: F.anim, anim_reps: o.anim_reps || 2,
        outfit: F.outfit, face: F.face, face_source: F.face_source, texture: F.texture, face_redraw: F.face_redraw ? "1" : "0", review: F.review, grace: String(F.grace), zip: F.zip,
      });
      toast.success(F.mode === "same" ? `Restarted ${target} from ${FORK_LABEL[F.stage]}` : `Forked into ${target}`);
      close(); nav(`/run/${encodeURIComponent(r.run || target)}`);
    } catch (e: any) { toast.error(e.message || "Could not fork."); } finally { setBusy(false); }
  };

  return (
    <div className="grid gap-6">
      <div>
        <div className="mb-2 text-xs font-medium text-ink-2">Start from</div>
        <div className="flex flex-wrap gap-1.5">
          {FORKABLE.map((s) => (
            <button key={s} onClick={() => set("stage", s)} className={cn("flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition", F.stage === s ? "border-accent/60 bg-accent/15 text-ink" : "border-line-strong text-ink-2 hover:text-ink")}>
              <span className={cn("grid size-4 place-items-center rounded font-mono text-[9px]", done.has(s) ? "bg-ok/20 text-ok" : "bg-white/8 text-ink-3")}>{ORDER.indexOf(s) + 1}</span>
              {FORK_LABEL[s]}
            </button>
          ))}
        </div>
        <p className="mt-2 text-[12px] text-ink-3">{FORK_HINT[F.stage]}{F.mode === "same" ? " This run's later results are replaced." : ""}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Where"><Segmented value={F.mode} onValueChange={(v) => set("mode", v as any)} options={[{ value: "new", label: "New run" }, { value: "same", label: "Restart this one" }]} /></Field>
        <Field label="Name"><Input value={F.mode === "same" ? d.name : F.name} disabled={F.mode === "same"} maxLength={40} onChange={(e) => set("name", e.target.value)} /></Field>
      </div>
      <Field label="Instructions" hint="Added to the redraw prompt and shown to every judge from this stage on.">
        <Textarea autoFocus value={F.notes} onChange={(e) => set("notes", e.target.value)} placeholder="e.g. keep the hands open with all five fingers apart; make the boots shorter" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Look" hint={hintOf(LOOKS, F.look) + (after && F.look !== (o.look || "asis") ? " A new look only shows if you restart from Redraw or earlier." : "")}><Select value={F.look} onValueChange={(v) => set("look", v)} options={LOOKS} /></Field>
        <Field label="Outfit" hint={hintOf(OUTFITS, F.outfit)}><Segmented value={F.outfit} onValueChange={(v) => set("outfit", v)} options={OUTFITS} /></Field>
        <Field label="Your review" hint={hintOf(REVIEWS, F.review)}><Segmented value={F.review} onValueChange={(v) => set("review", v)} options={REVIEWS} /></Field>
        {F.review === "override" && <Field label={`Review window · ${F.grace} s`}><Slider value={F.grace} onValueChange={(v) => set("grace", v)} min={15} max={300} step={15} /></Field>}
        <Field label="Face texture from" hint={hintOf(FACE_SOURCES, F.face_source)}><Segmented value={F.face_source} onValueChange={(v) => set("face_source", v)} options={FACE_SOURCES} /></Field>
        <Field label="Texture" hint={hintOf(TEXTURES, F.texture)}><Segmented value={F.texture} onValueChange={(v) => set("texture", v)} options={TEXTURES} /></Field>
        <Field label="Face" hint={hintOf(FACES, F.face)}><Segmented value={F.face} onValueChange={(v) => set("face", v)} options={FACES} /></Field>
        <Field label="Rigger" hint={hintOf(RIGGERS, F.rigger)}><Segmented value={F.rigger} onValueChange={(v) => set("rigger", v)} options={RIGGERS} /></Field>
      </div>
      <div className="grid gap-3 rounded-xl border border-line p-4">
        {F.face !== "off" && <Switch checked={F.face_redraw} onCheckedChange={(v) => set("face_redraw", v)} label="Face close-up redraw" hint="A sharper face for the 3D shape and texture." />}
        <Switch checked={F.zip} onCheckedChange={(v) => set("zip", v)} label="Mixamo zip" hint="OBJ + texture to upload to mixamo.com for animations." />
      </div>
      <Field label="Animation prompts (one per line)">
        <Textarea value={F.anim} onChange={(e) => set("anim", e.target.value)} placeholder={"walks forward\nwaves with the right hand"} />
      </Field>
      <PresetPicker value={F.anim} onChange={(v) => set("anim", v)} />
      <div className="sticky bottom-0 -mx-5 -mb-4 flex justify-end gap-2 border-t border-line bg-surface/95 px-5 py-3 backdrop-blur">
        <Button variant="ghost" onClick={close}>Cancel</Button>
        <Button variant="primary" onClick={submit} loading={busy}>{F.mode === "same" ? "Restart" : "Fork & start"}</Button>
      </div>
    </div>
  );
}
