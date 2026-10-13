import * as React from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { toast } from "sonner";
import { Box, Clapperboard, Film, ImagePlus, Layers, Rocket, ScanFace, Scale, Settings2, Sparkles, Bone, Upload } from "lucide-react";
import { upload, q, useRuns } from "@/lib/api";
import { Button, Field, Input, Panel, Progress, Segmented, Select, Slider, Switch, Textarea } from "@/components/ui";
import { PresetPicker } from "@/features/PresetPicker";
import { ACCEPT_INPUT, AUTO_REPAIR, FACES, FACE_SOURCES, LOOKS, MESH_RE, NAME_RE, OUTFITS, REVIEWS, RIGGERS, SHEET_ORDERS, STYLES, TEXTURES, hintOf, nameFromFile } from "@/lib/options";
import { FORKABLE, FORK_LABEL } from "@/lib/stages";
import { cn } from "@/lib/utils";

function Card({ icon: Icon, title, children, desc, tour }: { icon: any; title: string; desc?: string; children: React.ReactNode; tour?: string }) {
  return (
    <Panel className="p-5" data-tour={tour}>
      <div className="mb-4 flex items-start gap-3">
        <div className="grid size-8 place-items-center rounded-lg bg-accent/12 text-accent"><Icon className="size-4" /></div>
        <div><h3 className="text-[14px] font-semibold">{title}</h3>{desc && <p className="text-xs text-ink-3">{desc}</p>}</div>
      </div>
      <div className="grid gap-5">{children}</div>
    </Panel>
  );
}

