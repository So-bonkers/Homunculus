import { CheckCircle2, AlertTriangle, XCircle, RefreshCw } from "lucide-react";
import { useDoctor } from "@/lib/api";
import { Badge, Button, Dialog, Spinner } from "@/components/ui";
import type { DoctorCheck } from "@/lib/types";

export function DoctorList({ checks }: { checks: DoctorCheck[] }) {
  return (
    <div className="divide-y divide-line overflow-hidden rounded-xl border border-line">
      {checks.map((c) => (
        <div key={c.name} className="flex gap-3 bg-white/[0.015] px-4 py-3">
          <div className="pt-0.5">
            {c.status === "ok" ? <CheckCircle2 className="size-4 text-ok" /> : c.status === "warn" ? <AlertTriangle className="size-4 text-warn" /> : <XCircle className="size-4 text-bad" />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-medium text-ink">{c.name}</div>
            <div className="truncate text-xs text-ink-3" title={c.detail}>{c.detail}</div>
            {c.status !== "ok" && c.fix && <div className="mt-1.5 rounded-md bg-black/30 px-2 py-1 font-mono text-[11px] leading-relaxed text-ink-2">{c.fix}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function DoctorSummary({ checks }: { checks: DoctorCheck[] }) {
  const fail = checks.filter((c) => c.status === "fail").length, warn = checks.filter((c) => c.status === "warn").length;
  return fail ? <Badge tone="bad">{fail} need attention</Badge> : warn ? <Badge tone="warn">ready · {warn} optional part{warn > 1 ? "s" : ""} missing</Badge> : <Badge tone="ok">all good</Badge>;
}

export function DoctorDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { data, isFetching, refetch } = useDoctor(open);
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Is everything there?" description="Services, models, Blender, free VRAM and disk, checked live."
      footer={<><span className="mr-auto">{data && <DoctorSummary checks={data} />}</span><Button variant="ghost" onClick={() => refetch()} disabled={isFetching}><RefreshCw /> Check again</Button></>}>
      {isFetching && !data ? <div className="flex items-center gap-3 py-10 text-[13px] text-ink-3"><Spinner /> Checking (Blender and the services take a few seconds)…</div> : data ? <DoctorList checks={data} /> : null}
    </Dialog>
  );
}
