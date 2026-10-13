import * as React from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { api, usePurge, useInvalidate } from "@/lib/api";
import { Button, Dialog, Spinner } from "@/components/ui";
import { bytes } from "@/lib/utils";

export function DeleteDialog({ run, open, onOpenChange, onDone }: { run: string; open: boolean; onOpenChange: (v: boolean) => void; onDone?: () => void }) {
  const { data, isFetching } = usePurge(run, open);
  const inv = useInvalidate();
  const [busy, setBusy] = React.useState(false);
  const go = async () => {
    setBusy(true);
    try { const r = await api.remove(run); toast.success(`Deleted ${run} · freed ${bytes(r.freed)}`); inv(["runs"]); onOpenChange(false); onDone?.(); }
    catch (e: any) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={<span className="flex items-center gap-2"><Trash2 className="size-4 text-bad" /> Delete {run}?</span>}
      description="This permanently removes the run and everything made for it. It cannot be undone."
      footer={<><Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button><Button variant="danger" onClick={go} loading={busy} disabled={!data || !!data.busy?.length}>Delete permanently</Button></>}>
      {isFetching && !data ? <div className="flex items-center gap-3 text-[13px] text-ink-3"><Spinner /> Measuring…</div> : data && (
        <div className="grid gap-3">
          {!!data.busy?.length && <div className="rounded-lg border border-warn/30 bg-warn/10 px-3 py-2 text-[13px] text-warn">Still running: {data.busy.join(", ")}. Stop it first.</div>}
          <div className="divide-y divide-line overflow-hidden rounded-xl border border-line">
            {data.items.map((i) => (
              <div key={i.label} className="flex items-center justify-between gap-3 px-4 py-2 text-[13px]"><span className="truncate text-ink-2">{i.label}</span><span className="font-mono text-xs text-ink-3">{bytes(i.bytes)}</span></div>
            ))}
            <div className="flex items-center justify-between bg-white/[0.02] px-4 py-2 text-[13px] font-semibold"><span>Total</span><span className="font-mono">{bytes(data.total)}</span></div>
          </div>
        </div>
      )}
    </Dialog>
  );
}
