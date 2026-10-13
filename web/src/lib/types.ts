// Shapes of the JSON the Python server sends (homunculus/api.py, server.py). Field names are the server's.

export type RunStatus = "finished" | "waiting" | "running" | "failed" | "stopped";
export type StageStatus = "pending" | "running" | "done" | "failed" | "stopped" | "skipped" | "waiting";

export interface RepairPill { job: string; status: string; step: string }

export interface RunSummary {
  name: string; status: RunStatus; live: boolean;
  thumb: string | null; input: string | null; file: string;
  done: number; total: number; current: string | null; repair: RepairPill | null; last: string | null;
  t_start: number | null; t_total: number | null; updated: number; outfit?: string; model: string | null;
}

export interface Stage { key: string; label: string; model: string; status: StageStatus; seconds?: number | null; note?: string | null; peak_vram?: number | null }

export interface Review {
  gate: "pick" | "mesh_check" | "rig_check" | "orient" | string;
  title: string; verdict: string; manual: boolean; grace: number; opened: number | null;
  judge_best: number; choose: boolean; you_judge: boolean; kind: string; images: string[]; captions: string[];
}

export interface Snapshot { n: number; time: string; stage: string; label: string; title: string; url?: string; text?: string; images?: { url: string; caption?: string }[] }

export interface Clip {
  id: string; prompt: string; rep: number; url: string; fbx: string | null; thumb: string | null; textured: boolean;
  source?: "video"; video?: string | null; compare?: string | null;
}

export interface Animations { status: "idle" | "queued" | "running" | "done" | "failed"; error: string | null; clips: Clip[] }
export interface Looks { status: "queued" | "running" | "done"; raw: string; asis?: string; items: { look: string; label: string; url: string; time: string }[] }
export interface ModelRef { key: string; label: string; url: string }

export interface RunOptions {
  auto_repair?: string; face_source?: string; texture?: string; face?: string; face_redraw?: boolean; rigger?: string;
  anim_prompts?: string[]; anim_reps?: number; direct?: boolean; look?: string; outfit?: string; review?: string; grace?: number; style?: string;
}

export interface RunDetail {
  name: string; status: RunStatus; live: boolean; file: string; input: string | null; thumb: string | null;
  t_start: number | null; t_total: number | null; now: number; mode: "image" | "mesh";
  models_pending: number; repair: RepairPill | null; looks: Looks | null; animations: Animations | null;
  options: RunOptions; stages: Stage[]; review: Review | null; snapshots: Snapshot[];
  files: { label: string; url: string; name: string }[]; models: ModelRef[];
  zip: string | null; package: string | null; plan: Record<string, unknown>;
  human_reviews: { gate: string; title?: string; action: string; choice: number; notes: string; time: string }[];
  log: string[]; forked_from: { run: string; stage: string; time: string; notes: string } | null;
  accepted: { time: string; formats: string[]; freed: number } | null; zip_on: boolean;
  alert: { msg: string; time: string } | null; human_notes: string;
}

export interface Region {
  index: number; group: number; label: string; status: string; awaiting: boolean; info?: string[];
  crop?: string; candidates?: string[]; chosen?: string; after?: string; after_fingers?: number | null; checked?: boolean; by?: string; five_fingers?: boolean;
}
export interface RepairJob {
  job: string; status: "queued" | "running" | "done" | "failed"; step: string; error?: string | null; log: string[]; notes?: string;
  label?: string; view?: string; groups?: { label: string; view: string }[]; seconds?: number; regions: Region[];
  result?: string | null; textured?: string | null; can_use?: boolean;
}

export interface RetexJob {
  job: string; mode: "project" | "generate" | "apply"; status: string; error?: string | null; notes?: string; log?: string[];
  result?: string | null; before?: string | null; after?: string | null; camera?: CameraJSON; generated?: { name: string; url: string }[]; applied?: boolean;
}
export interface RetexInfo { base: string | null; original: string | null; jobs: RetexJob[] }
export interface CameraJSON { elements: number[]; fov: number; aspect: number; min_cos: number; feather: number }

export interface AcceptInfo {
  formats: Record<string, { label: string; available: boolean }>;
  cleanup: { items: { label: string; bytes: number }[]; total: number };
  accepted: { time: string; formats: string[]; freed: number } | null;
  status: { status: "running" | "done" | "failed"; log?: string[]; done?: string[]; formats?: string[]; freed?: number; error?: string } | null;
}
export interface PurgeInfo { run: string; items: { label: string; bytes: number }[]; total: number; busy: string[] }
export interface DoctorCheck { name: string; status: "ok" | "warn" | "fail"; detail: string; fix: string }

export interface PresetManifest {
  models: Record<string, { label: string; title: string; author: string; url: string; license: string; license_url: string; clips: Record<string, string[]>; done?: number }>;
  reps?: number; total?: number; status?: string;
}
