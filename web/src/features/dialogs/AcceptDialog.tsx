import * as React from "react";
import { toast } from "sonner";
import { CheckCircle2, Download, PackageCheck } from "lucide-react";
import { api, useAccept, useInvalidate } from "@/lib/api";
import { Button, Dialog, Spinner } from "@/components/ui";
import { bytes, cn } from "@/lib/utils";

export function AcceptDialog({ run, open, onOpenChange }: { run: string; open: boolean; onOpenChange: (v: boolean) => void }) {
  const [running, setRunning] = React.useState(false);
  const { data } = useAccept(run, open, running);
  const inv = useInvalidate();
  const [sel, setSel] = React.useState<Set<string>>(new Set());
  const [cleanup, setCleanup] = React.useState(false);
  const st = data?.status?.status;
  React.useEffect(() => { setRunning(st === "running"); if (st === "done") inv(["run", run]); }, [st]);      // eslint-disable-line react-hooks/exhaustive-deps

  const go = async () => {
    try { await api.accept(run, [...sel], cleanup); setRunning(true); inv(["accept", run]); }
    catch (e: any) { toast.error(e.message); }
  };
  const pkg = `/api/package/${encodeURIComponent(run)}.zip`;
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={<span className="flex items-center gap-2"><PackageCheck className="size-4 text-ok" /> {run}: happy with it?</span>}
      description="The pipeline keeps GLB only. Pick the other formats you want: they are made from the GLBs now and added to the package."
      footer={<><Button variant="ghost" onClick={() => onOpenChange(false)}>Close</Button><Button variant="primary" onClick={go} loading={running} disabled={!data}>{data?.accepted ? "Export more" : "Accept & export"}</Button></>}>
      {!data ? <div className="flex items-center gap-3 text-[13px] text-ink-3"><Spinner /> Loading…</div> : (
        <div className="grid gap-3">
          <label className="flex items-center gap-3 rounded-xl border border-line bg-white/[0.02] px-4 py-3 text-[13px] opacity-70">
            <input type="checkbox" checked disabled className="accent-[var(--color-accent)]" /><b>GLB</b><span className="text-ink-3">rigged character and every clip (always)</span>
          </label>
          {Object.entries(data.formats).map(([k, f]) => (
            <label key={k} className={cn("flex cursor-pointer items-center gap-3 rounded-xl border border-line px-4 py-3 text-[13px] transition hover:bg-white/[0.03]", !f.available && "pointer-events-none opacity-40")}>
              <input type="checkbox" disabled={!f.available} checked={sel.has(k)} onChange={(e) => setSel((s) => { const n = new Set(s); e.target.checked ? n.add(k) : n.delete(k); return n; })} className="accent-[var(--color-accent)]" />
              <b className="uppercase">{k}</b><span className="text-ink-3">{f.label.replace(/^[A-Z]+:\s*/, "")}</span>
            </label>
          ))}
          {data.cleanup.total > 50 * 1024 * 1024 && (
            <label className="flex cursor-pointer gap-3 rounded-xl border border-warn/25 bg-warn/5 px-4 py-3 text-[13px]">
              <input type="checkbox" checked={cleanup} onChange={(e) => setCleanup(e.target.checked)} className="mt-0.5 accent-[var(--color-accent)]" />
              <span><b>Free {bytes(data.cleanup.total)}</b> by deleting files only needed to fork from an early stage or to repair: <span className="text-ink-3">{data.cleanup.items.map((i) => `${i.label} (${bytes(i.bytes)})`).join("; ")}</span>. Not undoable.</span>
            </label>
          )}
          {st === "running" && <div className="flex items-center gap-3 rounded-lg bg-white/4 px-3 py-2 font-mono text-xs text-ink-2"><Spinner /> {data.status?.log?.slice(-1)[0] || "exporting…"}</div>}
          {st === "failed" && <div className="rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-[13px] text-bad">Failed: {data.status?.error}</div>}
          {(st === "done" || data.accepted) && (
            <div className="flex items-center justify-between gap-3 rounded-xl border border-ok/25 bg-ok/8 px-4 py-3 text-[13px]">
              <span className="flex items-center gap-2"><CheckCircle2 className="size-4 text-ok" /> Accepted{data.accepted ? ` ${data.accepted.time} · ${data.accepted.formats.join(", ").toUpperCase()}` : ""}{data.accepted?.freed ? ` · freed ${bytes(data.accepted.freed)}` : ""}</span>
              <a href={pkg} download><Button size="sm" variant="success"><Download /> Package</Button></a>
            </div>
          )}
        </div>
      )}
    </Dialog>
  );
}
