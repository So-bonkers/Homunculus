import type { HandCurve } from "@/lib/types";

/** Quick hand gestures as timed runs of poses. dt is seconds from the playhead (the moment of the hit); inserting one replaces whatever that hand had over its span.
 *  The timings are animation estimates (a real finger snap lasts a few milliseconds, which a 30 fps clip cannot show; here it is anticipation 0.12 s, hit, release 0.14 s): edit the blocks after. */
export interface GestureKey { dt: number; pose: string; curve?: HandCurve; d?: number }
export interface Gesture { key: string; label: string; text: string; keys: GestureKey[]; wrist?: boolean }

const alt = (n: number, step: number, a: string, b: string): GestureKey[] => Array.from({ length: n }, (_, i) => ({ dt: i * step, pose: i % 2 ? b : a, curve: "linear" as HandCurve, d: step * 0.7 }));

export const GESTURES: Gesture[] = [
  { key: "snap", label: "Finger snap", text: "Thumb loads on the middle finger, then the finger slaps the palm.", keys: [{ dt: -0.12, pose: "snap_ready", curve: "quick" }, { dt: 0, pose: "snap_hit", curve: "snap" }, { dt: 0.14, pose: "soft", curve: "quick" }] },
  { key: "flick", label: "Finger flick", text: "Index loaded under the thumb, then flicked out.", keys: [{ dt: -0.1, pose: "flick_ready", curve: "quick" }, { dt: 0, pose: "point", curve: "snap" }, { dt: 0.16, pose: "fist_loose", curve: "quick" }] },
  { key: "pulse", label: "Clench and release", text: "A hard clench, then the hand pops open.", keys: [{ dt: 0, pose: "fist_tight", curve: "quick" }, { dt: 0.14, pose: "spread", curve: "snap" }, { dt: 0.36, pose: "soft", curve: "smooth" }] },
  { key: "burst", label: "Burst", text: "A tight fist explodes into wide fingers.", keys: [{ dt: -0.1, pose: "fist_tight", curve: "quick" }, { dt: 0, pose: "spread_wide", curve: "snap" }, { dt: 0.3, pose: "spread", curve: "smooth" }] },
  { key: "wave", label: "Finger wave", text: "The fingers close one after another from the pinky, then open.", keys: [{ dt: 0, pose: "wave1", curve: "quick" }, { dt: 0.06, pose: "wave2", curve: "quick" }, { dt: 0.12, pose: "wave3", curve: "quick" }, { dt: 0.18, pose: "wave4", curve: "quick" }, { dt: 0.42, pose: "open", curve: "smooth" }] },
  { key: "shake", label: "Jazz-hands shake", text: "Spread and claw alternating fast, about eight changes a second.", keys: [...alt(7, 0.075, "spread", "claw_spread"), { dt: 0.6, pose: "spread", curve: "smooth" }] },
  { key: "tap", label: "Finger tap", text: "The fingers drum, one after another: pinky, ring, middle, index.", keys: [{ dt: 0, pose: "wave1", curve: "quick" }, { dt: 0.08, pose: "open", curve: "quick" }, { dt: 0.12, pose: "wave2", curve: "quick" }, { dt: 0.2, pose: "open", curve: "quick" }, { dt: 0.24, pose: "wave3", curve: "quick" }, { dt: 0.32, pose: "open", curve: "quick" }, { dt: 0.36, pose: "point", curve: "quick" }, { dt: 0.44, pose: "open", curve: "smooth" }] },
];

/** Wrist gestures: the hand bending at the wrist, dropped at the playhead like the finger gestures. */
export const WRIST_GESTURES: Gesture[] = [
  { key: "wflick_down", label: "Wrist flick down", text: "The hand cocks back, then flicks down.", wrist: true, keys: [{ dt: -0.1, pose: "ext_40", curve: "quick" }, { dt: 0, pose: "flex_40", curve: "snap" }, { dt: 0.22, pose: "neutral", curve: "smooth" }] },
  { key: "wflick_up", label: "Wrist flick up", text: "The hand drops, then flicks up.", wrist: true, keys: [{ dt: -0.1, pose: "flex_40", curve: "quick" }, { dt: 0, pose: "ext_40", curve: "snap" }, { dt: 0.22, pose: "neutral", curve: "smooth" }] },
  { key: "wwave", label: "Wrist wave", text: "The hand swings toward the thumb and the pinky and back, about three times a second.", wrist: true, keys: [{ dt: 0, pose: "radial_20", curve: "smooth" }, { dt: 0.17, pose: "ulnar_30", curve: "smooth" }, { dt: 0.34, pose: "radial_20", curve: "smooth" }, { dt: 0.51, pose: "ulnar_30", curve: "smooth" }, { dt: 0.68, pose: "neutral", curve: "smooth" }] },
  { key: "wcircle", label: "Wrist circle", text: "The hand draws a circle: in, toward the pinky, back, toward the thumb.", wrist: true, keys: [{ dt: 0, pose: "flex_40", curve: "smooth" }, { dt: 0.15, pose: "flex_ulnar", curve: "smooth" }, { dt: 0.3, pose: "ext_ulnar", curve: "smooth" }, { dt: 0.45, pose: "ext_radial", curve: "smooth" }, { dt: 0.6, pose: "flex_radial", curve: "smooth" }, { dt: 0.75, pose: "neutral", curve: "smooth" }] },
];
