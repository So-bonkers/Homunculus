import * as React from "react";
import { Link, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Command } from "cmdk";
import { Activity, BookOpen, Boxes, CircleHelp, Compass, Film, Library, Plus, Search, Stethoscope } from "lucide-react";
import { useLive, useRuns } from "@/lib/api";
import { Button, Dot, Kbd, Tip } from "@/components/ui";
import { LightboxProvider, StatusPill } from "@/components/common";
import { DoctorDialog } from "@/features/dialogs/DoctorDialog";
import { cn } from "@/lib/utils";
import Home from "@/pages/Home";
import NewRun from "@/pages/NewRun";
import RunPage from "@/pages/Run";
import LibraryPage from "@/pages/Library";
import SystemPage from "@/pages/System";
import AnimatePage from "@/pages/Animate";
import { useVersionReload } from "@/lib/version";
import { TourProvider, useTour } from "@/features/tour/Tour";

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-7">
      <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#c9baff" /><stop offset="1" stopColor="#5b8cff" /></linearGradient></defs>
      <rect width="32" height="32" rx="9" fill="#14121f" stroke="rgba(255,255,255,.08)" />
      <circle cx="16" cy="10" r="4.2" fill="url(#lg)" />
      <path d="M7 16h18M16 15v8M16 23l-4 5M16 23l4 5" stroke="url(#lg)" strokeWidth="2.6" strokeLinecap="round" fill="none" />
    </svg>
  );
}

function LiveChip() {
  const { data: live } = useLive();
  const nav = useNavigate();
  if (!live?.length) return null;
  return (
    <button onClick={() => nav(`/run/${encodeURIComponent(live[0])}`)} className="flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs text-[#d4c9ff] transition hover:bg-accent/20">
      <Dot tone="run" pulse />
      {live.length === 1 ? <span><b className="font-semibold">{live[0]}</b> running</span> : <span>{live.length} runs active</span>}
    </button>
  );
}

function Palette({ open, setOpen, onDoctor }: { open: boolean; setOpen: (v: boolean) => void; onDoctor: () => void }) {
  const { data: runs } = useRuns();
  const nav = useNavigate();
  const go = (p: string) => { setOpen(false); nav(p); };
  const tour = useTour();
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[14vh] backdrop-blur-sm" onClick={() => setOpen(false)}>
      <Command className="w-[min(640px,92vw)] overflow-hidden rounded-2xl border border-line-strong bg-overlay shadow-2xl" onClick={(e) => e.stopPropagation()} loop>
        <div className="flex items-center gap-2 border-b border-line px-4">
          <Search className="size-4 text-ink-3" />
          <Command.Input autoFocus placeholder="Jump to a run, start one, check the system…" className="h-12 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-3" />
          <Kbd>esc</Kbd>
        </div>
        <Command.List className="max-h-[50vh] overflow-y-auto p-2">
          <Command.Empty className="px-3 py-6 text-center text-[13px] text-ink-3">Nothing matches.</Command.Empty>
          <Command.Group heading="Actions" className="px-1 py-1 text-[11px] text-ink-3 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1">
            {[
              { k: "new", label: "New run", icon: Plus, run: () => go("/new") },
              { k: "runs", label: "All runs", icon: Boxes, run: () => go("/") },
              { k: "anim", label: "Animate a character with a video", icon: Film, run: () => go("/animate") },
              { k: "lib", label: "Animation library", icon: Library, run: () => go("/library") },
              { k: "tour", label: "Take the guided tour", icon: Compass, run: () => { setOpen(false); tour.start(); } },
              { k: "sys", label: "Check the system", icon: Stethoscope, run: () => { setOpen(false); onDoctor(); } },
              { k: "docs", label: "Documentation on GitHub", icon: BookOpen, run: () => { setOpen(false); window.open("https://github.com/So-bonkers/Homunculus#readme", "_blank"); } },
            ].map((a) => (
              <Command.Item key={a.k} onSelect={a.run} className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] text-ink data-[selected=true]:bg-white/6">
                <a.icon className="size-4 text-ink-3" />{a.label}
              </Command.Item>
            ))}
          </Command.Group>
          {!!runs?.length && (
            <Command.Group heading="Runs" className="px-1 py-1 text-[11px] text-ink-3 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1">
              {runs.map((r) => (
                <Command.Item key={r.name} value={`run ${r.name} ${r.file}`} onSelect={() => go(`/run/${encodeURIComponent(r.name)}`)} className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-[13px] text-ink data-[selected=true]:bg-white/6">
                  {r.thumb ? <img src={r.thumb} className="size-7 rounded-md object-cover" /> : <div className="size-7 rounded-md bg-white/6" />}
                  <span className="flex-1 truncate">{r.name}</span>
                  <StatusPill status={r.status} />
                </Command.Item>
              ))}
            </Command.Group>
          )}
        </Command.List>
      </Command>
    </div>
  );
}

