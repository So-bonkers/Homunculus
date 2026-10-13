import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Dices, Play, Plus, Search, Sparkles, Check, X } from "lucide-react";
import { usePresetManifest } from "@/lib/api";
import { Badge, Button, Input, Segmented } from "@/components/ui";
import { ModelViewer } from "@/components/ModelViewer";
import { cn } from "@/lib/utils";

export interface Category { name: string; icon: string; prompts: string[] }

/** The prompt library lives in homunculus/static/prompt_library.js (also read by preset_clips.py): loaded at run time, one source of truth. */
export function useLibrary() {
  return useQuery({
    queryKey: ["library"], staleTime: Infinity,
    queryFn: async () => {
      const m = await import(/* @vite-ignore */ `${location.origin}/static/prompt_library.js`);
      return (m.LIBRARY as any[]).map((c) => ({ name: c.cat ?? c.name ?? c.title, icon: c.icon ?? "", prompts: c.prompts ?? c.items ?? [] })) as Category[];
    },
  });
}

const lines = (s: string) => s.split("\n").map((l) => l.trim()).filter(Boolean);

export function PresetPreview({ prompt, onClose, selected, onToggle }: { prompt: string; onClose: () => void; selected: boolean; onToggle: () => void }) {
  const { data: man } = usePresetManifest(true);
  const models = man ? Object.keys(man.models) : [];
  const [model, setModel] = React.useState(() => { try { return localStorage.getItem("presetModel") || "male"; } catch { return "male"; } });
  const [take, setTake] = React.useState(0);
  const clips = man?.models[model]?.clips?.[prompt] ?? [];
  const m = man?.models[model];
  return (
    <div className="grid gap-3 rounded-xl border border-line-strong bg-black/30 p-3 sm:grid-cols-[260px_1fr]">
      <ModelViewer url={clips[take] ? `/static/presets/${clips[take]}` : null} className="h-64" toolbar={false} emptyText="This preview is not generated yet." />
      <div className="flex min-w-0 flex-col gap-3">
        <div className="text-[13px] text-ink">An object {prompt}.</div>
        <div className="flex flex-wrap items-center gap-2">
          {models.length > 0 && <Segmented value={model} onValueChange={(v) => { setModel(v); setTake(0); try { localStorage.setItem("presetModel", v); } catch { /* private mode */ } }} options={models.map((k) => ({ value: k, label: man!.models[k].label || k }))} />}
          {clips.length > 1 && <Segmented value={String(take)} onValueChange={(v) => setTake(+v)} options={clips.map((_, i) => ({ value: String(i), label: `Take ${i + 1}` }))} />}
        </div>
        {m && <p className="text-[11px] leading-snug text-ink-3">"{m.title}" by {m.author} is licensed under {m.license}. Animated locally by UniMate.</p>}
        <div className="mt-auto flex gap-2">
          <Button size="sm" variant={selected ? "secondary" : "primary"} onClick={onToggle}>{selected ? <><X /> Remove from my prompts</> : <><Plus /> Add to my prompts</>}</Button>
          <Button size="sm" variant="ghost" onClick={onClose}>Close preview</Button>
        </div>
      </div>
    </div>
  );
}

