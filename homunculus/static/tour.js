// Tips and the guided tour. The tour is a spotlight + a card that walks through the real elements of the page; steps whose element is not on screen are skipped.
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch {} } };

export const TIPS = [
  ["🧍", "One character, full body, facing the camera", "A single person or character, head to feet, looking at the camera. Busy backgrounds and text overlays are removed for you."],
  ["🙌", "Arms away from the body, hands open", "The redraw puts everyone into a rig-friendly T-pose anyway, but a closer start keeps the face more faithful and the rig cleaner."],
  ["🔎", "Small or blurry pictures are fine", "The picture is upscaled first. A sharper start still gives a better face."],
  ["⚡", "Already have a clean reference?", "Switch on “Use my picture as is” to skip the redraw. It works best for full-body T/A-pose pictures with open hands on a plain background."],
  ["🎭", "Describe the motion, not the character", "“walks forward”, “dances salsa, stepping side to side”, “does a spinning kick”. One motion per line. The Preset library has 190 ready-made prompts, many with a ▶ preview."],
  ["⚖️", "Pick how much you want to decide", "Override: the judges decide and you have a short window to overrule them. Manual: you are the judge, one candidate at a time. Off: fully automatic."],
  ["🗿", "Have a 3D model instead?", "Drop an STL, OBJ, PLY, GLB or FBX. Humanoids that are not in a T-pose are put into one first. Capes and long hair get dragged along with the arms."],
  ["🎨", "Chibi looks are risky", "Big heads and short limbs confuse the auto-rigger. “As is”, “3D film” and “Game” rig most reliably."],
  ["🖥️", "Give it the whole GPU", "Close games, Blender and other GPU apps. One run uses all 24 GB, one model at a time, and takes around 50 minutes. Runs queue behind each other."],
  ["🔁", "Something looks wrong?", "Stop the run and Fork it from any stage, with new instructions or a different choice. The original stays untouched."],
];

export function tipsHTML() {
  return `<div class="tips">${TIPS.map(([i, t, d]) => `<div class="tip reveal"><span class="ti">${i}</span><div><b>${esc(t)}</b><p>${esc(d)}</p></div></div>`).join("")}</div>`;
}

const HOME = [
  { sel: ".hero .ctas", title: "Welcome to Homunculus", text: "One picture (or 3D model) in, a textured, rigged and animated character out, built by models running on this machine. This 1-minute tour shows where everything is." },
  { sel: "#drop", title: "1 · Drop your input", text: "A picture (JPG, PNG, WebP) or a 3D model (STL, OBJ, PLY, GLB, FBX). A 3D model skips the picture steps and is painted and rigged as it is." },
  { sel: "#direct", up: ".switch", title: "Use my picture as is", text: "Skip the redraw when your picture is already a clean full-body T/A-pose reference." },
  { sel: '[data-seg="look"]', up: ".field", title: "2 · Choose a look", text: "Keep the picture's style or restyle it. “All · I pick” makes one candidate per look and lets you choose." },
  { sel: '[data-seg="review"]', up: ".field", title: "3 · Decide who judges", text: "Override: three AI judges decide and you can overrule them in a short window. Manual: you are the judge. Off: fully automatic." },
  { sel: '[data-seg="rigger"]', up: ".field", title: "4 · Pick the rigger", text: "Make-It-Animatable builds the 52-bone Mixamo skeleton. The normal-aware variant is the fallback." },
  { sel: "#anim", up: ".field", title: "5 · Type animation prompts", text: "One motion per line, e.g. “walks forward”. Open the Preset library below the box for 190 ready-made prompts and ▶ previews on a male and a female character." },
  { sel: "#go", up: ".go", title: "6 · Start the run", text: "A run takes around 50 minutes on one 24 GB GPU. Close the browser any time: it keeps going and you get a desktop notification when it needs you." },
  { sel: "#tips", title: "Tips for good results", text: "Short advice on pictures, prompts and review modes." },
  { sel: "#runlist", title: "Your runs", text: "Every run with live status and a Stop button. Open one to follow it, review it, view it in 3D and add animations." },
];
const RUN = [
  { sel: ".rhead", title: "A run", text: "The status, the input and the buttons for this run: Stop while it runs; Fork, Mixamo zip and View in 3D when it has stopped or finished." },
  { sel: "#flow", title: "The pipeline", text: "Fourteen stages as a graph. The current one shows a spinner. Click a stage for its details and snapshots; drag to pan, Ctrl/⌘ + scroll to zoom." },
  { sel: "#review", title: "Your call", text: "At every judge decision the candidates appear here, large. Choose one, accept or reject, add notes for the next try, or let the judges decide when the countdown ends." },
  { sel: '[data-seg="tab"]', up: ".seg", title: "Tabs", text: "Activity: the story so far. Looks: preview other styles. Animate: type or pick prompts and play the clips. 3D model: viewer with clay, wireframe and bones. Log: the raw text log." },
  { sel: ".rgrid > aside, .rgrid > div:last-child", title: "Downloads and details", text: "Rigged FBX/GLB with the final texture, the report, and the plan the planner wrote for this character." },
];

