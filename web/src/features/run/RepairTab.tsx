import * as React from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Brush as BrushIcon, Check, Download, Eraser, Eye, Footprints, Hand, HardHat, Plus, RefreshCw, Smile, Trash2, Wand2, X } from "lucide-react";
import { api, useInvalidate, useRepairs } from "@/lib/api";
import type { RepairJob, RunDetail } from "@/lib/types";
import { Badge, Button, Empty, Field, Input, Panel, Segmented, Select, Slider, Switch, Textarea, Tip } from "@/components/ui";
import { Img, StatusPill, useLightbox } from "@/components/common";
import { ModelViewer } from "@/components/ModelViewer";
import type { Viewer } from "@/viewer/Viewer";
import { Brush, type Dab } from "./brush";
import { REPAIR_STEP, jobLabel } from "@/lib/stages";
import { cn } from "@/lib/utils";

const NO_ROTATE = { rotate: false };
const PRESETS = {
  hands: { label: "hands (keep any gloves)", view: "front", icon: Hand, name: "Hands" },
  head: { label: "head (keep any hood or helmet)", view: "auto", icon: Smile, name: "Head" },
  crown: { label: "top of the head or helmet", view: "top", icon: HardHat, name: "Crown" },
  feet: { label: "feet (keep the shoes or boots)", view: "auto", icon: Footprints, name: "Feet" },
} as const;
const VIEWS = [{ value: "auto", label: "Automatic" }, { value: "front", label: "Front" }, { value: "back", label: "Back" }, { value: "left", label: "Left side" }, { value: "right", label: "Right side" }, { value: "top", label: "Above" }, { value: "bottom", label: "Below" }];

function useBrushKeys(b: React.RefObject<Brush | null>) {
  React.useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement; if (t.closest?.("input,textarea,select")) return;
      if (e.key === "[") b.current?.setSize(b.current.size * 0.85); else if (e.key === "]") b.current?.setSize(b.current.size * 1.18);
    };
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
  }, [b]);
}

export function RepairTab({ d }: { d: RunDetail }) {
  const meshDone = d.stages.find((s) => s.key === "mesh")?.status === "done";
  const mesh = meshDone ? d.models.find((m) => m.key === "colored_glb") ?? d.models.find((m) => m.key === "mesh_glb") ?? d.models.find((m) => m.key === "final_glb") : null;      // the coloured mesh is the same geometry (same frame), with colour: easier to see what is broken
  if (!mesh) return <Empty icon={<Wand2 />} title="No finished 3D model yet.">Repair works on the model before rigging, once the 3D shape stage has finished (you can already inspect the model in the 3D model tab).</Empty>;
  return <RepairTool d={d} meshUrl={mesh.url} />;
}