function TourButton() {
  const tour = useTour();
  return <Tip content="A two-minute guided tour"><Button data-tour="tour" variant="ghost" size="icon" onClick={tour.start}><Compass /></Button></Tip>;
}

export default function App() {
  const [pal, setPal] = React.useState(false);
  const [doctor, setDoctor] = React.useState(false);
  const loc = useLocation();
  useVersionReload();

  React.useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPal((v) => !v); } if (e.key === "Escape") setPal(false); };
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
  }, []);
  React.useEffect(() => { window.scrollTo({ top: 0 }); }, [loc.pathname]);

  const link = ({ isActive }: { isActive: boolean }) => cn("rounded-lg px-3 py-1.5 text-[13px] transition", isActive ? "bg-white/8 text-ink" : "text-ink-3 hover:text-ink");

  return (
    <LightboxProvider>
      <TourProvider>
      <div className="flex min-h-full flex-col">
        <header className="glass sticky top-0 z-30 flex h-14 items-center gap-4 border-x-0 border-t-0 px-4 lg:px-6">
          <Link to="/" className="flex items-center gap-2.5">
            <Logo />
            <span className="text-[15px] font-semibold tracking-tight">Homunculus</span>
            <span className="rounded-md border border-line-strong px-1.5 py-0.5 font-mono text-[10px] text-ink-3">v2.0</span>
          </Link>
          <nav className="ml-4 hidden items-center gap-1 md:flex" data-tour="nav">
            <NavLink to="/" end className={link}>Runs</NavLink>
            <NavLink to="/new" className={link}>New run</NavLink>
            <NavLink to="/animate" className={link}>Animate</NavLink>
            <NavLink to="/library" className={link}>Library</NavLink>
            <NavLink to="/system" className={link}>System</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <LiveChip />
            <button data-tour="search" onClick={() => setPal(true)} className="hidden h-8 items-center gap-2 rounded-lg border border-line-strong bg-black/20 px-3 text-xs text-ink-3 transition hover:text-ink-2 sm:flex">
              <Search className="size-3.5" /> Search <Kbd>⌘K</Kbd>
            </button>
            <Tip content="Check that the services, models and GPU are ready"><Button data-tour="doctor" variant="ghost" size="icon" onClick={() => setDoctor(true)}><Activity /></Button></Tip>
            <TourButton />
            <span className="hidden sm:inline-flex"><Tip content="Tips for good results"><Link to="/?tips=1"><Button variant="ghost" size="icon"><CircleHelp /></Button></Link></Tip></span>
            <Link to="/new"><Button variant="primary" size="sm" aria-label="New run"><Plus /><span className="hidden sm:inline">New run</span></Button></Link>
          </div>
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b border-line px-3 py-1.5 [scrollbar-width:none] md:hidden">
          <NavLink to="/" end className={link}>Runs</NavLink>
          <NavLink to="/new" className={link}>New run</NavLink>
          <NavLink to="/animate" className={link}>Animate</NavLink>
          <NavLink to="/library" className={link}>Library</NavLink>
          <NavLink to="/system" className={link}>System</NavLink>
        </nav>
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/runs" element={<Home />} />
            <Route path="/tips" element={<Home />} />
            <Route path="/new" element={<NewRun />} />
            <Route path="/run/:name" element={<RunPage />} />
            <Route path="/animate" element={<AnimatePage />} />
            <Route path="/animate/:name" element={<AnimatePage />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/system" element={<SystemPage />} />
            <Route path="*" element={<Home />} />
          </Routes>
        </main>
      </div>
      <Palette open={pal} setOpen={setPal} onDoctor={() => setDoctor(true)} />
      <DoctorDialog open={doctor} onOpenChange={setDoctor} />
      </TourProvider>
    </LightboxProvider>
  );
}
