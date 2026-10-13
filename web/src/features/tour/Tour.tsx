import * as React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ArrowRight, Compass, X } from "lucide-react";
import { useRuns } from "@/lib/api";
import type { RunSummary } from "@/lib/types";
import { Button, Kbd } from "@/components/ui";
import { cn } from "@/lib/utils";

/** The guided tour: a spotlight on one part of the app and a card that explains it, page by page (home, new run, a run, the Animate page).
 *  Steps point at data-tour="…" attributes; a step whose target is not on the page (no runs yet, no dance yet) is skipped. */

type Ctx = { run: string | null };
interface Step { part: string; path: (c: Ctx) => string | null; sel: string[]; title: string; text: React.ReactNode }

const STEPS: Step[] = [
  { part: "Home", path: () => "/", sel: ['[data-tour="hero"]'], title: "Welcome to Homunculus", text: "A picture (or a 3D model) in; a textured, rigged and animated character out. Every model runs on this machine. This tour takes two minutes and shows where everything is." },
  { part: "Home", path: () => "/", sel: ['[data-tour="nav"]'], title: "Find your way", text: <><b>Runs</b> lists everything you have made, <b>New run</b> starts one, <b>Animate</b> makes a finished character dance a video, <b>Library</b> has 190 text prompts for motions, <b>System</b> shows the GPU, the services and the disk.</> },
  { part: "Home", path: () => "/", sel: ['[data-tour="runs"]'], title: "Your runs", text: "Each card shows the live status of a run. Open one to follow it, judge it, see it in 3D and animate it; fork or delete it from the card's menu." },
  { part: "Home", path: () => "/", sel: ['[data-tour="search"]'], title: "Jump anywhere", text: <>Press <Kbd>Ctrl</Kbd> <Kbd>K</Kbd> to find a run or an action by typing.</> },
  { part: "Home", path: () => "/", sel: ['[data-tour="doctor"]'], title: "Check the machine", text: "Makes sure ComfyUI, Studio, Blender, the models and enough free VRAM are all there before you start something long." },

  { part: "New run", path: () => "/new", sel: ['[data-tour="nr-drop"]'], title: "1 · Drop your input", text: "A picture (JPG, PNG, WebP) or a 3D model (STL, OBJ, PLY, GLB, FBX). A 3D model skips the picture steps and is painted and rigged as it is." },
  { part: "New run", path: () => "/new", sel: ['[data-tour="nr-input"]'], title: "2 · What you are giving it", text: "A single picture is redrawn as a clean T-pose. A clean reference or a character sheet can be used as it is." },
  { part: "New run", path: () => "/new", sel: ['[data-tour="nr-look"]'], title: "3 · The look", text: "Keep the picture's style or restyle it. “All · I pick” draws one candidate per look and lets you choose." },
  { part: "New run", path: () => "/new", sel: ['[data-tour="nr-review"]'], title: "4 · Who decides", text: "At the redraw pick, the shape check and the rig check: three AI judges with a window for you to overrule them, you alone, or nobody (fully automatic)." },
  { part: "New run", path: () => "/new", sel: ['[data-tour="nr-anim"]'], title: "5 · Animation", text: "A dance from a video is the default. You can also type motions in plain words, or add both later from the run." },
  { part: "New run", path: () => "/new", sel: ['[data-tour="nr-start"]'], title: "6 · Start", text: "About 50 minutes on one 24 GB GPU. Close the browser any time: the run keeps going and the desktop notifies you when it needs you." },

  { part: "A run", path: (c) => c.run && `/run/${encodeURIComponent(c.run)}`, sel: ['[data-tour="header"]'], title: "A run", text: "Its status, its input and the actions: Stop while it runs; Fork (redo from any stage), Accept (export) and Package when it is done." },
  { part: "A run", path: (c) => c.run && `/run/${encodeURIComponent(c.run)}`, sel: ['[data-tour="pipeline"]'], title: "The pipeline", text: "Fifteen stages from the picture to the final texture. The running one pulses; ↺ marks the gates that can retry. Click a stage to see its snapshots." },
  { part: "A run", path: (c) => c.run && `/run/${encodeURIComponent(c.run)}`, sel: ['[data-tour="tabs"]'], title: "Everything about it", text: "Activity tells the story with pictures, 3D model has the viewer (clay, wireframe, bones), Animate the clips, Repair and Retexture fix what came out wrong, Log the raw log." },
  { part: "A run", path: (c) => c.run && `/run/${encodeURIComponent(c.run)}`, sel: ['[data-tour="inspector"]'], title: "Downloads and details", text: "The rigged model in GLB or FBX, the report, and what the planner wrote about this character." },
  { part: "A run", path: (c) => c.run && `/run/${encodeURIComponent(c.run)}?tab=animate`, sel: ['[data-tour="video"]'], title: "Animate from the run", text: "Copy a dance from a video, or type motions. The clips play in the viewer below; a dance plays next to its video." },

  { part: "Animate", path: (c) => (c.run ? `/animate/${encodeURIComponent(c.run)}` : "/animate"), sel: ['[data-tour="anim-character"]'], title: "Animate a finished character", text: "No new run needed: choose any character that has a rig…" },
  { part: "Animate", path: (c) => (c.run ? `/animate/${encodeURIComponent(c.run)}` : "/animate"), sel: ['[data-tour="anim-video"]'], title: "…a video, and the part to copy", text: "Drop a video of one person dancing. Drag the two handles, or play it and press Start here / End here. The preview loops your range." },
  { part: "Animate", path: (c) => (c.run ? `/animate/${encodeURIComponent(c.run)}` : "/animate"), sel: ['[data-tour="anim-start"]'], title: "See the cost before you start", text: "The estimate and the time it will be done by follow the length you chose. If a run is using the GPU, the dance waits its turn." },
  { part: "Animate", path: (c) => c.run && `/animate/${encodeURIComponent(c.run)}`, sel: ['[data-tour="job"]', "#jobs"], title: "Follow it stage by stage", text: "Cut, body motion, camera, retarget, texture, preview, side by side: each with its time, a report you can open, and the time left (adjusted to how fast this machine is going). When it is done, the video and your character play together." },
  { part: "Done", path: () => null, sel: [], title: "That's the tour", text: "Start it again any time from the compass in the top bar. Have fun making things dance." },
];

