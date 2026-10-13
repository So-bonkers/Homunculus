import * as React from "react";
import { Copy, Library as LibIcon, Play, Search } from "lucide-react";
import { toast } from "sonner";
import { usePresetManifest } from "@/lib/api";
import { Badge, Input, Panel, Spinner } from "@/components/ui";
import { PresetPreview, useLibrary } from "@/features/PresetPicker";
import { cn } from "@/lib/utils";

export default function LibraryPage() {
  const { data: lib, isLoading } = useLibrary();
  const { data: man } = usePresetManifest(true);
  const [qs, setQs] = React.useState("");
  const [preview, setPreview] = React.useState<string | null>(null);
  const has = (p: string) => !!man && Object.values(man.models).some((m) => m.clips?.[p]?.length);
  const total = lib?.reduce((n, c) => n + c.prompts.length, 0) ?? 0;
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 lg:px-6">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold tracking-[0.14em] text-ink-3 uppercase"><LibIcon className="size-3.5" /> Library</div>
          <h1 className="text-3xl font-semibold tracking-tight">Animation prompts</h1>
          <p className="mt-2 max-w-2xl text-[14px] text-ink-3">{total} ready-made text prompts for UniMate in {lib?.length ?? 10} categories. Add them in a run's Animate tab or when you start a run; for a real dance, copy it from a video instead.</p>
        </div>
        <div className="relative w-72"><Search className="absolute top-2.5 left-3 size-4 text-ink-3" /><Input value={qs} onChange={(e) => setQs(e.target.value)} placeholder="Search: dance, sword, jump…" className="pl-9" /></div>
      </div>
      {!man && <div className="mb-6 rounded-xl border border-line bg-white/[0.02] px-4 py-3 text-[13px] text-ink-3">3D previews are not generated on this machine yet (about 90 minutes per character): <code className="font-mono text-ink-2">python -m homunculus.preset_clips</code></div>}
      {preview && <div className="mb-6"><PresetPreview prompt={preview} onClose={() => setPreview(null)} selected={false} onToggle={() => { navigator.clipboard?.writeText(preview); toast("Copied the prompt"); }} /></div>}
      {isLoading ? <Spinner /> : (
        <div className="columns-1 gap-4 md:columns-2 xl:columns-3">
          {lib?.map((c) => {
            const ps = c.prompts.filter((p) => !qs || p.toLowerCase().includes(qs.toLowerCase()));
            if (!ps.length) return null;
            return (
              <Panel key={c.name} className="mb-4 break-inside-avoid p-5">
                <div className="mb-3 flex items-center gap-2"><span className="text-xl">{c.icon}</span><h2 className="text-[15px] font-semibold">{c.name}</h2><Badge className="ml-auto">{ps.length}</Badge></div>
                <div className="flex flex-wrap gap-1.5">
                  {ps.map((p) => (
                    <span key={p} className="group inline-flex items-center overflow-hidden rounded-lg border border-line-strong text-xs text-ink-2 transition hover:border-white/20 hover:text-ink">
                      <button className="px-2.5 py-1.5" onClick={() => { navigator.clipboard?.writeText(p); toast("Copied the prompt"); }} title="Copy">{p}</button>
                      {has(p) ? <button onClick={() => setPreview(p)} className="border-l border-white/10 px-2 py-1.5 text-ink-3 hover:bg-white/8 hover:text-ink"><Play className="size-3" /></button>
                        : <span className={cn("border-l border-white/10 px-2 py-1.5 text-ink-3 opacity-0 group-hover:opacity-100")}><Copy className="size-3" /></span>}
                    </span>
                  ))}
                </div>
              </Panel>
            );
          })}
        </div>
      )}
    </div>
  );
}
