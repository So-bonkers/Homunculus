import {
  Download, ScanSearch, Brain, Paintbrush, MousePointerClick, Sparkles, Layers, Box, ShieldCheck, Palette, Bone, PersonStanding, Clapperboard, Wand2, FileText,
  type LucideIcon,
} from "lucide-react";
import type { Review, Stage, StageStatus } from "./types";

export const ORDER = ["ingest", "upscale", "plan", "edit", "pick", "upscale_edit", "views", "mesh", "mesh_check", "color", "rig", "rig_check", "animate", "texture", "report"] as const;

export const STAGE_META: Record<string, { icon: LucideIcon; blurb: string }> = {
  ingest: { icon: Download, blurb: "The input is recorded (a mesh is welded, cleaned and given UVs)." },
  upscale: { icon: ScanSearch, blurb: "4× upscale with the model that fits the picture's style." },
  plan: { icon: Brain, blurb: "A vision-language model describes the character and writes the redraw prompt." },
  edit: { icon: Paintbrush, blurb: "The character is redrawn as a clean full-body T-pose with open hands." },
  pick: { icon: MousePointerClick, blurb: "One redraw is picked: by the judges, by you, or both." },
  upscale_edit: { icon: Sparkles, blurb: "The chosen redraw is cleaned and upscaled for the 3D model." },
  views: { icon: Layers, blurb: "Depth phase: the back is drawn under the depth map of a proxy shape, kept only if its outline agrees." },
  mesh: { icon: Box, blurb: "Pixal3D builds the 3D shape from the front (and back) view." },
  mesh_check: { icon: ShieldCheck, blurb: "The shape candidates are checked; torn hands are repaired." },
  color: { icon: Palette, blurb: "The picture is projected onto the mesh so the rig is built on a coloured model." },
  rig: { icon: Bone, blurb: "Make-It-Animatable builds a 52-bone Mixamo skeleton with skin weights." },
  rig_check: { icon: PersonStanding, blurb: "Test poses and a wrist-bend check." },
  animate: { icon: Clapperboard, blurb: "A dance from a video and/or text prompts become clips for this rig." },
  texture: { icon: Wand2, blurb: "The face is fitted from your picture; the final texture goes on the rig and every clip." },
  report: { icon: FileText, blurb: "Contact sheet, report and downloads." },
};

/** Stages a run can be restarted from, and which of them a graph node maps to. */
export const FORKABLE = ["upscale", "plan", "edit", "upscale_edit", "views", "mesh", "color", "rig", "animate", "texture", "report"] as const;
export const FORK_OF: Record<string, string | null> = {
  ingest: null, upscale: "upscale", plan: "plan", edit: "edit", pick: "edit", upscale_edit: "upscale_edit", views: "views", mesh: "mesh", mesh_check: "mesh",
  color: "color", rig: "rig", rig_check: "rig", animate: "animate", texture: "texture", report: "report",
};
export const FORK_LABEL: Record<string, string> = {
  upscale: "Upscale", plan: "Plan", edit: "Redraw", upscale_edit: "Prepare", views: "Views", mesh: "3D shape", color: "Colour", rig: "Auto-rig", animate: "Animate", texture: "Texture", report: "Report",
};
export const FORK_HINT: Record<string, string> = {
  upscale: "Everything is redone from the upscaled input.",
  plan: "The planner looks at the picture again and writes a new redraw prompt.",
  edit: "New redraws. Your instructions go straight into the redraw prompt.",
  upscale_edit: "Keeps the chosen redraw, prepares it again for 3D.",
  views: "Keeps the redraw; draws the back view again under a depth map, then the 3D shapes.",
  mesh: "Keeps the redraw; new 3D shapes. Instructions steer the judges.",
  color: "Keeps the 3D model; redoes the quick colours, then rigs, animates and textures.",
  rig: "Keeps the coloured model; rigs it again (pick another rigger below).",
  animate: "Keeps the rig; generates the animation clips again from the prompts you give.",
  texture: "Keeps the rig and the clips; redoes the final texture and puts it on all of them.",
  report: "Only rebuilds the report and downloads.",
};

export const GATE_STAGE: Record<string, string> = { pick: "pick", mesh_check: "mesh_check", rig_check: "rig_check", orient: "plan" };
const GATE_SOURCE: Record<string, string> = { pick: "edit", mesh_check: "mesh", rig_check: "rig" };

/** Stage statuses with the open review gate shown as "waiting" (and its source stage as done). */
export function effectiveStages(stages: Stage[], review: Review | null): Stage[] {
  const gate = review ? GATE_STAGE[review.gate] : undefined;
  return stages.map((s) => {
    if (gate && s.key === gate) return { ...s, status: "waiting" as StageStatus };
    if (gate && GATE_SOURCE[gate] === s.key && s.status === "running") return { ...s, status: "done" as StageStatus };
    return s;
  });
}

export const STATUS_TONE: Record<string, "ok" | "warn" | "bad" | "run" | "neutral"> = {
  done: "ok", finished: "ok", running: "run", waiting: "warn", failed: "bad", stopped: "neutral", skipped: "neutral", pending: "neutral",
};
export const RUN_STATUS_LABEL: Record<string, string> = { running: "Running", waiting: "Needs you", finished: "Finished", failed: "Failed", stopped: "Stopped" };

export const REPAIR_STEP: Record<string, string> = { queued: "Waiting for the GPU", regions: "Finding the region", running: "Working", merge: "Joining the new part", bake: "Baking the texture", done: "Done" };

export const GATE_NAME: Record<string, string> = { look: "Pick a look", pick: "Pick a redraw", mesh_check: "3D shape", rig_check: "Rig check", orient: "Front of the model" };

/** "20261013_034713" -> "13.10. 03:47"; other ids unchanged. */
export const jobLabel = (id: string) => id.replace(/^(\d{4})(\d\d)(\d\d)_(\d\d)(\d\d)(\d\d)$/, "$3.$2. $4:$5");