const DONE = "homunculus_tour_done", OFFERED = "homunculus_tour_offered";
const store = { get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } } };

const TourCtx = React.createContext<{ start: () => void }>({ start: () => {} });
export const useTour = () => React.useContext(TourCtx);

function pickRun(runs: RunSummary[] | undefined) {
  const r = runs ?? [];
  return (r.find((x) => x.rigged && (x.dances ?? 0) > 0) ?? r.find((x) => x.rigged && x.status === "finished") ?? r.find((x) => x.rigged) ?? r.find((x) => x.status === "finished") ?? r[0])?.name ?? null;
}

export function TourProvider({ children }: { children: React.ReactNode }) {
  const [i, setI] = React.useState<number | null>(null);
  const [offer, setOffer] = React.useState(false);
  const { data: runs } = useRuns();
  const ctx: Ctx = { run: pickRun(runs) };

  React.useEffect(() => {      // the first visit offers the tour once
    if (store.get(DONE) || store.get(OFFERED)) return;
    const t = setTimeout(() => setOffer(true), 1800); return () => clearTimeout(t);
  }, []);

  const start = React.useCallback(() => { setOffer(false); store.set(OFFERED, "1"); setI(0); }, []);
  const end = React.useCallback(() => { setI(null); store.set(DONE, "1"); }, []);

  return (
    <TourCtx.Provider value={{ start }}>
      {children}
      {i !== null && <Runner i={i} setI={setI} end={end} ctx={ctx} />}
      <AnimatePresence>
        {offer && i === null && (
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 16 }} className="glass fixed right-4 bottom-4 z-50 w-[min(340px,calc(100vw-32px))] rounded-2xl p-4 shadow-2xl">
            <div className="mb-1 flex items-center gap-2"><Compass className="size-4 text-accent" /><b className="text-[14px]">New here?</b></div>
            <p className="mb-3 text-[13px] text-ink-2">A two-minute tour of the studio: starting a run, following it, and making a character dance a video.</p>
            <div className="flex gap-2"><Button variant="primary" size="sm" onClick={start}>Take the tour</Button><Button variant="ghost" size="sm" onClick={() => { setOffer(false); store.set(OFFERED, "1"); }}>Not now</Button></div>
          </motion.div>
        )}
      </AnimatePresence>
    </TourCtx.Provider>
  );
}

type Rect = { x: number; y: number; w: number; h: number; top: number };      // top: where the spotlight may start (below the sticky header, unless the target is in it)