function RepairTool({ d, meshUrl }: { d: RunDetail; meshUrl: string }) {
  const brush = React.useRef<Brush | null>(null);
  const [viewer, setViewer] = React.useState<Viewer | null>(null);
  const [showing, setShowing] = React.useState<string>(meshUrl);
  const original = showing === meshUrl;
  const [, force] = React.useReducer((x) => x + 1, 0);
  const [label, setLabel] = React.useState(""); const [view, setView] = React.useState("auto");
  const [manual, setManual] = React.useState(true); const [notes, setNotes] = React.useState("");
  const [staged, setStaged] = React.useState<{ strokes: Dab[]; label: string; view: string }[]>([]);
  const [msg, setMsg] = React.useState(""); const [busy, setBusy] = React.useState(false);
  const inv = useInvalidate();
  const { data: jobs, refetch } = useRepairs(d.name, true);
  useBrushKeys(brush);

  React.useEffect(() => {
    if (!viewer) return;
    const b = new Brush(viewer, 0xff375f); b.onChange = force; brush.current = b; if (viewer.internals().root()) b.attach(); force();
    return () => { b.dispose(); brush.current = null; };
  }, [viewer]);
  React.useEffect(() => { if (brush.current) { brush.current.extra = staged.flatMap((g) => g.strokes); brush.current.redraw(); } }, [staged]);
  React.useEffect(() => { if (brush.current) brush.current.enabled = original; }, [original]);

  const b = brush.current; const n = b?.strokes.length ?? 0; const parts = staged.length + (n ? 1 : 0);
  const preset = (k: keyof typeof PRESETS) => {
    if (!b || !original) return; const c = b.region(k);
    if (c) { setLabel(PRESETS[k].label); setView(PRESETS[k].view); }
    setMsg(c ? `${PRESETS[k].label} selected (${c} dabs). Check them, then press Repair.` : `Could not find the ${PRESETS[k].label}: paint them by hand.`);
  };
  const keep = () => { if (!b || !n) return; setStaged((s) => [...s, { strokes: b.strokes.slice(), label: label.trim(), view }]); b.clear(); setLabel(""); setView("auto"); setMsg(`${staged.length + 1} part${staged.length ? "s" : ""} kept. Select the next one, then press Repair.`); };
  const go = async () => {
    if (!b) return; setBusy(true);
    try {
      const groups = [...staged, ...(n ? [{ strokes: b.strokes.slice(), label: label.trim(), view }] : [])];
      await api.repair(d.name, groups, notes.trim(), manual); setStaged([]); b.clear(); setMsg(""); toast.success("Repair started"); refetch(); inv(["run", d.name]);
    } catch (e: any) { setMsg(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_400px]">
      <div className="grid content-start gap-3">
        <ModelViewer url={showing} onViewer={setViewer} settings={NO_ROTATE} onLoaded={() => { brush.current?.attach(); force(); }} className="h-[min(72vh,760px)] border border-line [&_canvas]:cursor-crosshair">
          <div className="pointer-events-none absolute top-3 right-3 rounded-lg bg-black/45 px-2.5 py-1 text-[11px] text-ink-2 backdrop-blur">
            {original ? "Drag to paint the broken part · right-drag or scroll to move the view" : "The repaired model"}
          </div>
        </ModelViewer>
        <div className="panel flex flex-wrap items-center gap-2 p-2">
          <Segmented value={b?.erase ? "erase" : "paint"} onValueChange={(v) => { if (b) { b.erase = v === "erase"; force(); } }} options={[{ value: "paint", label: <span className="flex items-center gap-1.5"><BrushIcon className="size-3.5" /> Paint</span> }, { value: "erase", label: <span className="flex items-center gap-1.5"><Eraser className="size-3.5" /> Erase</span> }]} />
          <div className="flex w-56 items-center gap-2 px-2"><span className="text-xs text-ink-3">Brush</span><Slider value={b?.size ?? 3} onValueChange={(v) => b?.setSize(v)} min={0.3} max={25} step={0.1} /><span className="w-10 font-mono text-[11px] text-ink-2">{(b?.size ?? 3).toFixed((b?.size ?? 3) < 10 ? 1 : 0)}%</span></div>
          <span className="h-5 w-px bg-white/10" />
          {(Object.keys(PRESETS) as (keyof typeof PRESETS)[]).map((k) => { const P = PRESETS[k]; return <Tip key={k} content={`Select the ${P.label}`}><Button size="sm" variant="ghost" disabled={!original} onClick={() => preset(k)}><P.icon /> {P.name}</Button></Tip>; })}
          <Button size="sm" variant="ghost" onClick={() => { b?.clear(); setMsg(""); }}><Trash2 /> Clear</Button>
          <span className="ml-auto pr-2 text-[11px] text-ink-3">[ ] or Alt + scroll: brush size</span>
        </div>
      </div>
      <div className="grid content-start gap-4">
        <Panel className="p-5">
          <h3 className="text-[15px] font-semibold">Repair a part</h3>
          <p className="mt-1 mb-4 text-[13px] leading-relaxed text-ink-3">Paint over what came out broken (fused fingers, a crumpled helmet top, a melted foot), a little of the neighbouring part included, or press a region button. The part is redrawn from the side it faces, rebuilt in 3D and grafted in with a clean cut.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="What is it?"><Input value={label} maxLength={80} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. the top of the helmet" /></Field>
            <Field label="Redraw from"><Select value={view} onValueChange={setView} options={VIEWS} /></Field>
          </div>
          <div className="mt-4"><Switch checked={manual} onCheckedChange={setManual} label="I choose the redraw myself" hint="The job shows you every redraw and waits for your pick. Off: the finger counter or silhouette check (and a judge) choose." /></div>
          <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} className="mt-4 min-h-14" placeholder="Optional: e.g. the glove has a white wrist band; a smooth round dome with no crease" />
          {!!staged.length && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {staged.map((g, i) => <Badge key={i} tone="accent">{g.label || "painted part"} · {g.view}<button onClick={() => setStaged((s) => s.filter((_, j) => j !== i))}><X className="size-3" /></button></Badge>)}
            </div>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="primary" onClick={go} loading={busy} disabled={!parts || !original}><Wand2 /> {parts > 1 ? `Repair ${parts} parts` : n ? `Repair painted region (${n} dabs)` : "Repair painted region"}</Button>
            <Button variant="secondary" onClick={keep} disabled={!n || !original || staged.length >= 5} title="Keep this selection (with its label and view) and select another part"><Plus /> Add part</Button>
          </div>
          {msg && <p className="mt-3 text-[12px] text-ink-2">{msg}</p>}
        </Panel>
        <div className="grid gap-3">
          {!jobs?.length ? <div className="px-1 text-[13px] text-ink-3">No repairs yet.</div> : jobs.map((j) => <RepairJobCard key={j.job} d={d} j={j} onShow={(u) => setShowing(u ?? meshUrl)} showing={showing} refetch={refetch} />)}
        </div>
      </div>
    </div>
  );
}

function RepairJobCard({ d, j, onShow, showing, refetch }: { d: RunDetail; j: RepairJob; onShow: (u: string | null) => void; showing: string; refetch: () => void }) {
  const lb = useLightbox(); const nav = useNavigate();
  const [use, setUse] = React.useState(false); const [mode, setMode] = React.useState<"new" | "same">("new"); const [name, setName] = React.useState(`${d.name}_repaired`);
  const active = j.status === "queued" || j.status === "running";
  const choose = async (group: number, region: number, choice: number | "more") => {
    try { await api.repairChoose(d.name, j.job, group, region, choice); toast(choice === "more" ? "Making more redraws…" : "Building that redraw…"); refetch(); } catch (e: any) { toast.error(e.message); }
  };
  return (
    <Panel className={cn("p-4", active && "border-accent/30")}>
      <div className="mb-3 flex items-center gap-2">
        <b className="text-[13px]">{jobLabel(j.job)}</b>
        <StatusPill status={j.status === "done" ? "finished" : j.status === "failed" ? "failed" : "running"} />
        {active && <span className="text-xs text-ink-3">{REPAIR_STEP[j.step] ?? j.step}</span>}
        {j.seconds ? <span className="ml-auto font-mono text-[11px] text-ink-3">{j.seconds} s</span> : null}
      </div>
      {j.error && <div className="mb-3 rounded-lg border border-bad/30 bg-bad/8 px-3 py-2 text-xs text-bad">{j.error}</div>}
      {j.regions.map((r) => (
        <div key={`${r.group}-${r.index}`} className="mb-3 rounded-xl border border-line p-3">
          <div className="mb-2 text-xs text-ink-2">{r.label && <b className="text-ink">{r.label}</b>} · {r.status}{r.by === "you" ? " · chosen by you" : ""}{r.five_fingers === false ? " · no redraw had five fingers: best effort" : r.checked === false ? " · no redraw passed the check: best effort" : ""}</div>
          <div className="grid grid-cols-3 gap-2">
            {r.crop && <figure><Img src={r.crop} className="aspect-square rounded-lg" onClick={() => lb([{ url: r.crop!, title: "before" }], 0)} /><figcaption className="mt-1 text-[10.5px] text-ink-3">before</figcaption></figure>}
            {(r.candidates ?? []).map((c, ci) => (
              <figure key={c} className={cn("rounded-lg", c === r.chosen && "ring-2 ring-accent")}>
                <Img src={c} className="aspect-square rounded-lg" onClick={() => lb((r.candidates ?? []).map((u, k) => ({ url: u, title: `redraw ${k + 1}` })), ci)} />
                <figcaption className="mt-1 text-[10.5px] text-ink-3">{c === r.chosen ? "chosen" : `redraw ${ci + 1}`}{r.info?.[ci] ? ` · ${r.info[ci]}` : ""}</figcaption>
                {r.awaiting && <Button size="sm" variant="primary" className="mt-1 w-full" onClick={() => choose(r.group || 0, r.index, ci)}><Check /> Use this</Button>}
              </figure>
            ))}
            {r.after && <figure><Img src={r.after} className="aspect-square rounded-lg ring-1 ring-ok/40" onClick={() => lb([{ url: r.after!, title: "after" }], 0)} /><figcaption className="mt-1 text-[10.5px] text-ok">after{r.after_fingers ? ` · ${r.after_fingers} fingers` : ""}</figcaption></figure>}
          </div>
          {r.awaiting && <div className="mt-2 flex items-center gap-2 text-xs"><b className="text-warn">Pick the redraw to build</b><Button size="sm" variant="ghost" onClick={() => choose(r.group || 0, r.index, "more")}><RefreshCw /> Make 3 more</Button></div>}
        </div>
      ))}
      {active && !!j.log?.length && <div className="rounded-lg bg-black/40 p-2 font-mono text-[10.5px] leading-relaxed text-ink-3">{j.log.map((l, i) => <div key={i}>{l}</div>)}</div>}
      {j.result && (
        <div className="mt-2 flex flex-wrap gap-2">
          <Button size="sm" variant={showing === j.result ? "primary" : "secondary"} onClick={() => onShow(j.result!)}><Eye /> View repaired</Button>
          <Button size="sm" variant="ghost" onClick={() => onShow(null)}>View original</Button>
          <a href={j.result} download><Button size="sm" variant="ghost"><Download /> .glb</Button></a>
          {j.can_use && <Button size="sm" variant="success" onClick={() => setUse((v) => !v)}>Use for this run</Button>}
        </div>
      )}
      {use && (
        <div className="mt-3 grid gap-3 rounded-xl border border-ok/25 bg-ok/5 p-3">
          <p className="text-xs text-ink-2">One mesh with the original texture continues from the Colour stage (colour, rig, rig check, animation, texture). Needs the run to be stopped or finished.</p>
          <Segmented value={mode} onValueChange={(v) => setMode(v as any)} options={[{ value: "new", label: "New run (keeps this one)" }, { value: "same", label: "Replace in this run" }]} />
          {mode === "new" && <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={40} />}
          <Button size="sm" variant="primary" onClick={async () => { try { const r = await api.repairUse(d.name, j.job, mode, name.trim()); toast.success("Continuing with the repaired mesh"); nav(`/run/${encodeURIComponent(r.run)}`); } catch (e: any) { toast.error(e.message); } }}>Continue the run with it</Button>
        </div>
      )}
    </Panel>
  );
}