export function PresetPicker({ value, onChange, disabled, defaultOpen }: { value: string; onChange: (v: string) => void; disabled?: boolean; defaultOpen?: boolean }) {
  const [open, setOpen] = React.useState(!!defaultOpen);
  const { data: lib } = useLibrary();
  const { data: man } = usePresetManifest(open);
  const [cat, setCat] = React.useState(0);
  const [qs, setQs] = React.useState("");
  const [preview, setPreview] = React.useState<string | null>(null);
  const chosen = new Set(lines(value).map((l) => l.toLowerCase()));
  const total = lib?.reduce((n, c) => n + c.prompts.length, 0) ?? 190;
  const hasPreview = (p: string) => !!man && Object.values(man.models).some((m) => m.clips?.[p]?.length);
  const toggle = (p: string) => {
    const ls = lines(value);
    onChange((chosen.has(p.toLowerCase()) ? ls.filter((l) => l.toLowerCase() !== p.toLowerCase()) : [...ls, p]).join("\n"));
  };
  const surprise = () => {
    const all = lib?.flatMap((c) => c.prompts).filter((p) => !chosen.has(p.toLowerCase())) ?? [];
    const pick = [...all].sort(() => Math.random() - 0.5).slice(0, 3);
    onChange([...lines(value), ...pick].join("\n"));
  };
  const shown = qs ? lib?.flatMap((c) => c.prompts).filter((p) => p.toLowerCase().includes(qs.toLowerCase())) ?? [] : lib?.[cat]?.prompts ?? [];
  const previews = man ? lib?.flatMap((c) => c.prompts).filter(hasPreview).length ?? 0 : 0;

  return (
    <div className={cn("rounded-xl border border-line bg-white/[0.015]", disabled && "pointer-events-none opacity-50")}>
      <button type="button" onClick={() => setOpen((v) => !v)} className="flex w-full items-center gap-3 px-4 py-3 text-left">
        <Sparkles className="size-4 text-accent" />
        <span className="text-[13px] font-medium text-ink">Preset library</span>
        <span className="text-xs text-ink-3">{total} prompts in {lib?.length ?? 10} categories</span>
        {chosen.size > 0 && <Badge tone="accent">{chosen.size} selected</Badge>}
        <ChevronDown className={cn("ml-auto size-4 text-ink-3 transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="grid gap-3 border-t border-line p-4">
          <div className="flex gap-2">
            <div className="relative flex-1"><Search className="absolute top-2.5 left-3 size-4 text-ink-3" /><Input value={qs} onChange={(e) => setQs(e.target.value)} placeholder="Search presets: dance, sword, jump…" className="pl-9" /></div>
            <Button type="button" variant="secondary" onClick={surprise}><Dices /> Surprise me</Button>
          </div>
          {!qs && (
            <div className="flex flex-wrap gap-1.5">
              {lib?.map((c, i) => {
                const n = c.prompts.filter((p) => chosen.has(p.toLowerCase())).length;
                return (
                  <button type="button" key={c.name} onClick={() => setCat(i)} className={cn("flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition", i === cat ? "border-accent/50 bg-accent/15 text-ink" : "border-line-strong text-ink-2 hover:text-ink")}>
                    <span>{c.icon}</span>{c.name}{n > 0 && <span className="rounded-full bg-accent px-1.5 text-[10px] text-white">{n}</span>}
                  </button>
                );
              })}
            </div>
          )}
          {qs && <div className="text-xs text-ink-3">{shown.length} matches for "{qs}"</div>}
          <div className="flex flex-wrap gap-1.5">
            {shown.map((p) => {
              const on = chosen.has(p.toLowerCase());
              return (
                <span key={p} className={cn("group inline-flex items-center overflow-hidden rounded-lg border text-xs transition", on ? "border-accent/50 bg-accent/15 text-ink" : "border-line-strong text-ink-2 hover:border-white/20 hover:text-ink")}>
                  <button type="button" onClick={() => toggle(p)} className="flex items-center gap-1.5 px-2.5 py-1.5">{on && <Check className="size-3 text-accent" />}{p}</button>
                  {hasPreview(p) && <button type="button" title="Preview in 3D" onClick={() => setPreview(p)} className="border-l border-white/10 px-2 py-1.5 text-ink-3 hover:bg-white/8 hover:text-ink"><Play className="size-3" /></button>}
                </span>
              );
            })}
          </div>
          {preview && <PresetPreview prompt={preview} onClose={() => setPreview(null)} selected={chosen.has(preview.toLowerCase())} onToggle={() => toggle(preview)} />}
          <div className="flex items-center justify-between text-[11px] text-ink-3">
            <span>{chosen.size} selected · 3D previews for {previews} of {total}{man ? "" : " (none generated on this machine yet: python -m homunculus.preset_clips)"}</span>
            {chosen.size > 0 && <button type="button" className="hover:text-ink" onClick={() => onChange(lines(value).filter((l) => !lib?.some((c) => c.prompts.some((p) => p.toLowerCase() === l.toLowerCase()))).join("\n"))}>Clear presets</button>}
          </div>
        </div>
      )}
    </div>
  );
}