function Runner({ i, setI, end, ctx }: { i: number; setI: (n: number) => void; end: () => void; ctx: Ctx }) {
  const nav = useNavigate(); const loc = useLocation();
  const [rect, setRect] = React.useState<Rect | null>(null);
  const [found, setFound] = React.useState(false);
  const [vw, setVw] = React.useState({ w: innerWidth, h: innerHeight });
  const dir = React.useRef(1);
  const step = STEPS[i];
  const go = React.useCallback((n: number) => { dir.current = n >= i ? 1 : -1; if (n < 0) return; if (n >= STEPS.length) return end(); setI(n); }, [i, end, setI]);

  // go to the step's page, wait for its target, then follow the target's box (it moves while the page scrolls and animates)
  React.useEffect(() => {
    setFound(false); setRect(null);
    const want = step.path(ctx);
    if (step.sel.length && !want) { go(i + dir.current); return; }
    if (want && loc.pathname + loc.search !== want) { nav(want); }
    if (!step.sel.length) { setFound(true); return; }
    let el: Element | null = null, raf = 0, tries = 0, alive = true;
    const find = () => {
      if (!alive) return;
      el = step.sel.map((s) => document.querySelector(s)).find(Boolean) ?? null;
      if (el) { setFound(true); el.scrollIntoView({ behavior: "smooth", block: (el as HTMLElement).offsetHeight > innerHeight * 0.6 ? "start" : "center" }); follow(); }
      else if (++tries < 40) setTimeout(find, 100);
      else go(i + dir.current);        // not on this page (no runs yet, no dance yet): skip it
    };
    const follow = () => {
      raf = requestAnimationFrame(follow);
      const b = el!.getBoundingClientRect();
      const top = el!.closest("header") ? 4 : 62;
      setRect((r) => (r && Math.abs(r.x - b.left) < 0.5 && Math.abs(r.y - b.top) < 0.5 && Math.abs(r.w - b.width) < 0.5 && Math.abs(r.h - b.height) < 0.5 ? r : { x: b.left, y: b.top, w: b.width, h: b.height, top }));
    };
    setTimeout(find, want && loc.pathname + loc.search !== want ? 250 : 0);
    return () => { alive = false; cancelAnimationFrame(raf); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i]);

  React.useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") end(); if (e.key === "ArrowRight" || e.key === "Enter") go(i + 1); if (e.key === "ArrowLeft") go(i - 1); };
    const rs = () => setVw({ w: innerWidth, h: innerHeight });
    addEventListener("keydown", k); addEventListener("resize", rs); return () => { removeEventListener("keydown", k); removeEventListener("resize", rs); };
  }, [i, go, end]);

  // the spotlight is the target's box (clipped to the screen); the card goes below it, above it, or inside a tall one
  const pad = 8, cw = Math.min(360, vw.w - 32), ch = 210;
  const hole = rect && { x: Math.max(6, rect.x - pad), y: Math.max(rect.top, rect.y - pad), r: Math.min(vw.w - 6, rect.x + rect.w + pad), b: Math.min(vw.h - 6, rect.y + rect.h + pad) };
  let card = { left: (vw.w - cw) / 2, top: vw.h / 2 - ch / 2 };
  if (hole && hole.b > hole.y) {
    const left = Math.max(16, Math.min(vw.w - cw - 16, (hole.x + hole.r) / 2 - cw / 2));
    if (hole.b + 14 + ch < vw.h) card = { left, top: hole.b + 14 };
    else if (hole.y - 14 - ch > 62) card = { left, top: hole.y - 14 - ch };
    else card = { left: Math.max(16, Math.min(vw.w - cw - 16, hole.r - cw - 16)), top: Math.max(76, hole.b - ch - 16) };
  }
  const parts = [...new Set(STEPS.map((s) => s.part))];

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-label="Guided tour">
      <div className="absolute inset-0" onClick={(e) => e.stopPropagation()} />
      {hole && hole.b > hole.y ? (
        <motion.div className="pointer-events-none absolute rounded-[14px] ring-2 ring-accent/70" initial={false}
          animate={{ left: hole.x, top: hole.y, width: hole.r - hole.x, height: hole.b - hole.y }} transition={{ type: "spring", stiffness: 260, damping: 32 }}
          style={{ boxShadow: "0 0 0 9999px rgb(4 5 8 / 0.72), 0 0 40px 4px rgb(139 108 255 / 0.35)" }} />
      ) : <div className="absolute inset-0 bg-[rgb(4_5_8/0.72)]" />}
      <AnimatePresence mode="wait">
        {(found || !step.sel.length) && (
          <motion.div key={i} initial={{ opacity: 0, y: 8, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.22 }}
            className="absolute rounded-2xl border border-line-strong bg-overlay p-5 shadow-2xl" style={{ left: card.left, top: card.top, width: cw }}>
            <div className="mb-3 flex items-center gap-2">
              {parts.map((p) => <span key={p} className={cn("h-1 flex-1 rounded-full", p === step.part ? "bg-accent" : parts.indexOf(p) < parts.indexOf(step.part) ? "bg-accent/40" : "bg-white/10")} title={p} />)}
            </div>
            <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold tracking-[0.12em] text-ink-3 uppercase">{step.part}<span className="ml-auto font-mono tracking-normal normal-case">{i + 1} / {STEPS.length}</span></div>
            <h3 className="mb-1.5 text-[16px] font-semibold tracking-tight">{step.title}</h3>
            <p className="text-[13px] leading-relaxed text-ink-2">{step.text}</p>
            <div className="mt-4 flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={end}><X /> {i === STEPS.length - 1 ? "Close" : "Skip tour"}</Button>
              <div className="ml-auto flex gap-1.5">
                {i > 0 && <Button size="sm" onClick={() => go(i - 1)}><ArrowLeft /> Back</Button>}
                <Button variant="primary" size="sm" onClick={() => go(i + 1)}>{i === STEPS.length - 1 ? "Finish" : <>Next <ArrowRight /></>}</Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