export default function NewRun() {
  const nav = useNavigate();
  const { data: runs } = useRuns();
  const [file, setFile] = React.useState<File | null>(null);
  const [preview, setPreview] = React.useState<string | null>(null);
  const [over, setOver] = React.useState(false);
  const [pct, setPct] = React.useState<number | null>(null);
  const [F, setF] = React.useState({
    name: "", direct: false, sheet: false, order: "lfrb", look: "choose", outfit: "keep", texture: "simple", face: "auto", auto_repair: "auto",
    face_source: "original", face_redraw: true, review: "override", grace: 60, zip: true, rigger: "mia", anim: "", style: "", anim_reps: "2", frm: "",
  });
  const set = <K extends keyof typeof F>(k: K, v: (typeof F)[K]) => setF((f) => ({ ...f, [k]: v }));
  const isMesh = !!file && MESH_RE.test(file.name);
  const plain = F.direct || F.sheet;

  const choose = (f: File | undefined | null) => {
    if (!f) return;
    setFile(f); setPreview((p) => { if (p) URL.revokeObjectURL(p); return MESH_RE.test(f.name) ? null : URL.createObjectURL(f); });
    if (!F.name) set("name", nameFromFile(f.name));
  };

  const exists = runs?.find((r) => r.name === F.name);
  const nameHint = !F.name ? "" : !NAME_RE.test(F.name) ? "Letters, digits, - and _ only." : exists?.live ? "This run is active right now." : exists && file ? "A run with this name exists: the new picture replaces its input and the run resumes."
    : exists ? "Existing run: start without a picture to resume it, or pick a stage under Advanced to redo from there." : "";
  const warn = !!F.name && (!NAME_RE.test(F.name) || !!exists?.live);

  const start = async () => {
    if (!F.name) return toast.error("Give the run a name.");
    if (!NAME_RE.test(F.name)) return toast.error("Letters, digits, - and _ only.");
    if (!file && !exists) return toast.error("Choose a picture or a 3D model first.");
    const query = q({
      name: F.name, fname: file?.name ?? "image.jpg", look: plain ? "asis" : F.look, direct: plain ? "1" : "0", sheet: F.sheet && !isMesh ? F.order : "", rigger: F.rigger,
      anim: F.anim.trim(), anim_reps: F.anim_reps, outfit: F.outfit, face: F.face, face_source: F.face_source, texture: F.texture, auto_repair: F.auto_repair,
      face_redraw: F.face_redraw ? "1" : "0", review: F.review, grace: F.grace, style: F.style, frm: F.frm, zip: F.zip ? "1" : "0",
    });
    setPct(file ? 0 : null);
    try {
      await upload(`/api/upload?${query}`, file ?? new Blob([]), (p) => setPct(p));
      toast.success(`Started ${F.name}`); nav(`/run/${encodeURIComponent(F.name)}`);
    } catch (e: any) { toast.error(e.message || "Could not start the run."); setPct(null); }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 lg:px-6">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
        <div className="mb-2 text-[11px] font-semibold tracking-[0.14em] text-ink-3 uppercase">New run</div>
        <h1 className="text-4xl font-semibold tracking-tight">Drop a picture. <span className="text-gradient">Watch it come alive.</span></h1>
        <p className="mt-2 max-w-2xl text-[14px] text-ink-3">A picture, a turnaround sheet or a 3D model. A run takes 15 to 50 minutes and stops at every gate you ask it to.</p>
      </motion.div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,420px)_1fr]">
        <div className="lg:sticky lg:top-20 lg:self-start">
          <label data-tour="nr-drop"
            onDragEnter={(e) => { e.preventDefault(); setOver(true); }} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
            onDrop={(e) => { e.preventDefault(); setOver(false); choose(e.dataTransfer.files[0]); }}
            className={cn("group relative flex aspect-[4/5] cursor-pointer flex-col items-center justify-center overflow-hidden rounded-xl2 border-2 border-dashed transition",
              over ? "border-accent bg-accent/10" : file ? "border-line bg-surface" : "border-line-strong bg-white/[0.02] hover:border-accent/50 hover:bg-accent/5")}>
            <input type="file" accept={ACCEPT_INPUT} className="hidden" onChange={(e) => choose(e.target.files?.[0])} />
            {preview ? (
              <><img src={preview} className="absolute inset-0 h-full w-full object-contain p-3" /><span className="glass absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full px-3 py-1 text-xs text-ink-2">{file?.name} · click to change</span></>
            ) : isMesh ? (
              <div className="flex flex-col items-center gap-3 px-8 text-center">
                <Box className="size-12 text-accent" /><b className="text-sm">{file?.name}</b>
                <span className="text-xs text-ink-3">{((file?.size ?? 0) / 1048576).toFixed(1)} MB · a 3D model: it is oriented, painted from its own renders and rigged. Click to change.</span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4 px-8 text-center">
                <div className="grid size-16 place-items-center rounded-2xl bg-accent/12 text-accent transition group-hover:scale-105"><ImagePlus className="size-7" /></div>
                <div><b className="text-[15px]">Drop a picture or a 3D model</b><p className="mt-1 text-xs text-ink-3">JPG, PNG, WebP · STL, OBJ, PLY, GLB, FBX</p></div>
              </div>
            )}
          </label>
          <div className="mt-4 grid gap-3">
            <Field label="Run name" hint={<span className={warn ? "text-warn" : ""}>{nameHint}</span>}>
              <Input value={F.name} maxLength={40} onChange={(e) => set("name", e.target.value)} placeholder="e.g. knight" spellCheck={false} />
            </Field>
            {pct !== null && <div><Progress value={pct * 100} /><p className="mt-1 text-[11px] text-ink-3">Uploading · {Math.round(pct * 100)}%</p></div>}
            <Button data-tour="nr-start" variant="primary" size="lg" onClick={start} loading={pct !== null} className="w-full"><Rocket /> {exists && !file ? "Resume run" : "Start run"}</Button>
          </div>
        </div>

        <div className="grid gap-4">
          {!isMesh && (
            <Card tour="nr-input" icon={Layers} title="What you are giving it" desc="A single picture is redrawn as a clean T-pose; a clean reference or a sheet is used as it is.">
              <Switch checked={F.direct} onCheckedChange={(v) => { set("direct", v); if (v) set("sheet", false); }} label="Use my picture as is"
                hint="Skip the redraw: for clean full-body references (T/A-pose, open hands, plain background). The texture then comes from your picture itself (upscaled, not redrawn)." />
              <Switch checked={F.sheet} onCheckedChange={(v) => { set("sheet", v); if (v) set("direct", false); }} label="My picture is a turnaround sheet"
                hint="Four views side by side (front, back and both sides, in a T-pose). The shape is built from all four views and the texture comes from them, so the back and sides are real, not guessed." />
              {F.sheet && <Field label="Order in the sheet" hint={hintOf(SHEET_ORDERS, F.order)}><Segmented value={F.order} onValueChange={(v) => set("order", v)} options={SHEET_ORDERS} /></Field>}
            </Card>
          )}
          {!isMesh && !plain && (
            <Card tour="nr-look" icon={Sparkles} title="Look" desc="Keep the picture's style, restyle it, or see every look and pick.">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {LOOKS.map((l) => (
                  <button key={l.value} onClick={() => set("look", l.value)} className={cn("rounded-xl border px-3 py-3 text-left transition", F.look === l.value ? "border-accent/60 bg-accent/12" : "border-line-strong hover:border-white/20")}>
                    <div className="text-[13px] font-medium">{l.label}</div>
                  </button>
                ))}
              </div>
              <p className="-mt-2 text-xs text-ink-3">{hintOf(LOOKS, F.look)}</p>
              <Field label="Outfit" hint={hintOf(OUTFITS, F.outfit)}><Segmented value={F.outfit} onValueChange={(v) => set("outfit", v)} options={OUTFITS} /></Field>
            </Card>
          )}
          <Card tour="nr-review" icon={Scale} title="Who decides" desc="At the redraw pick, the 3D shape check and the rig check.">
            <Field label="Your review" hint={hintOf(REVIEWS, F.review)}><Segmented value={F.review} onValueChange={(v) => set("review", v)} options={REVIEWS} /></Field>
            {F.review === "override" && <Field label={`Review window · ${F.grace} s`}><Slider value={F.grace} onValueChange={(v) => set("grace", v)} min={15} max={300} step={15} /></Field>}
          </Card>
          <Card icon={ScanFace} title="Face and texture">
            <Field label="Face" hint={hintOf(FACES, F.face)}><Segmented value={F.face} onValueChange={(v) => set("face", v)} options={FACES} /></Field>
            {F.face !== "off" && <Switch checked={F.face_redraw} onCheckedChange={(v) => set("face_redraw", v)} label="Redraw the face as a close-up" hint="A sharper face for the 3D shape and texture. Turn it off to use the full-body redraw as it is." />}
            <Field label="Face texture from" hint={hintOf(FACE_SOURCES, F.face_source)}><Segmented value={F.face_source} onValueChange={(v) => set("face_source", v)} options={FACE_SOURCES} /></Field>
            <Field label="Texture" hint={hintOf(TEXTURES, F.texture)}><Segmented value={F.texture} onValueChange={(v) => set("texture", v)} options={TEXTURES} /></Field>
          </Card>
          <Card icon={Bone} title="Rig">
            <Field label="Rigger" hint={hintOf(RIGGERS, F.rigger)}><Segmented value={F.rigger} onValueChange={(v) => set("rigger", v)} options={RIGGERS} /></Field>
            <Field label="Broken hands" hint={hintOf(AUTO_REPAIR, F.auto_repair)}><Segmented value={F.auto_repair} onValueChange={(v) => set("auto_repair", v)} options={AUTO_REPAIR} /></Field>
          </Card>
          <Card tour="nr-anim" icon={Clapperboard} title="Animation" desc="Clips are made once the rig is built; add more any time on the run page.">
            <div className="flex gap-3 rounded-xl border border-cyan/20 bg-cyan/5 p-4">
              <Film className="mt-0.5 size-4 shrink-0 text-cyan" />
              <p className="text-[13px] text-ink-2"><b className="text-ink">Copy a dance from a video</b> is the main way to animate: once the rig is built, open the run's <b>Animate</b> tab, drop a video of one person dancing and pick the seconds to copy.</p>
            </div>
            <Field label="Text prompts" hint="Describe one motion per line (not the character). Made after the rig is built.">
              <Textarea value={F.anim} onChange={(e) => set("anim", e.target.value)} placeholder={"walks forward\nwaves with the right hand\njumps in place"} />
            </Field>
            <PresetPicker value={F.anim} onChange={(v) => set("anim", v)} />
          </Card>
          <details className="panel group p-5">
            <summary className="flex cursor-pointer list-none items-center gap-3"><div className="grid size-8 place-items-center rounded-lg bg-white/6 text-ink-2"><Settings2 className="size-4" /></div><h3 className="text-[14px] font-semibold">Advanced</h3></summary>
            <div className="mt-5 grid gap-5 sm:grid-cols-2">
              <Field label="Image style" hint={hintOf(STYLES, F.style)}><Select value={F.style || "auto"} onValueChange={(v) => set("style", v === "auto" ? "" : v)} options={STYLES.map((s) => ({ ...s, value: s.value || "auto" }))} /></Field>
              <Field label="Clips per prompt"><Select value={F.anim_reps} onValueChange={(v) => set("anim_reps", v)} options={["1", "2", "3", "4"].map((v) => ({ value: v, label: v }))} /></Field>
              <Field label="Start from" hint="Redo an existing run from that stage."><Select value={F.frm || "start"} onValueChange={(v) => set("frm", v === "start" ? "" : v)} options={[{ value: "start", label: "Beginning / resume" }, ...FORKABLE.map((s) => ({ value: s, label: FORK_LABEL[s] }))]} /></Field>
              <div className="pt-6"><Switch checked={F.zip} onCheckedChange={(v) => set("zip", v)} label="Mixamo zip" hint="OBJ + texture to upload to mixamo.com for animations." /></div>
            </div>
          </details>
          <p className="flex items-center gap-2 text-xs text-ink-3"><Upload className="size-3.5" /> The picture goes to the server on this machine only.</p>
        </div>
      </div>
    </div>
  );
}
