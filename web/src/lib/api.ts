// The HTTP API of the Python server. POST bodies are JSON (the server reads the raw body); the two uploads send raw bytes with options in the query string.
import { useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import type { AcceptInfo, DoctorCheck, PresetManifest, PurgeInfo, RepairJob, RetexInfo, RunDetail, RunSummary, VideoJob, HandsInfo, HandTracks, HandPose, HandMoves } from "./types";

export class ApiError extends Error { status: number; constructor(msg: string, status: number) { super(msg); this.status = status; } }

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) { let m = `HTTP ${r.status}`; try { m = (await r.json()).error || m; } catch { /* plain text */ } throw new ApiError(m, r.status); }
  return r.json();
}

export async function post<T = { ok: true }>(path: string, body: unknown): Promise<T> {
  let r: Response;
  try { r = await fetch(path, { method: "POST", body: JSON.stringify(body) }); }
  catch { throw new ApiError("Could not reach the Homunculus server.", 0); }
  const text = await r.text(); let j: any = {};
  try { j = text ? JSON.parse(text) : {}; } catch { j = { error: text }; }      // /api/review answers errors in plain text
  if (!r.ok) throw new ApiError(j.error || text || `HTTP ${r.status}`, r.status);
  return j as T;
}

/** Raw-body upload with progress (images for a run, videos for dance-from-video). */
export function upload<T = { ok: true; run?: string }>(path: string, body: Blob, onProgress?: (fraction: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest(); x.open("POST", path);
    x.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
    x.onload = () => { let j: any = {}; try { j = JSON.parse(x.responseText || "{}"); } catch { j = { error: x.responseText }; }
      x.status >= 200 && x.status < 300 ? resolve(j) : reject(new ApiError(j.error || `HTTP ${x.status}`, x.status)); };
    x.onerror = () => reject(new ApiError("Could not reach the Homunculus server.", 0));
    x.send(body);
  });
}

export const q = (o: Record<string, string | number | boolean | undefined | null>) =>
  Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");

/* ---------------------------------------------------------------- queries */
export const useLive = () => useQuery({ queryKey: ["live"], queryFn: () => get<string[]>("/api/live"), refetchInterval: 5000 });
export const useRuns = () => useQuery({ queryKey: ["runs"], queryFn: () => get<RunSummary[]>("/api/runs"), refetchInterval: 4000 });
export const useRun = (name: string) =>
  useQuery({ queryKey: ["run", name], queryFn: () => get<RunDetail>(`/api/run/${encodeURIComponent(name)}`), refetchInterval: 2000, placeholderData: keepPreviousData, retry: false });
export const useRepairs = (name: string, active: boolean) =>
  useQuery({ queryKey: ["repair", name], queryFn: () => get<RepairJob[]>(`/api/repair/${encodeURIComponent(name)}`), refetchInterval: active ? 2500 : false });
export const useRetex = (name: string, active: boolean) =>
  useQuery({ queryKey: ["retex", name], queryFn: () => get<RetexInfo>(`/api/retex/${encodeURIComponent(name)}`), refetchInterval: active ? 2500 : false });
export const useAccept = (name: string, enabled: boolean, running: boolean) =>
  useQuery({ queryKey: ["accept", name], queryFn: () => get<AcceptInfo>(`/api/accept/${encodeURIComponent(name)}`), enabled, refetchInterval: running ? 2000 : false });
export const usePurge = (name: string, enabled: boolean) => useQuery({ queryKey: ["purge", name], queryFn: () => get<PurgeInfo>(`/api/purge/${encodeURIComponent(name)}`), enabled, staleTime: 0 });
export const useVideoJobs = (name: string | null | undefined) =>
  useQuery({ queryKey: ["video", name], queryFn: () => get<VideoJob[]>(`/api/video/${encodeURIComponent(name!)}`), enabled: !!name,
    refetchInterval: (qq) => (qq.state.data?.some((j) => j.status === "queued" || j.status === "running") ? 1500 : 8000) });
export const useHands = (run: string, clip: string) =>
  useQuery({ queryKey: ["hands", run, clip], queryFn: () => get<HandsInfo>(`/api/hands/${encodeURIComponent(run)}/${encodeURIComponent(clip)}`),
    refetchInterval: (qq) => (qq.state.data?.status === "running" || qq.state.data?.llm?.status === "running" ? 1500 : false) });
export const useHandMoves = () => useQuery({ queryKey: ["handmoves"], queryFn: () => get<HandMoves>(`/static/hands/moves.json?v=${Date.now() >> 16}`), staleTime: 3600_000 });
export const useHandPoses = () => useQuery({ queryKey: ["handposes"], queryFn: () => get<HandPose[]>(`/static/hands/catalogue.json?v=${Date.now() >> 16}`), staleTime: 3600_000 });
export const useDoctor = (enabled: boolean) => useQuery({ queryKey: ["doctor"], queryFn: () => get<DoctorCheck[]>("/api/doctor"), enabled, staleTime: 0, gcTime: 0 });
export const usePresetManifest = (enabled: boolean) =>
  useQuery({ queryKey: ["presets"], queryFn: () => get<PresetManifest>(`/static/presets/manifest.json?t=${Date.now()}`).catch(() => null), enabled, staleTime: 60000 });

export function useInvalidate() {
  const qc = useQueryClient();
  return (...keys: unknown[][]) => keys.forEach((k) => qc.invalidateQueries({ queryKey: k }));
}

/* ---------------------------------------------------------------- actions */
export const api = {
  stop: (run: string) => post("/api/stop", { run }),
  fork: (body: Record<string, unknown>) => post<{ ok: true; run: string }>("/api/fork", body),
  looks: (run: string) => post("/api/looks", { run }),
  animate: (run: string, prompts: string[], reps: number) => post("/api/animate", { run, prompts, reps }),
  handPoses: (run: string) => post("/api/animate", { run, hands: true }),
  review: (run: string, gate: string, action: string, choice: number, notes: string) => post("/api/review", { run, gate, action, choice, notes }),
  repair: (run: string, groups: unknown[], notes: string, manual: boolean) => post<{ ok: true; job: string }>("/api/repair", { run, groups, notes, manual }),
  repairChoose: (run: string, job: string, group: number, region: number, choice: number | "more") => post("/api/repair_choose", { run, job, group, region, choice }),
  repairUse: (run: string, job: string, mode: "new" | "same", name: string) => post<{ ok: true; run: string }>("/api/repair_use", { run, job, mode, name }),
  retex: (run: string, body: Record<string, unknown>) => post<{ ok: true; job: string }>("/api/retex", { run, ...body }),
  accept: (run: string, formats: string[], cleanup: boolean) => post("/api/accept", { run, formats, cleanup }),
  hands: (run: string, clip: string, tracks: HandTracks) => post("/api/hands", { run, clip, tracks }),
  handsLlm: (run: string, clip: string, stop = false, opts: { fps?: number; thinking?: boolean; model?: string } = {}) => post("/api/hands/llm", { run, clip, stop, ...opts }),
  handsLlmResult: (run: string, clip: string) => get<{ tracks: HandTracks; meta: { how?: string }; finished: number | null; final?: boolean; upto?: number; chunk?: number }>(`/api/hands/${encodeURIComponent(run)}/${encodeURIComponent(clip)}/llm`),
  remove: (run: string) => post<{ ok: true; freed: number }>("/api/delete", { run }),
};
