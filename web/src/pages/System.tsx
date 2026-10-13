import { RefreshCw, Stethoscope } from "lucide-react";
import { useDoctor } from "@/lib/api";
import { Button, Panel, Spinner } from "@/components/ui";
import { DoctorList, DoctorSummary } from "@/features/dialogs/DoctorDialog";

export default function SystemPage() {
  const { data, isFetching, refetch } = useDoctor(true);
  const groups: [string, (n: string) => boolean][] = [
    ["Services and GPU", (n) => /Studio|GPU|Blender|ComfyUI Python|systemd|disk|node/i.test(n)],
    ["Models", (n) => /Pixal3D|DINO|VAE|Upscaler|Qwen|Make-It|UniMate|GVHMR|SkinTokens|landmark/i.test(n)],
    ["Python packages", (n) => /^python:/i.test(n)],
  ];
  const used = new Set<string>();
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 lg:px-6">
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold tracking-[0.14em] text-ink-3 uppercase"><Stethoscope className="size-3.5" /> System</div>
          <h1 className="text-3xl font-semibold tracking-tight">Is everything there?</h1>
          <p className="mt-2 max-w-2xl text-[14px] text-ink-3">Every service, model and package the pipeline needs, checked live on this machine, with the command that fixes what is missing.</p>
        </div>
        <div className="flex items-center gap-3">{data && <DoctorSummary checks={data} />}<Button onClick={() => refetch()} loading={isFetching}><RefreshCw /> Check again</Button></div>
      </div>
      {!data ? <div className="flex items-center gap-3 text-[13px] text-ink-3"><Spinner /> Checking…</div> : (
        <div className="grid gap-6">
          {[...groups.map(([title, test]) => { const xs = data.filter((c) => !used.has(c.name) && test(c.name)); xs.forEach((c) => used.add(c.name)); return [title, xs] as const; }),
            ["Other", data.filter((c) => !used.has(c.name))] as const].filter(([, xs]) => xs.length).map(([title, xs]) => (
            <Panel key={title} className="min-w-0 p-5 [overflow-wrap:anywhere]">
              <h2 className="mb-3 text-sm font-semibold">{title}</h2>
              <DoctorList checks={xs as any} />
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}
