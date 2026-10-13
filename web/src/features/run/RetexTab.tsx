import * as React from "react";
import * as THREE from "three";
import { toast } from "sonner";
import { Brush as BrushIcon, Check, Eraser, Eye, ImagePlus, Loader2, Move3d, PaintBucket, Sparkles, Trash2, Wand2 } from "lucide-react";
import { api, useRetex } from "@/lib/api";
import type { CameraJSON, RetexJob, RunDetail } from "@/lib/types";
import { Button, Empty, Panel, Segmented, Slider, Spinner, Textarea } from "@/components/ui";
import { Img, StatusPill, useLightbox } from "@/components/common";
import { ModelViewer } from "@/components/ModelViewer";
import type { Viewer } from "@/viewer/Viewer";
import { Brush } from "./brush";
import { jobLabel } from "@/lib/stages";
import { cn } from "@/lib/utils";

const NO_ROTATE = { rotate: false };
const readFile = (f: Blob) => new Promise<string>((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result as string); r.onerror = rej; r.readAsDataURL(f); });
const MODE_NAME: Record<string, string> = { project: "Texture", generate: "Generate view", apply: "Keep" };

export function RetexTab({ d }: { d: RunDetail }) {
  const { data: info, refetch, isLoading } = useRetex(d.name, true);
  if (isLoading && !info) return <div className="flex items-center gap-3 text-[13px] text-ink-3"><Spinner /> Loading…</div>;
  if (!info?.base) return <Empty icon={<PaintBucket />} title="No textured 3D model yet.">Retexture works on the model after the colour or texture stage.</Empty>;
  return <RetexTool d={d} base={info.base} original={info.original} jobs={info.jobs ?? []} refetch={refetch} />;
}