let live = null;
function close(done) { if (!live) return; live.root.remove(); removeEventListener("keydown", live.key); removeEventListener("resize", live.pos); removeEventListener("scroll", live.pos, true); if (done) store.set("homunculus_tour_done", "1"); live = null; }

export function startTour(kind = "home") {
  close(); const all = kind === "run" ? RUN : HOME;
  const target = (s) => { const el = $(s.sel); const e = el && (s.up ? el.closest(s.up) || el : el); return e && e.getClientRects().length ? e : null; };
  const steps = all.filter((s) => target(s));
  if (!steps.length) return;
  const root = document.createElement("div"); root.className = "tour";
  root.innerHTML = `<div class="tour-spot"></div><div class="tour-card" role="dialog" aria-live="polite"><div class="tour-n"></div><b class="tour-t"></b><p class="tour-p"></p>
    <div class="tour-dots"></div><div class="tour-act"><button type="button" class="btn btn-ghost btn-sm" data-t="skip">Skip tour</button><span></span><button type="button" class="btn btn-ghost btn-sm" data-t="back">Back</button><button type="button" class="btn btn-primary btn-sm" data-t="next">Next</button></div></div>`;
  document.body.appendChild(root);
  let i = 0; const spot = $(".tour-spot", root), card = $(".tour-card", root);
  const pos = () => {
    const el = target(steps[i]); if (!el) return; const r = el.getBoundingClientRect(), pad = 10;
    Object.assign(spot.style, { left: r.left - pad + "px", top: r.top - pad + "px", width: r.width + pad * 2 + "px", height: r.height + pad * 2 + "px" });
    const cw = card.offsetWidth, ch = card.offsetHeight, vw = innerWidth, vh = innerHeight; let top = r.bottom + pad + 14;
    if (top + ch > vh - 12) top = r.top - pad - 14 - ch; if (top < 12) top = Math.min(vh - ch - 12, Math.max(12, r.top + 16));
    card.style.top = top + "px"; card.style.left = Math.max(12, Math.min(vw - cw - 12, r.left + r.width / 2 - cw / 2)) + "px";
  };
  const show = () => {
    const s = steps[i], el = target(s); el.scrollIntoView({ block: "center", behavior: "smooth" });
    $(".tour-n", root).textContent = `${i + 1} of ${steps.length}`; $(".tour-t", root).textContent = s.title; $(".tour-p", root).textContent = s.text;
    $(".tour-dots", root).innerHTML = steps.map((_, k) => `<i class="${k === i ? "on" : ""}"></i>`).join("");
    $('[data-t="back"]', root).style.visibility = i ? "visible" : "hidden"; $('[data-t="next"]', root).textContent = i === steps.length - 1 ? "Done" : "Next";
    pos(); setTimeout(pos, 350); setTimeout(pos, 800);
  };
  const go = (d) => { const n = i + d; if (n >= steps.length) return close(true); if (n < 0) return; i = n; show(); };
  root.onclick = (e) => { const b = e.target.closest("[data-t]"); if (!b) return; ({ next: () => go(1), back: () => go(-1), skip: () => close(true) })[b.dataset.t](); };
  const key = (e) => { if (e.key === "Escape") close(true); else if (e.key === "ArrowRight" || e.key === "Enter") go(1); else if (e.key === "ArrowLeft") go(-1); };
  addEventListener("keydown", key); addEventListener("resize", pos); addEventListener("scroll", pos, true);
  live = { root, key, pos }; show();
}
export const stopTour = () => close(false);

export function offerTour(kind = "home") {
  if (store.get("homunculus_tour_done") || store.get("homunculus_tour_offered") || $(".tour-offer")) return;
  const t = document.createElement("div"); t.className = "tour-offer";
  t.innerHTML = `<b>New here?</b><span>Take a 1-minute tour of how a run works.</span><div><button type="button" class="btn btn-primary btn-sm" data-o="go">Start tour</button><button type="button" class="btn btn-ghost btn-sm" data-o="no">Not now</button></div>`;
  t.onclick = (e) => { const b = e.target.closest("[data-o]"); if (!b) return; store.set("homunculus_tour_offered", "1"); t.remove(); if (b.dataset.o === "go") startTour(kind); };
  setTimeout(() => document.body.appendChild(t), 1800);
}