function RetexTool({ d, base, original, jobs, refetch }: { d: RunDetail; base: string; original: string | null; jobs: RetexJob[]; refetch: () => void }) {
  const lb = useLightbox();
  const brush = React.useRef<Brush | null>(null);
  const [viewer, setViewer] = React.useState<Viewer | null>(null);
  const [, force] = React.useReducer((x) => x + 1, 0);
  const [showing, setShowing] = React.useState(base); const isBase = showing === base;
  const [tool, setTool] = React.useState<"model" | "mask" | "orbit">("model");
  const [erase, setErase] = React.useState(false);
  const [src, setSrc] = React.useState<"gen" | "ref">("gen");
  const [notes, setNotes] = React.useState("");
  const [ref, setRef] = React.useState<{ url: string; aspect: number } | null>(null);
  const [refFile, setRefFile] = React.useState<string | null>(null);
  const [refGen, setRefGen] = React.useState<{ job: string; name: string; camera: CameraJSON } | null>(null);
  const [opacity, setOpacity] = React.useState(55);
  const [mstrokes, setM] = React.useState<[number, number, number][]>([]);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [hint, setHint] = React.useState("Brush the part to change");
  const mask = React.useRef<HTMLCanvasElement>(null);
  const mdown = React.useRef(false);

  React.useEffect(() => {
    if (!viewer) return;
    const b = new Brush(viewer, 0x5b8cff); b.onChange = force; brush.current = b; if (viewer.internals().root()) b.attach(); force();
    return () => { b.dispose(); brush.current = null; };
  }, [viewer]);
  React.useEffect(() => { if (brush.current) { brush.current.enabled = tool === "model" && isBase; brush.current.erase = erase; } }, [tool, isBase, erase]);
  React.useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.target as HTMLElement).closest?.("input,textarea,select")) return; const b = brush.current; if (!b) return; if (e.key === "[") b.setSize(b.size * 0.85); else if (e.key === "]") b.setSize(b.size * 1.18); };
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
  }, []);

  // ---- the picture's mask: circles [x, y, r] in normalised canvas coordinates, drawn over the viewport
  const drawMask = React.useCallback(() => {
    const c = mask.current; if (!c) return; const r = c.getBoundingClientRect(); c.width = Math.max(1, Math.round(r.width)); c.height = Math.max(1, Math.round(r.height));
    const g = c.getContext("2d")!; g.clearRect(0, 0, c.width, c.height); g.fillStyle = "rgba(91,140,255,.45)";
    mstrokes.forEach(([x, y, rad]) => { g.beginPath(); g.arc(x * c.width, y * c.height, rad * c.width, 0, 7); g.fill(); });
  }, [mstrokes]);
  React.useEffect(() => { drawMask(); const c = mask.current; if (!c) return; const ro = new ResizeObserver(drawMask); ro.observe(c); return () => ro.disconnect(); }, [drawMask]);
  const mdab = (e: React.PointerEvent) => {
    const c = mask.current!, r = c.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height, rad = ((brush.current?.size ?? 3) / 100) * 0.6;
    setM((m) => (erase ? m.filter(([a, b]) => Math.hypot((a - x) * r.width, (b - y) * r.height) > rad * r.width) : [...m, [x, y, rad]]));
  };
  const maskDataURL = () => {
    if (!mstrokes.length || !ref) return null; const W = 768, H = Math.round(768 / ref.aspect), c = document.createElement("canvas"); c.width = W; c.height = H; const g = c.getContext("2d")!;
    g.fillStyle = "#000"; g.fillRect(0, 0, W, H); g.fillStyle = "#fff"; mstrokes.forEach(([x, y, r]) => { g.beginPath(); g.arc(x * W, y * H, r * W, 0, 7); g.fill(); }); return c.toDataURL("image/png");
  };

  // ---- cameras: the camera's pose in the model's own glTF frame (what the server projects from)
  const camJSON = (): CameraJSON => {
    const { camera, root } = viewer!.internals(); const m = root()!.matrixWorld.clone().invert().multiply(camera.matrixWorld);
    return { elements: m.elements.slice(), fov: camera.fov, aspect: camera.aspect, min_cos: 0.15, feather: 0.35 };
  };
  const setCamera = (elements: number[]) => {
    const { camera, controls, root } = viewer!.internals();
    const w = root()!.matrixWorld.clone().multiply(new THREE.Matrix4().fromArray(elements)), p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3(); w.decompose(p, q, s);
    const dist = camera.position.distanceTo(controls.target) || 3; camera.position.copy(p); camera.quaternion.copy(q);
    controls.target.copy(p).add(new THREE.Vector3(0, 0, -dist).applyQuaternion(q)); controls.update();
  };

  const pickFile = async (f: File | undefined) => {
    if (!f) return; const url = await readFile(f), im = new Image();
    im.onload = () => { setRefFile(url); setRefGen(null); setM([]); setRef({ url, aspect: im.naturalWidth / im.naturalHeight }); }; im.src = url;
  };

  const useOriginal = async () => {
    if (!original || !viewer) return; setBusy("orig");
    try {
      const url = await readFile(await (await fetch(original)).blob()), im = new Image(); await new Promise((res, rej) => { im.onload = res; im.onerror = rej; im.src = url; });
      const W = 256, H = Math.max(8, Math.round((256 * im.naturalHeight) / im.naturalWidth)), c = document.createElement("canvas"); c.width = W; c.height = H;
      const g = c.getContext("2d", { willReadFrequently: true })!; g.drawImage(im, 0, 0, W, H);
      const px = g.getImageData(0, 0, W, H).data, at = (x: number, y: number) => [px[(y * W + x) * 4], px[(y * W + x) * 4 + 1], px[(y * W + x) * 4 + 2]], edge: number[][] = [];
      for (let x = 0; x < W; x += 4) edge.push(at(x, 0), at(x, H - 1)); for (let y = 0; y < H; y += 4) edge.push(at(0, y), at(W - 1, y));
      const bg = [0, 1, 2].map((k) => edge.map((e) => e[k]).sort((p, q) => p - q)[edge.length >> 1]); let x0 = W, x1 = 0, y0 = H, y1 = 0;
      for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const p = at(x, y); if (Math.abs(p[0] - bg[0]) + Math.abs(p[1] - bg[1]) + Math.abs(p[2] - bg[2]) > 60) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); } }
      if (x1 <= x0 || y1 <= y0) throw new Error("no subject found in the picture");
      const asp = im.naturalWidth / im.naturalHeight;
      setRefFile(url); setRefGen(null); setM([]); setRef({ url, aspect: asp }); setSrc("ref"); setOpacity(45);
      await new Promise((r) => setTimeout(r, 400));      // let the stage take the picture's shape before the camera is set
      const { camera, controls, root } = viewer.internals();
      const box = new THREE.Box3().setFromObject(root()!), hm = box.max.y - box.min.y, f = (y1 - y0) / H, cxi = (x0 + x1) / 2 / W, cyi = (y0 + y1) / 2 / H, fov = 30, t = Math.tan(THREE.MathUtils.degToRad(fov / 2));
      const D = hm / (f * 2 * t), V = 2 * D * t, cx = (box.min.x + box.max.x) / 2, cy = (box.min.y + box.max.y) / 2;
      camera.fov = fov; camera.aspect = asp; camera.updateProjectionMatrix(); camera.quaternion.identity();
      const px_ = cx - (cxi - 0.5) * V * asp, py_ = cy - (0.5 - cyi) * V; camera.position.set(px_, py_, box.max.z + D); controls.target.set(px_, py_, box.max.z); controls.update();
      setHint("Matched to the picture's front view. Brush the part to restore, then Apply. Fine-tune with the Picture slider and Orbit if needed.");
      toast.success("Front view matched to your picture");
    } catch (e: any) { toast.error("Could not use the original picture: " + e.message); } finally { setBusy(null); }
  };

  const post = async (body: Record<string, unknown>) => { await api.retex(d.name, body); refetch(); };
  const generate = async () => { setBusy("gen"); try { await post({ mode: "generate", camera: camJSON(), notes: notes.trim() }); } catch (e: any) { toast.error(e.message); } finally { setBusy(null); } };
  const apply = async () => {
    setBusy("apply");
    try {
      const body: Record<string, unknown> = { mode: "project", strokes: brush.current?.strokes ?? [], mask: maskDataURL() };
      if (src === "ref" && refFile) { body.camera = camJSON(); body.ref = refFile; } else if (refGen) { body.camera = refGen.camera; body.ref_job = refGen.job; body.ref_name = refGen.name; }
      else throw new Error("Choose or generate a picture first.");
      await post(body);
    } catch (e: any) { toast.error(e.message); } finally { setBusy(null); }
  };
  const gen = jobs.find((j) => j.mode === "generate" && j.generated?.length);
  const pickGen = (job: RetexJob, name: string, url: string) => {
    if (!job.camera) return; const im = new Image();
    im.onload = () => { setRefGen({ job: job.job, name, camera: job.camera! }); setRefFile(null); setRef({ url, aspect: im.naturalWidth / im.naturalHeight }); setCamera(job.camera!.elements); }; im.src = url;
  };
  const canApply = isBase && (src === "ref" ? !!(refFile || refGen) : !!refGen);
  const applyMsg = !isBase ? "Showing a result: go back to the model to apply another." : !canApply ? (src === "ref" ? "Choose a reference picture first." : "Generate a view first.") : brush.current?.strokes.length ? "" : "No brush: the whole visible surface will change.";
  const size = brush.current?.size ?? 3;

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_400px]">
      <div className="grid content-start gap-3">
        <div className="mx-auto w-full" style={{ aspectRatio: String(ref?.aspect ?? 0.75), maxWidth: ref ? `min(100%, ${Math.round(ref.aspect * 640)}px)` : "min(100%, 520px)" }}>
          <div className="relative h-full w-full">
            <ModelViewer url={showing} toolbar={false} onViewer={setViewer} settings={NO_ROTATE} onLoaded={() => { brush.current?.attach(); force(); }} className={cn("absolute inset-0 border border-line", tool === "model" && "[&_canvas]:cursor-crosshair")}>
              {ref && <img src={ref.url} className="pointer-events-none absolute inset-0 h-full w-full" style={{ objectFit: "fill", opacity: opacity / 100 }} />}
              <canvas ref={mask} className="absolute inset-0 h-full w-full" style={{ pointerEvents: tool === "mask" ? "auto" : "none", cursor: tool === "mask" ? "crosshair" : undefined }}
                onPointerDown={(e) => { (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId); mdown.current = true; mdab(e); }} onPointerMove={(e) => mdown.current && mdab(e)} onPointerUp={() => (mdown.current = false)}
                onWheel={(e) => { if (!e.altKey) return; brush.current?.setSize(size * (e.deltaY < 0 ? 1.12 : 0.89)); }} />
              <div className="pointer-events-none absolute top-3 left-3 max-w-[70%] rounded-lg bg-black/45 px-2.5 py-1 text-[11px] text-ink-2 backdrop-blur">{isBase ? hint : "The retextured model"}</div>
            </ModelViewer>
          </div>
        </div>
        <div className="panel flex flex-wrap items-center gap-2 p-2">
          <Segmented value={tool} onValueChange={(v) => { setTool(v as any); setHint(v === "model" ? "Brush the part to change on the model" : v === "mask" ? "Paint the pixels of the picture that may be used" : "Drag to orbit"); }}
            options={[{ value: "model", label: <span className="flex items-center gap-1.5"><BrushIcon className="size-3.5" /> Brush model</span> }, ...(ref ? [{ value: "mask", label: <span className="flex items-center gap-1.5"><ImagePlus className="size-3.5" /> Mask picture</span> }] : []), { value: "orbit", label: <span className="flex items-center gap-1.5"><Move3d className="size-3.5" /> Orbit</span> }]} />
          <Button size="sm" variant={erase ? "primary" : "ghost"} onClick={() => setErase(!erase)}><Eraser /> Erase</Button>
          <div className="flex w-48 items-center gap-2 px-2"><span className="text-xs text-ink-3">Size</span><Slider value={size} onValueChange={(v) => brush.current?.setSize(v)} min={0.3} max={25} step={0.1} /><span className="w-9 font-mono text-[11px] text-ink-2">{size.toFixed(size < 10 ? 1 : 0)}%</span></div>
          <Button size="sm" variant="ghost" onClick={() => brush.current?.clear()}><Trash2 /> Brush</Button>
          {ref && <Button size="sm" variant="ghost" onClick={() => setM([])}><Trash2 /> Mask</Button>}
          <span className="h-5 w-px bg-white/10" />
          {[["Front", 0], ["Right", 90], ["Back", 180], ["Left", 270]].map(([l, az]) => <Button key={l} size="sm" variant="ghost" onClick={() => viewer?.view(az as number, 0)}>{l}</Button>)}
          {ref && <div className="flex w-40 items-center gap-2 px-2"><span className="text-xs text-ink-3">Picture</span><Slider value={opacity} onValueChange={setOpacity} min={0} max={100} /></div>}
        </div>
      </div>
      <div className="grid content-start gap-4">
        <Panel className="p-5">
          <h3 className="text-[15px] font-semibold">Retexture a part</h3>
          <p className="mt-1 mb-4 text-[13px] leading-relaxed text-ink-3">1. Brush the part to change. 2. Orbit to a view that shows it. 3. Pick where the new look comes from. The picture is projected onto the brushed area from that view.</p>
          <Segmented value={src} onValueChange={(v) => setSrc(v as any)} options={[{ value: "gen", label: "Describe it (generate)" }, { value: "ref", label: "Use a reference picture" }]} />
          {src === "gen" ? (
            <div className="mt-4 grid gap-3">
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. a worn brown leather jacket with white stitching and a small red patch on the shoulder" />
              <Button variant="primary" onClick={generate} loading={busy === "gen"}><Sparkles /> Generate this view</Button>
              <p className="text-[11px] text-ink-3">The image model redraws what you see in the viewer; the result is aligned with it (needs the GPU, about a minute).</p>
            </div>
          ) : (
            <div className="mt-4 grid gap-3">
              {original && <Button variant="primary" onClick={useOriginal} loading={busy === "orig"}><Wand2 /> Use the original picture</Button>}
              {original && <p className="-mt-1 text-[11px] text-ink-3">For logos, engravings and text the redraw changed: the model is set to the picture's front view; brush that part, then Apply.</p>}
              <label className="flex cursor-pointer items-center gap-3 rounded-xl border-2 border-dashed border-line-strong px-4 py-3 text-[13px] hover:border-accent/40">
                <input type="file" accept="image/*" className="hidden" onChange={(e) => pickFile(e.target.files?.[0])} /><ImagePlus className="size-5 text-accent" />
                <span><b>Choose a reference picture</b><span className="block text-xs text-ink-3">Seen from any angle; orbit until the model matches it, then paint which pixels to use.</span></span>
              </label>
            </div>
          )}
          {gen && (
            <div className="mt-4">
              <div className="mb-2 text-xs text-ink-3">Generated views, pick one (the viewer snaps back to the camera it was made from):</div>
              <div className="grid grid-cols-2 gap-2">
                {gen.generated!.map((g, i) => (
                  <button key={g.name} onClick={() => pickGen(gen, g.name, g.url)} className={cn("overflow-hidden rounded-lg border transition", refGen?.job === gen.job && refGen.name === g.name ? "border-accent shadow-glow" : "border-line")}>
                    <img src={g.url} className="aspect-square w-full object-cover" /><div className="py-1 text-[11px] text-ink-3">{i === 0 ? "first take" : "second take"}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="mt-4 flex items-center gap-3">
            <Button variant="success" onClick={apply} disabled={!canApply} loading={busy === "apply"}><Check /> Apply to the brushed area</Button>
          </div>
          {applyMsg && <p className="mt-2 text-[11px] text-ink-3">{applyMsg}</p>}
        </Panel>
        <div className="grid gap-3">
          {!jobs.length ? <div className="px-1 text-[13px] text-ink-3">No retextures yet.</div> : jobs.map((j) => {
            const active = j.status === "queued" || j.status === "running";
            return (
              <Panel key={j.job} className="p-4">
                <div className="mb-2 flex items-center gap-2"><b className="text-[13px]">{MODE_NAME[j.mode] ?? j.mode}</b><StatusPill status={j.status === "done" ? "finished" : j.status === "failed" ? "failed" : "running"} /><span className="ml-auto font-mono text-[11px] text-ink-3">{jobLabel(j.job)}</span></div>
                {j.notes && <p className="mb-2 text-xs text-ink-3">{j.notes}</p>}
                {j.error && <div className="mb-2 rounded-lg border border-bad/30 bg-bad/8 px-3 py-2 text-xs text-bad">{j.error}</div>}
                {j.before && j.after && <div className="grid grid-cols-2 gap-2"><Img src={j.before} className="aspect-square rounded-lg" onClick={() => lb([{ url: j.before!, title: "before" }, { url: j.after!, title: "after" }], 0)} /><Img src={j.after} className="aspect-square rounded-lg ring-1 ring-ok/40" onClick={() => lb([{ url: j.before!, title: "before" }, { url: j.after!, title: "after" }], 1)} /></div>}
                {active && <div className="mt-2 flex items-start gap-2 rounded-lg bg-black/40 p-2 font-mono text-[10.5px] text-ink-3"><Loader2 className="mt-0.5 size-3 shrink-0 animate-spin" /><div>{(j.log ?? []).map((l, i) => <div key={i}>{l}</div>)}</div></div>}
                {j.mode === "project" && j.result && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button size="sm" variant={showing === j.result ? "primary" : "secondary"} onClick={() => setShowing(j.result!)}><Eye /> View in 3D</Button>
                    <Button size="sm" variant="ghost" onClick={() => setShowing(base)}>Back to the model</Button>
                    {j.applied ? <span className="self-center text-[11px] text-ok">kept: on the rig and the clips</span> : <Button size="sm" variant="success" onClick={async () => { try { await post({ mode: "apply", from_job: j.job }); toast("Putting the texture on the rig and clips…"); } catch (e: any) { toast.error(e.message); } }}>Keep: put it on the rig and clips</Button>}
                  </div>
                )}
              </Panel>
            );
          })}
        </div>
      </div>
    </div>
  );
}
