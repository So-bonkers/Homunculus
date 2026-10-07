// homunculus web app: home (hero + launcher + runs) and live run pages. Talks to homunculus/server.py (/api/*).
import { LIBRARY } from "/static/prompt_library.js";
import { tipsHTML, startTour, stopTour, offerTour } from "/static/tour.js";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const app = $("#app");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const dur = (s) => { s = Math.max(0, Math.round(s || 0)); const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}` : `${m}:${String(x).padStart(2, "0")}`; };
const api = async (p, opt) => { const r = await fetch(p, { cache: "no-store", ...opt }); if (!r.ok) throw Object.assign(new Error(r.statusText), { status: r.status }); return r.json(); };
const STATUS = { running: "Running", waiting: "Needs you", finished: "Finished", failed: "Failed", stopped: "Stopped" };
const pill = (s) => `<span class="pill ${s}"><i></i>${STATUS[s] || s}</span>`;
const ICON = {
  upload: `<svg viewBox="0 0 24 24" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></svg>`,
  cube: `<svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M12 22V12M3 7l9 5 9-5"/></svg>`,
  zoom: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>`,
};

ICON.fork = `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="5" r="2.2"/><circle cx="18" cy="5" r="2.2"/><circle cx="12" cy="19" r="2.2"/><path d="M6 7.2v1.3a4 4 0 0 0 4 4h4a4 4 0 0 0 4-4V7.2M12 12.5v4.3"/></svg>`;
const LOOKS = [["choose", "All · I pick"], ["asis", "As is"], ["stylized", "3D film"], ["game", "Game"], ["anime3d", "Anime 3D"], ["clay", "Clay"], ["chibi", "Chibi"]];
const LOOK_HINT = { choose: "First redraw: one image per look (As is + 5 styles). You pick the look and the image; the rest of the run uses it.", asis: "Keeps the picture's own style.", stylized: "Pixar/Disney-like 3D animated film character.", game: "Realistic game character, clean Unreal-style render.",
  anime3d: "Cel-shaded anime 3D (Genshin-like).", clay: "Matte claymation / vinyl toy figure.", chibi: "Big head, short limbs. Risky for the auto-rigger." };
const RIGGERS = [["mia", "Make-It-Animatable"], ["mia_normal", "MIA · normal weights"]];
const RIGGER_HINT = { mia: "Default skin weights: a good all-round rig (52 Mixamo bones with fingers).",
  mia_normal: "Binds the skin using the surface normals; try it if the default tears at thick armour, cloth or the shoulders." };
const FORKABLE = ["upscale", "plan", "edit", "upscale_edit", "mesh", "color", "rig", "animate", "texture", "report"];
const FORK_OF = { ingest: null, upscale: "upscale", plan: "plan", edit: "edit", pick: "edit", upscale_edit: "upscale_edit", mesh: "mesh", mesh_check: "mesh",
  color: "color", rig: "rig", rig_check: "rig", animate: "animate", texture: "texture", report: "report" };
const FORK_LABEL = { upscale: "Upscale", plan: "Plan", edit: "Redraw", upscale_edit: "Prepare", mesh: "3D shape", color: "Colour", rig: "Auto-rig", animate: "Animate", texture: "Texture", report: "Report" };
const LABEL_OF = (k) => FORK_LABEL[k] || k;
const FORK_HINT = { upscale: "Everything is redone from the upscaled input.", plan: "The planner looks at the picture again and writes a new redraw prompt.",
  edit: "New redraws. Your instructions go straight into the redraw prompt.", upscale_edit: "Keeps the chosen redraw, prepares it again for 3D.",
  mesh: "Keeps the redraw; new 3D shapes. Instructions steer the judges.", color: "Keeps the 3D model; redoes the quick colours, then rigs, animates and textures.",
  rig: "Keeps the coloured model; rigs it again (pick another rigger in the dialog).", animate: "Keeps the rig; generates the animation clips again from the prompts you give.",
  texture: "Keeps the rig and the clips; redoes the final texture and puts it on all of them.", report: "Only rebuilds the report and downloads." };

const fmtBytes = (n) => (n >= 1e9 ? (n / 1e9).toFixed(1) + " GB" : n >= 1e6 ? Math.round(n / 1e6) + " MB" : Math.max(1, Math.round(n / 1e3)) + " KB");
async function openDelete(name, onDone) {
  let P; try { P = await api("/api/purge/" + encodeURIComponent(name)); } catch { return toast("Could not load that run", true); }
  const box = document.createElement("div"); box.className = "sheet-bg";
  box.innerHTML = `<div class="sheet" role="dialog" aria-modal="true" style="width:min(520px,100%)">
    <div class="sh-head"><div><div class="eb">Delete</div><h2>Delete ${esc(name)}?</h2></div><button class="x" data-x>✕</button></div>
    <p class="hint" style="margin:0">This permanently removes the run and everything made for it. It cannot be undone.</p>
    <dl class="kv">${P.items.map((i) => `<dt>${esc(i.label)}</dt><dd>${fmtBytes(i.bytes)}</dd>`).join("")}<dt><b>Total</b></dt><dd><b>${fmtBytes(P.total)}</b></dd></dl>
    ${P.busy.length ? `<div class="alertbar"><span>Still running: ${esc(P.busy.join(", "))}. Stop it first.</span></div>` : ""}
    <div class="sh-foot"><span class="hint" id="dmsg" style="margin:0"></span><button class="btn btn-ghost" data-x>Cancel</button><button class="btn btn-danger" id="dgo" ${P.busy.length ? "disabled" : ""}>Delete permanently</button></div></div>`;
  document.body.appendChild(box); document.body.style.overflow = "hidden";
  const close = () => { box.remove(); document.body.style.overflow = ""; removeEventListener("keydown", onKey); }; const onKey = (e) => e.key === "Escape" && close(); addEventListener("keydown", onKey);
  box.addEventListener("click", (e) => { if (e.target === box || e.target.closest("[data-x]")) close(); });
  $("#dgo", box).onclick = async () => { $("#dgo", box).disabled = true; $("#dmsg", box).textContent = "Deleting…";
    try { const r = await fetch("/api/delete", { method: "POST", body: JSON.stringify({ run: name }) }); const j = await r.json();
      if (!r.ok) { $("#dmsg", box).textContent = j.error || "Could not delete."; $("#dgo", box).disabled = false; return; }
      close(); toast(`Deleted ${name} · freed ${fmtBytes(j.freed)}`); onDone && onDone(); } catch { $("#dmsg", box).textContent = "Could not reach the server."; $("#dgo", box).disabled = false; } };
}

async function openFork(d, stage, preset = {}) {
  let runs = []; try { runs = await api("/api/runs"); } catch {}
  const names = new Set(runs.map((r) => r.name)); let n = 1; while (names.has(`${d.name}_f${n}`)) n++;
  const firstOpen = d.stages.find((s) => s.status !== "done");
  const F = { stage: FORK_OF[stage] || FORK_OF[firstOpen?.key] || "edit", rigger: d.options.rigger || "mia", mode: "new", look: preset.look || d.options.look || "asis", face: d.options.face || "auto", faceRedraw: d.options.face_redraw !== false, outfit: d.options.outfit, review: d.options.review, zip: d.zip_on };
  const box = document.createElement("div"); box.className = "sheet-bg";
  box.innerHTML = `<div class="sheet" role="dialog" aria-modal="true">
    <div class="sh-head"><div><div class="eb">${ICON.fork} Fork</div><h2>Restart ${esc(d.name)} from a stage</h2></div><button class="x" data-x>✕</button></div>
    <div class="flabel">Start from</div><div class="stages">${FORKABLE.map((k, i) => { const st = d.stages.find((s) => s.key === k);
      return `<button type="button" data-st="${k}" class="${k === F.stage ? "on" : ""} ${st?.status === "done" ? "done" : ""}"><b>${i + 2}</b>${FORK_LABEL[k]}</button>`; }).join("")}</div>
    <div class="hint" id="fhint"></div>
    <div class="row2" style="margin-top:10px"><div class="field"><span class="flabel">Where</span>${seg("fmode", [["new", "New run"], ["same", "Restart this one"]], "new")}</div>
      <div class="field"><label class="flabel" for="fname">Name</label><input class="input" id="fname" value="${esc(`${d.name}_f${n}`)}" maxlength="40" spellcheck="false"></div></div>
    <div class="field"><label class="flabel" for="fnotes">Instructions</label><textarea class="notes" id="fnotes" placeholder="e.g. keep the hands open with all five fingers apart; make the boots shorter"></textarea>
      <div class="hint">Added to the redraw prompt and shown to every judge from this stage on.</div></div>
    <div class="field"><span class="flabel">Look</span>${seg("flook", LOOKS, F.look)}<div class="hint" id="flookhint"></div></div>
    <div class="row2"><div class="field"><span class="flabel">Outfit</span>${seg("foutfit", [["keep", "Keep"], ["shirtless", "Shirtless"], ["nude", "Nude"]], F.outfit)}</div>
      <div class="field"><span class="flabel">Your review</span>${seg("freview", [["override", "Override"], ["manual", "Manual"], ["off", "Off"]], F.review)}</div></div>
    <div class="row2"><div class="field"><span class="flabel">Face</span>${seg("fface", [["auto", "Auto"], ["off", "No face (helmet / mask)"], ["on", "Always"]], F.face)}</div>
      <div class="switch" id="ffrf"><div><b>Face close-up redraw</b></div><button type="button" class="tg ${F.faceRedraw ? "on" : ""}" id="ffr"></button></div></div>
    <div class="field"><span class="flabel">Rigger</span>${seg("frigger", RIGGERS, d.options.rigger || "mia")}</div>
    <div class="field"><label class="flabel" for="fanim">Animation prompts <small style="text-transform:none;letter-spacing:0;font-weight:500">(one per line)</small></label>
      <textarea class="notes" id="fanim" rows="2" placeholder="walks forward">${esc((d.options.anim_prompts || []).join("\n"))}</textarea><div id="fpresets" class="presetbox"></div></div>
    <div class="row2"><div class="field" id="fgracef"><span class="flabel">Review window</span><div class="range"><input type="range" id="fgrace" min="15" max="300" step="15" value="${esc(d.options.grace || 60)}"><output id="fgraceo">${esc(d.options.grace || 60)} s</output></div></div>
      <div class="switch"><div><b>Mixamo zip</b></div><button type="button" class="tg ${F.zip ? "on" : ""}" id="fzip"></button></div></div>
    <div class="sh-foot"><span class="hint" id="fmsg" style="margin:0"></span><button class="btn btn-ghost" data-x>Cancel</button><button class="btn btn-glow" id="fgo">${ICON.fork} Fork &amp; start</button></div></div>`;
  document.body.appendChild(box); document.body.style.overflow = "hidden"; presetPicker($("#fanim", box), $("#fpresets", box));
  const close = () => { disposePresetViewers(); box.remove(); document.body.style.overflow = ""; removeEventListener("keydown", onKey); };
  const onKey = (e) => e.key === "Escape" && close(); addEventListener("keydown", onKey);
  box.addEventListener("click", (e) => { if (e.target === box || e.target.closest("[data-x]")) close(); });
  const hint = () => { lookHint && lookHint(); $("#fhint", box).textContent = FORK_HINT[F.stage] + (F.mode === "same" ? " This run's later results are replaced." : "");
    $("#fgracef", box).style.visibility = F.review === "override" ? "" : "hidden"; };
  $(".stages", box).onclick = (e) => { const b = e.target.closest("[data-st]"); if (!b) return; F.stage = b.dataset.st; $$(".stages button", box).forEach((x) => x.classList.toggle("on", x === b)); hint(); };
  initSeg($('[data-seg="fmode"]', box), (v) => { F.mode = v; $("#fname", box).disabled = v === "same"; hint(); });
  initSeg($('[data-seg="foutfit"]', box), (v) => (F.outfit = v));
  initSeg($('[data-seg="frigger"]', box), (v) => (F.rigger = v));
  initSeg($('[data-seg="fface"]', box), (v) => { F.face = v; $("#ffrf", box).style.visibility = v === "off" ? "hidden" : ""; });
  $("#ffr", box).onclick = (e) => { F.faceRedraw = !F.faceRedraw; e.currentTarget.classList.toggle("on", F.faceRedraw); };
  $("#ffrf", box).style.visibility = F.face === "off" ? "hidden" : "";
  const lookHint = () => ($("#flookhint", box).textContent = LOOK_HINT[F.look] + (F.look !== (d.options.look || "asis") && FORKABLE.indexOf(F.stage) > FORKABLE.indexOf("edit") ? " A new look only shows if you restart from Redraw or earlier." : ""));
  initSeg($('[data-seg="flook"]', box), (v) => { F.look = v; lookHint(); });
  initSeg($('[data-seg="freview"]', box), (v) => { F.review = v; hint(); });
  $("#fgrace", box).oninput = (e) => ($("#fgraceo", box).textContent = e.target.value + " s");
  $("#fzip", box).onclick = (e) => { F.zip = !F.zip; e.currentTarget.classList.toggle("on", F.zip); };
  hint(); setTimeout(() => $("#fnotes", box).focus(), 50);
  $("#fgo", box).onclick = async () => {
    const target = F.mode === "same" ? d.name : $("#fname", box).value.trim(), msg = $("#fmsg", box);
    if (!/^[A-Za-z0-9_-]{1,40}$/.test(target)) { msg.textContent = "Name: letters, digits, - and _ only."; return; }
    if (F.mode === "new" && names.has(target)) { msg.textContent = "That name is taken."; return; }
    $("#fgo", box).disabled = true; msg.textContent = F.mode === "new" ? "Copying the finished stages…" : "Restarting…";
    try {
      const r = await fetch("/api/fork", { method: "POST", body: JSON.stringify({ run: d.name, name: target, stage: F.stage, notes: $("#fnotes", box).value,
        look: F.look, rigger: F.rigger, anim: $("#fanim", box).value.trim(), anim_reps: d.options.anim_reps || 2, outfit: F.outfit, face: F.face, face_redraw: F.faceRedraw ? "1" : "0", review: F.review, grace: $("#fgrace", box).value, zip: F.zip }) });
      const j = await r.json();
      if (!r.ok) { msg.textContent = j.error || "Could not fork."; $("#fgo", box).disabled = false; return; }
      close(); toast(F.mode === "new" ? `Forked into ${target}` : `Restarted ${target} from ${LABEL_OF(F.stage)}`);
      if (location.hash === "#/run/" + encodeURIComponent(target)) route(); else location.hash = "#/run/" + encodeURIComponent(target);
    } catch { msg.textContent = "Could not reach the homunculus server."; $("#fgo", box).disabled = false; }
  };
}

let page = { cleanup: [] };
const onCleanup = (f) => page.cleanup.push(f);
const every = (ms, f) => { const id = setInterval(f, ms); onCleanup(() => clearInterval(id)); };

function toast(msg, bad = false) {
  const t = $("#toast"); t.textContent = msg; t.className = "toast" + (bad ? " bad" : ""); t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => (t.hidden = true), 3200);
}

/* ---------------- preset prompt library ---------------- */
const presetViewers = new Set();
function disposePresetViewers() { presetViewers.forEach((v) => { try { v.dispose(); } catch {} }); presetViewers.clear(); }
async function presetManifest() { try { const r = await fetch("/static/presets/manifest.json?t=" + Date.now(), { cache: "no-store" }); return r.ok ? await r.json() : null; } catch { return null; } }

function presetPicker(ta, host) {
  if (!ta || !host) return;
  let cat = 0, q = "", mf = null, viewer = null, current = null, take = 0, who = (() => { try { return localStorage.getItem("presetModel") || "male"; } catch { return "male"; } })();
  const total = LIBRARY.reduce((n, c) => n + c.prompts.length, 0);
  const lines = () => ta.value.split("\n").map((x) => x.trim()).filter(Boolean);
  const mdl = () => mf?.models?.[who] || { clips: {} };
  const clipsOf = (p) => (mdl().clips?.[p] || []);
  const anyClips = (p) => Object.values(mf?.models || {}).some((m) => (m.clips?.[p] || []).length);
  host.innerHTML = `<button type="button" class="preset-toggle"><span>✨ Preset library</span><small>${total} prompts in ${LIBRARY.length} categories</small><i>▾</i></button>
    <div class="presets" hidden>
      <div class="ppreview" hidden><div class="pvhost"><div class="vload"><div style="text-align:center">Loading preview<div class="p"><i></i></div></div></div></div>
        <div class="pvinfo"><b class="pvtitle"></b><div class="pvwho"></div><div class="pvtakes"></div><div class="pvbtns"><button type="button" class="btn btn-primary btn-sm" data-act="pvadd">Add to my prompts</button>
          <button type="button" class="btn btn-ghost btn-sm" data-act="pvclose">Close preview</button></div>
          <small class="pvcredit"></small></div></div>
      <div class="ptop"><input class="input psearch" placeholder="Search presets: dance, sword, jump…" autocomplete="off" spellcheck="false">
      <button type="button" class="btn btn-ghost btn-sm" data-act="surprise" title="Add three random prompts">🎲 Surprise me</button></div>
      <div class="pcats"></div><div class="pchips"></div><div class="pfoot"></div></div>`;
  const panel = $(".presets", host), tg = $(".preset-toggle", host), pv = $(".ppreview", host);
  const draw = () => {
    const cur = new Set(lines().map((l) => l.toLowerCase()));
    const list = q ? LIBRARY.flatMap((c) => c.prompts.filter((p) => p.toLowerCase().includes(q))) : LIBRARY[cat].prompts;
    $(".pcats", host).innerHTML = q ? `<span class="pq">${list.length} match${list.length === 1 ? "" : "es"} for “${esc(q)}”</span>`
      : LIBRARY.map((c, i) => { const n = c.prompts.filter((p) => cur.has(p.toLowerCase())).length;
          return `<button type="button" class="pcat ${i === cat ? "on" : ""}" data-i="${i}">${c.icon} ${esc(c.cat)}${n ? `<b>${n}</b>` : ""}</button>`; }).join("");
    $(".pchips", host).innerHTML = list.length ? list.map((p) => `<div class="pchip ${cur.has(p.toLowerCase()) ? "on" : ""} ${current === p ? "pv-on" : ""}" role="button" tabindex="0" data-p="${esc(p)}"><span>${esc(p)}</span>${anyClips(p) ? `<i class="pvbtn" data-pv="${esc(p)}" title="Preview this motion">▶</i>` : ""}</div>`).join("")
      : `<div class="empty" style="padding:16px;grid-column:1/-1">No preset matches. Type your own prompt in the box above.</div>`;
    const have = mf ? Object.keys(mdl().clips || {}).length : 0;
    $(".pfoot", host).innerHTML = `<span>${cur.size} selected${mf ? ` · ▶ previews for ${have} of ${total}${mf.status && mf.status !== "done" ? " (still being generated)" : ""}` : ""}</span>${cur.size ? `<button type="button" class="btn-link" data-act="clear">Clear all</button>` : ""}`;
  };
  const write = (arr) => { ta.value = arr.join("\n"); ta.dispatchEvent(new Event("input", { bubbles: true })); draw(); updatePv(); };
  const updatePv = () => { if (!current) return; const has = lines().some((l) => l.toLowerCase() === current.toLowerCase()); const b = $("[data-act=pvadd]", host); b.textContent = has ? "Remove from my prompts" : "Add to my prompts"; b.classList.toggle("btn-ghost", has); b.classList.toggle("btn-primary", !has); };
  const showTake = async () => {
    const ms = Object.entries(mf?.models || {}).filter(([, m]) => (m.clips?.[current] || []).length);
    if (ms.length && !ms.some(([k]) => k === who)) who = ms[0][0];
    $(".pvwho", host).innerHTML = Object.entries(mf?.models || {}).map(([k, m]) => `<button type="button" class="pcat ${k === who ? "on" : ""}" data-who="${k}" ${(m.clips?.[current] || []).length ? "" : "disabled title='Not generated yet'"}>${esc(m.label || k)}</button>`).join("");
    const m = mdl(), cr = $(".pvcredit", host);
    cr.innerHTML = m.title ? `“${esc(m.title)}” (<a href="${esc(m.url)}" target="_blank" rel="noopener">${esc(m.url)}</a>) by ${esc(m.author)} is licensed under <a href="${esc(m.license_url)}" target="_blank" rel="noopener">${esc(m.license)}</a>. Animated locally by UniMate.` : "";
    const files = clipsOf(current); if (!files.length) return;
    $(".pvtakes", host).innerHTML = files.map((f, i) => `<button type="button" class="pcat ${i === take ? "on" : ""}" data-take="${i}">Take ${i + 1}</button>`).join("");
    const load = $(".pvhost .vload", host); load.hidden = false;
    try { await viewer.load("/static/presets/" + files[take]); load.hidden = true; viewer.set({ bones: false }); } catch { load.textContent = "Could not load this preview."; }
  };
  const preview = async (p) => {
    current = p; take = 0; pv.hidden = false; $(".pvtitle", host).textContent = "An object " + p + "."; updatePv(); draw();
    if (!viewer) { const { createViewer } = await import("/static/viewer.js"); viewer = createViewer($(".pvhost", host), {}); presetViewers.add(viewer); }
    await showTake(); pv.scrollIntoView({ block: "nearest", behavior: "smooth" });
  };
  tg.onclick = async () => { if (ta.disabled) return; panel.hidden = !panel.hidden; host.classList.toggle("open", !panel.hidden);
    if (!panel.hidden) { mf = await presetManifest(); draw(); } else if (viewer) { presetViewers.delete(viewer); viewer.dispose(); viewer = null; pv.hidden = true; current = null; } };
  $(".psearch", host).oninput = (e) => { q = e.target.value.trim().toLowerCase(); draw(); };
  panel.onclick = (e) => {
    const c = e.target.closest(".pcat[data-i]"); if (c) { cat = +c.dataset.i; return draw(); }
    const w = e.target.closest("[data-who]"); if (w && !w.disabled) { who = w.dataset.who; take = 0; try { localStorage.setItem("presetModel", who); } catch {} draw(); return showTake(); }
    const t = e.target.closest("[data-take]"); if (t) { take = +t.dataset.take; return showTake(); }
    const v = e.target.closest("[data-pv]"); if (v) { e.stopPropagation(); return preview(v.dataset.pv); }
    const p = e.target.closest(".pchip");
    if (p) { const cur = lines(), i = cur.findIndex((l) => l.toLowerCase() === p.dataset.p.toLowerCase()); i >= 0 ? cur.splice(i, 1) : cur.push(p.dataset.p); return write(cur); }
    const a = e.target.closest("[data-act]"); if (!a) return;
    if (a.dataset.act === "clear") write([]);
    if (a.dataset.act === "pvclose") { pv.hidden = true; current = null; draw(); }
    if (a.dataset.act === "pvadd") { const cur = lines(), i = cur.findIndex((l) => l.toLowerCase() === current.toLowerCase()); i >= 0 ? cur.splice(i, 1) : cur.push(current); write(cur); }
    if (a.dataset.act === "surprise") { const all = LIBRARY.flatMap((c2) => c2.prompts), cur = lines(), have = new Set(cur.map((l) => l.toLowerCase())); let n = 0;
      while (n < 3 && all.length) { const p2 = all[Math.floor(Math.random() * all.length)]; if (!have.has(p2.toLowerCase())) { cur.push(p2); have.add(p2.toLowerCase()); n++; } } write(cur); }
  };
  ta.addEventListener("input", () => { if (!panel.hidden) { draw(); updatePv(); } });
}

/* ---------------- lightbox ---------------- */
const lb = { list: [], i: 0 };
function openLB(list, i) { lb.list = list; lb.i = i; showLB(); $("#lightbox").hidden = false; }
function showLB() { const it = lb.list[lb.i]; if (!it) return; $("#lightbox img").src = it.url; $("#lightbox figcaption").textContent = it.title || "";
  $(".lb-prev").style.visibility = $(".lb-next").style.visibility = lb.list.length > 1 ? "visible" : "hidden"; }
$("#lightbox").addEventListener("click", (e) => {
  if (e.target.closest(".lb-prev")) { lb.i = (lb.i - 1 + lb.list.length) % lb.list.length; showLB(); }
  else if (e.target.closest(".lb-next")) { lb.i = (lb.i + 1) % lb.list.length; showLB(); }
  else if (!e.target.closest("img")) $("#lightbox").hidden = true;
});
addEventListener("keydown", (e) => {
  if ($("#lightbox").hidden) return;
  if (e.key === "Escape") $("#lightbox").hidden = true;
  if (e.key === "ArrowLeft") { lb.i = (lb.i - 1 + lb.list.length) % lb.list.length; showLB(); }
  if (e.key === "ArrowRight") { lb.i = (lb.i + 1) % lb.list.length; showLB(); }
});

/* ---------------- reveal on scroll ---------------- */
const revealIO = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && (e.target.classList.add("in"), revealIO.unobserve(e.target))), { threshold: 0.08 });
const reveal = (root = app) => $$(".reveal:not(.in)", root).forEach((el) => revealIO.observe(el));

/* ---------------- segmented control ---------------- */
function seg(name, opts, val) {
  return `<div class="seg" data-seg="${name}">${opts.map(([v, l]) => `<button type="button" data-v="${esc(v)}" class="${v === val ? "on" : ""}">${esc(l)}</button>`).join("")}<span class="thumb"></span></div>`;
}
function initSeg(el, onChange) {
  const thumb = $(".thumb", el);
  const place = () => { const b = $("button.on", el) || $("button", el); thumb.style.left = b.offsetLeft + "px"; thumb.style.width = b.offsetWidth + "px"; };
  el.addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return;
    $$("button", el).forEach((x) => x.classList.toggle("on", x === b)); place(); onChange && onChange(b.dataset.v); });
  new ResizeObserver(place).observe(el); requestAnimationFrame(place);
}

/* ---------------- live chip in the nav ---------------- */
async function pollLive() {
  try { const l = await api("/api/live"); const c = $("#livechip"); c.hidden = !l.length; $("span", c).textContent = l.length === 1 ? `${l[0]} running` : `${l.length} runs active`; } catch {}
}
pollLive(); setInterval(pollLive, 5000);

// a tab that stays open for hours must not keep running old code: reload when the app's files change (unless you're mid-edit)
let appVersion = null;
async function checkVersion() {
  try {
    const { v } = await api("/api/version");
    if (appVersion === null) { appVersion = v; return; }
    if (v === appVersion) return;
    const busy = $(".sheet-bg") || ["TEXTAREA", "INPUT", "SELECT"].includes(document.activeElement?.tagName) || $("#notes")?.value;
    if (!busy) location.reload(); else toast("homunculus was updated; it reloads when you're done here");
  } catch {}
}
checkVersion(); setInterval(checkVersion, 10000);

async function stopRun(name) {
  if (!confirm(`Stop “${name}”?\nIt can be resumed later by starting the same name again.`)) return;
  try { await api("/api/stop", { method: "POST", body: JSON.stringify({ run: name }) }); toast(`Stopping ${name}…`); } catch { toast("Could not stop the run", true); }
}

/* ======================================================================= HOME */
async function home(scrollTo) {
  app.innerHTML = `
  <section class="hero">
    <div class="reveal">
      <span class="eyebrow"><i></i>Fully local · one 24 GB GPU</span>
      <h1><span>Picture in.</span><span class="grad">Character out.</span></h1>
      <p class="lead">One image becomes a textured, animation-ready 3D character with a 52-bone skeleton. Redrawn, sculpted, rigged and judged by models running on this machine.</p>
      <div class="ctas"><a class="btn btn-glow" href="#/new">Start a run</a><a class="btn btn-ghost" href="#/runs">Browse runs</a></div>
      <div class="ticker"><span>Qwen-Image 2.1</span><span>Pixal3D</span><span>Make-It-Animatable</span><span>Qwen3.8 · Gemma 4 · Qwen3.6 judges</span><span>Blender</span></div>
      <div class="stats"><div class="stat"><b>14</b><span>stages</span></div><div class="stat"><b>3</b><span>AI judges</span></div><div class="stat"><b>52</b><span>bones</span></div><div class="stat"><b id="st-runs">–</b><span>runs</span></div></div>
    </div>
    <div class="stage3d reveal" id="hero3d"><div class="floor"></div><div class="loader3d"><div class="orb"></div><small>loading model</small></div><div class="cap" id="herocap"></div></div>
  </section>

  <section class="section" id="new"><div class="wrap">
    <div class="reveal"><span class="eyebrow">New run</span>
      <h2 class="h-sec">Drop an image.<br><span class="grad">Watch it come alive.</span></h2>
      <p class="lead">Choose how it should be built. A run takes around 50 minutes and asks for your call at every judge decision.</p></div>
    <div class="launcher reveal">
      <label class="drop" id="drop"><input type="file" id="file" accept="image/png,image/jpeg,image/webp,.stl,.obj,.ply,.glb,.gltf,.fbx" hidden>
        <div class="ph" id="ph"><div class="ic">${ICON.upload}</div><b>Drop a picture or a 3D model</b><span>JPG, PNG, WebP · or STL, OBJ, PLY, GLB, FBX (it gets painted and textured)</span></div>
      </label>
      <form class="form" id="form" autocomplete="off" onsubmit="return false">
        <div class="field"><label for="name">Run name</label><input class="input" id="name" placeholder="e.g. hero_v1" maxlength="40" spellcheck="false"><div class="hint" id="namehint"></div></div>
        <div class="switch"><div><b>Use my picture as is</b><small>Skip the redraw: for clean full-body references (T/A-pose, open hands, plain background). The texture then comes from your picture itself (upscaled, not redrawn).</small></div><button type="button" class="tg" id="direct"></button></div>
        <div class="field" id="lookf"><span class="flabel">Look</span>${seg("look", LOOKS, "choose")}<div class="hint" id="lookhint"></div></div>
        <div class="field"><span class="flabel">Outfit</span>${seg("outfit", [["keep", "Keep"], ["shirtless", "Shirtless"], ["nude", "Nude"]], "keep")}<div class="hint" id="outfithint"></div></div>
        <div class="field" id="facef"><span class="flabel">Face</span>${seg("face", [["auto", "Auto"], ["off", "No face (helmet / mask)"], ["on", "Always"]], "auto")}<div class="hint" id="facehint"></div></div>
        <div class="switch" id="fredrawf"><div><b>Redraw the face as a close-up</b><small>A sharper face for the 3D shape and texture. Turn it off to use the full-body redraw as it is.</small></div><button type="button" class="tg on" id="fredraw" aria-pressed="true"></button></div>
        <div class="field"><span class="flabel">Your review</span>${seg("review", [["override", "Override"], ["manual", "Manual"], ["off", "Off"]], "override")}<div class="hint" id="reviewhint"></div></div>
        <div class="field" id="gracef"><span class="flabel">Review window</span><div class="range"><input type="range" id="grace" min="15" max="300" step="15" value="60"><output id="graceo">60 s</output></div></div>
        <div class="switch"><div><b>Mixamo zip</b><small>OBJ + texture to upload to mixamo.com for animations</small></div><button type="button" class="tg on" id="zip" aria-pressed="true"></button></div>
        <div class="field"><span class="flabel">Rigger</span>${seg("rigger", RIGGERS, "mia")}<div class="hint" id="riggerhint"></div></div>
        <div class="field"><label class="flabel" for="anim">Animations <small style="text-transform:none;letter-spacing:0;font-weight:500">(optional · one prompt per line)</small></label>
          <textarea class="notes" id="anim" rows="3" placeholder="walks forward&#10;waves with the right hand&#10;jumps in place"></textarea>
          <div class="hint">Describe one motion per line (not the character). Made after the rig is built; add more any time on the run page.</div><div id="animpresets" class="presetbox"></div></div>
        <details class="adv"><summary>Advanced options</summary>
          <div class="row2">
            <div class="field"><span class="flabel">Image style</span><select class="input" id="style"><option value="">Auto-detect</option><option value="photo">Photo</option><option value="anime">Anime</option><option value="3d_render">3D render</option></select></div>
            <div class="field"><span class="flabel">Clips per prompt</span><select class="input" id="animreps"><option>1</option><option selected>2</option><option>3</option><option>4</option></select></div>
            <div class="field"><span class="flabel">Start from</span><select class="input" id="frm"><option value="">Beginning / resume</option>${["upscale", "plan", "edit", "upscale_edit", "mesh", "color", "rig", "animate", "texture", "report"].map((s) => `<option>${s}</option>`).join("")}</select></div>
          </div>
        </details>
        <div class="go"><button type="button" class="btn btn-glow" id="go">Start run</button><div class="bar" id="upbar" hidden><i></i></div><span class="hint" id="gomsg" style="margin:0"></span></div>
      </form>
    </div>
  </div></section>

  <section class="section" id="tips"><div class="wrap">
    <div class="reveal"><span class="eyebrow">Tips</span><h2 class="h-sec">Get better results.</h2></div>
    ${tipsHTML()}
  </div></section>

  <section class="section" id="runs"><div class="wrap">
    <div class="runs-head reveal"><div><span class="eyebrow">Library</span><h2 class="h-sec" style="margin-bottom:0">Runs</h2></div>
      ${seg("filter", [["all", "All"], ["active", "Active"], ["finished", "Finished"]], "all").replace('class="seg"', 'class="seg filters"')}</div>
    <div class="runs" id="runlist"></div>
  </div></section>
  <footer class="foot">homunculus · everything runs on this machine</footer>`;
  reveal(); offerTour("home");
  if (scrollTo) requestAnimationFrame(() => document.getElementById(scrollTo)?.scrollIntoView({ behavior: "instant", block: "start" }));

  // ---- launcher
  const F = { file: null, direct: false, look: "choose", rigger: "mia", face: "auto", faceRedraw: true, outfit: "keep", review: "override", zip: true };
  let known = [];
  const FACE_HINT = { auto: "The planner checks whether a full-face helmet or mask hides the face.", off: "Skip every face step (close-up redraw, reshape, face fit). Use it for helmets, masks and visors so no face gets carved into them.", on: "Always fit a face, even if the planner thinks it is hidden." };
  const HINT = { keep: "Redraws the outfit from the picture.", shirtless: "Bare torso and arms; avoids sleeve cuffs tearing at the wrists.", nude: "Unclothed, anatomy kept. Only for generated or fictional adult characters.",
    override: "The judges decide; you can overrule them within the review window.", manual: "You are the judge: one redraw, one 3D shape at a time; use it or try another. No AI judges, no time limit.", off: "Fully automatic, no questions asked." };
  initSeg($('[data-seg="look"]'), (v) => { F.look = v; setHints(); });
  const setHints = () => { $("#facehint").textContent = FACE_HINT[F.face]; $("#riggerhint").textContent = RIGGER_HINT[F.rigger]; $("#lookhint").textContent = LOOK_HINT[F.look]; $("#outfithint").textContent = HINT[F.outfit]; $("#reviewhint").textContent = HINT[F.review]; $("#gracef").style.display = F.review === "override" ? "" : "none"; };
  initSeg($('[data-seg="rigger"]'), (v) => { F.rigger = v; setHints(); });
  initSeg($('[data-seg="outfit"]'), (v) => { F.outfit = v; setHints(); });
  initSeg($('[data-seg="face"]'), (v) => { F.face = v; setHints(); $("#fredrawf").style.display = v === "off" ? "none" : ""; });
  $("#fredraw").onclick = (e) => { F.faceRedraw = !F.faceRedraw; e.currentTarget.classList.toggle("on", F.faceRedraw); e.currentTarget.setAttribute("aria-pressed", F.faceRedraw); };
  initSeg($('[data-seg="review"]'), (v) => { F.review = v; setHints(); });
  setHints(); presetPicker($("#anim"), $("#animpresets"));
  $("#grace").oninput = (e) => ($("#graceo").textContent = e.target.value + " s");
  $("#zip").onclick = (e) => { F.zip = !F.zip; e.currentTarget.classList.toggle("on", F.zip); };
  $("#direct").onclick = (e) => { F.direct = !F.direct; e.currentTarget.classList.toggle("on", F.direct);
    $("#lookf").style.display = F.direct ? "none" : ""; $('[data-seg="outfit"]').closest(".field").style.display = F.direct ? "none" : ""; };
  const nameHint = () => {
    const n = $("#name").value.trim(), h = $("#namehint");
    h.className = "hint";
    if (n && !/^[A-Za-z0-9_-]+$/.test(n)) { h.textContent = "Letters, digits, - and _ only."; h.className = "hint warn"; return; }
    const ex = known.find((r) => r.name === n);
    if (ex && ex.live) { h.textContent = "This run is active right now."; h.className = "hint warn"; }
    else if (ex) h.textContent = F.file ? "A run with this name exists; the new image replaces its input and the run resumes." : "Existing run: start without an image to resume it, or pick a stage under Advanced to redo from there.";
    else h.textContent = "";
  };
  $("#name").oninput = nameHint;
  const drop = $("#drop");
  const isMesh = (f) => /\.(stl|obj|ply|glb|gltf|fbx)$/i.test(f.name);
  const pick = (f) => {
    if (!f) return; F.file = f;
    $$("img.pv,.swap,.meshpv", drop).forEach((x) => x.remove());
    $("#ph").style.opacity = 0;
    drop.insertAdjacentHTML("beforeend", isMesh(f)
      ? `<div class="meshpv"><div class="ic">${ICON.cube}</div><b>${esc(f.name)}</b><span>${(f.size / 1048576).toFixed(1)} MB · 3D model: it will be prepared, painted and textured</span></div><span class="swap">click to change</span>`
      : `<img class="pv" src="${URL.createObjectURL(f)}" alt=""><span class="swap">${esc(f.name)} · click to change</span>`);
    $("#direct").closest(".switch").style.display = isMesh(f) ? "none" : "";
    $('[data-seg="outfit"]').closest(".field").style.display = isMesh(f) || F.direct ? "none" : "";
    if (!$("#name").value) $("#name").value = f.name.replace(/\.[^.]+$/, "").replace(/[^A-Za-z0-9_-]+/g, "_").slice(0, 40);
    nameHint();
  };
  $("#file").onchange = (e) => pick(e.target.files[0]);
  ["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => pick(e.dataTransfer.files[0]));
  $("#go").onclick = () => {
    const name = $("#name").value.trim(), msg = $("#gomsg");
    if (!name) { msg.textContent = "Give the run a name."; return $("#name").focus(); }
    if (!/^[A-Za-z0-9_-]{1,40}$/.test(name)) { msg.textContent = "Letters, digits, - and _ only."; return; }
    if (!F.file && !known.some((r) => r.name === name)) { msg.textContent = "Choose an image first."; return; }
    const q = new URLSearchParams({ name, fname: F.file ? F.file.name : "image.jpg", look: F.direct ? "asis" : F.look, direct: F.direct ? "1" : "0", rigger: F.rigger, anim: $("#anim").value.trim(), anim_reps: $("#animreps").value, outfit: F.outfit, face: F.face, face_redraw: F.faceRedraw ? "1" : "0", review: F.review, grace: $("#grace").value,
      style: $("#style").value, frm: $("#frm").value, zip: F.zip ? "1" : "0" });
    const x = new XMLHttpRequest(); x.open("POST", "/api/upload?" + q);
    $("#go").disabled = true; $("#upbar").hidden = !F.file; msg.textContent = F.file ? "" : "Starting…";
    x.upload.onprogress = (e) => { if (e.lengthComputable) $("#upbar i").style.width = (100 * e.loaded / e.total) + "%"; };
    x.onload = () => { let j = {}; try { j = JSON.parse(x.responseText); } catch {}
      if (x.status !== 200) { $("#go").disabled = false; $("#upbar").hidden = true; msg.textContent = j.error || "Could not start the run."; return; }
      toast(`Started ${name}`); location.hash = "#/run/" + encodeURIComponent(name); };
    x.onerror = () => { $("#go").disabled = false; msg.textContent = "Could not reach the homunculus server."; };
    x.send(F.file || new Blob([]));
  };

  // ---- runs grid
  let filter = "all", lastSig = "";
  initSeg($('[data-seg="filter"]'), (v) => { filter = v; lastSig = ""; drawRuns(); });
  const card = (r) => `<a class="rc" href="#/run/${encodeURIComponent(r.name)}">
      <div class="im">${r.thumb ? `<img src="${esc(r.thumb)}" loading="lazy" alt="">` : ""}</div>
      <div class="top">${pill(r.status)}${r.live ? `<button class="btn stop" data-stop="${esc(r.name)}">Stop</button>` : `<button class="btn stop" data-fork="${esc(r.name)}">${ICON.fork} Fork</button><button class="btn stop del" data-del="${esc(r.name)}" title="Delete this run and its files">Delete</button>`}</div>
      <div class="ov"><div class="nm">${esc(r.name)}</div><div class="sub">${esc(r.current ? (r.live ? "Now: " : "Stopped at ") + r.current : r.last || r.file)}</div>
      <div class="prog"><i style="width:${(100 * r.done) / r.total}%"></i></div></div></a>`;
  function drawRuns() {
    const list = known.filter((r) => filter === "all" || (filter === "active" ? r.live : r.status === "finished"));
    const sig = filter + JSON.stringify(list.map((r) => [r.name, r.status, r.done, r.current, r.thumb, r.last]));
    if (sig === lastSig) return; lastSig = sig;
    $("#runlist").innerHTML = list.length ? list.map(card).join("") : `<div class="empty">${filter === "all" ? "No runs yet. Drop an image above to start one." : "Nothing here."}</div>`;
  }
  $("#runlist").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-stop]"); if (b) { e.preventDefault(); return stopRun(b.dataset.stop); }
    const dl = e.target.closest("[data-del]"); if (dl) { e.preventDefault(); return openDelete(dl.dataset.del, loadRuns); }
    const f = e.target.closest("[data-fork]"); if (f) { e.preventDefault(); try { openFork(await api("/api/run/" + encodeURIComponent(f.dataset.fork)), null); } catch { toast("Could not load that run", true); } }
  });
  const loadRuns = async () => { try { known = await api("/api/runs"); $("#st-runs").textContent = known.length; drawRuns(); nameHint(); } catch {} };
  await loadRuns(); every(4000, loadRuns);

  // ---- hero model: the newest run that has a 3D model (finished first)
  const pickHero = known.find((r) => r.model && r.status === "finished") || known.find((r) => r.model);
  const host = $("#hero3d");
  if (!pickHero) { $(".loader3d small", host).textContent = "your first character will appear here"; return; }
  try {
    const { createViewer } = await import("/static/viewer.js");
    if (!document.body.contains(host)) return;
    const v = createViewer(host, { hero: true }); onCleanup(() => v.dispose());
    await v.load(pickHero.model);
    $(".loader3d", host)?.remove();
    $("#herocap").innerHTML = `<a href="#/run/${encodeURIComponent(pickHero.name)}">${esc(pickHero.name)}</a> · drag to turn`;
  } catch (e) { $(".loader3d small", host).textContent = "3D preview unavailable"; console.warn(e); }
}

/* ======================================================================= RUN */
// ReactFlow-style pipeline graph: two rows, snaking, with retry loops.
const NW = 180, NH = 68, GX = 64, RY = 160;
const ORDER = ["ingest", "upscale", "plan", "edit", "pick", "upscale_edit", "mesh", "mesh_check", "color", "rig", "rig_check", "animate", "texture", "report"];
const PER = 7;       // nodes per row: the second row runs right to left
const POS = Object.fromEntries(ORDER.map((s, i) => [s, i < PER ? { x: i * (NW + GX), y: 0 } : { x: (ORDER.length - 1 - i) * (NW + GX), y: RY }]));
const GATE_STAGE = { pick: "pick", mesh_check: "mesh_check", rig_check: "rig_check", orient: "plan" };
const NUM = Object.fromEntries(ORDER.map((s, i) => [s, i + 1]));

function edgePaths() {
  const E = [];
  for (let i = 0; i < ORDER.length - 1; i++) {
    const a = ORDER[i], b = ORDER[i + 1], A = POS[a], B = POS[b];
    let d;
    if (i < PER - 1) d = `M${A.x + NW},${A.y + NH / 2} C${A.x + NW + GX / 2},${A.y + NH / 2} ${B.x - GX / 2},${B.y + NH / 2} ${B.x},${B.y + NH / 2}`;
    else if (i === PER - 1) d = `M${A.x + NW / 2},${A.y + NH} C${A.x + NW / 2},${A.y + NH + 45} ${B.x + NW / 2},${B.y - 45} ${B.x + NW / 2},${B.y}`;
    else d = `M${A.x},${A.y + NH / 2} C${A.x - GX / 2},${A.y + NH / 2} ${B.x + NW + GX / 2},${B.y + NH / 2} ${B.x + NW},${B.y + NH / 2}`;
    E.push({ a, b, d });
  }
  const loop = (from, to, up) => { const A = POS[from], B = POS[to], y = up ? A.y : A.y + NH, dy = up ? -48 : 48;
    return { a: from, b: to, retry: true, d: `M${A.x + NW / 2},${y} C${A.x + NW / 2},${y + dy} ${B.x + NW / 2},${y + dy} ${B.x + NW / 2},${y}`,
      lx: (A.x + B.x + NW) / 2, ly: y + dy * 0.78 }; };
  E.push(loop("pick", "edit", true), loop("rig_check", "rig", false));
  const m = POS.mesh, mc = POS.mesh_check;      // vertical neighbours: the retry arc bulges out to the right
  E.push({ a: "mesh_check", b: "mesh", retry: true, d: `M${mc.x + NW},${mc.y + NH / 2} C${mc.x + NW + 70},${mc.y + NH / 2} ${m.x + NW + 70},${m.y + NH / 2} ${m.x + NW},${m.y + NH / 2}`, lx: m.x + NW + 40, ly: (m.y + mc.y + NH) / 2 + 4 });
  return E;
}
const HANDLES = (s) => s === "ingest" ? ["r"] : s === "mesh" ? ["l", "b"] : s === "mesh_check" ? ["t", "l"] : s === "report" ? ["r"] : ["l", "r"];

function buildFlow(el, onSelect) {
  const edges = edgePaths();
  el.innerHTML = `<div class="vp"><svg class="edges" width="1" height="1">${edges.map((e, i) => `<path class="edge${e.retry ? " retry" : ""}" data-e="${i}" d="${e.d}"/>`).join("")}
      ${edges.filter((e) => e.retry).map((e) => `<text class="elabel" x="${e.lx}" y="${e.ly}" text-anchor="middle">retry</text>`).join("")}</svg>
      ${ORDER.map((s) => `<div class="node" data-s="${s}" style="left:${POS[s].x}px;top:${POS[s].y}px">${HANDLES(s).map((h) => `<i class="h h${h}"></i>`).join("")}
        <div class="ic">${NUM[s]}</div><div class="tx"><div class="nl"></div><div class="nm"></div></div><span class="tm" hidden></span></div>`).join("")}</div>
    <div class="fctl"><button data-z="in" title="Zoom in">+</button><button data-z="out" title="Zoom out">−</button><button data-z="fit" title="Fit view">⤢</button></div>
    <div class="flegend"><span><i style="background:var(--ok)"></i>done</span><span><i style="background:var(--accent)"></i>running</span><span><i style="background:var(--warn)"></i>needs you</span><span>⌘/Ctrl + scroll to zoom · drag to pan</span></div>`;
  const vp = $(".vp", el); let t = { x: 0, y: 0, k: 1 };
  const apply = () => { vp.style.transform = `translate(${t.x}px,${t.y}px) scale(${t.k})`; el.style.backgroundSize = `${22 * t.k}px ${22 * t.k}px`; el.style.backgroundPosition = `${t.x}px ${t.y}px`; };
  const fit = () => { const W = el.clientWidth, H = el.clientHeight, gw = PER * NW + (PER - 1) * GX + 80, gh = RY + NH + 110;
    t.k = Math.min(1.15, (W - 150) / gw, (H - 40) / gh); t.x = (W - gw * t.k) / 2 + 20; t.y = (H - (RY + NH) * t.k) / 2 + 4 * t.k; apply(); };
  const zoomAt = (f, cx, cy) => { const k = Math.min(2.2, Math.max(0.35, t.k * f)); t.x = cx - (cx - t.x) * (k / t.k); t.y = cy - (cy - t.y) * (k / t.k); t.k = k; apply(); };
  el.addEventListener("wheel", (e) => { if (!(e.ctrlKey || e.metaKey)) return; e.preventDefault(); const r = el.getBoundingClientRect(); zoomAt(Math.exp(-e.deltaY * 0.0022), e.clientX - r.left, e.clientY - r.top); }, { passive: false });
  let drag = null;
  el.addEventListener("pointerdown", (e) => { if (e.target.closest(".fctl")) return; drag = { x: e.clientX, y: e.clientY, tx: t.x, ty: t.y, moved: false, node: e.target.closest(".node") }; el.setPointerCapture(e.pointerId); });
  el.addEventListener("pointermove", (e) => { if (!drag) return; const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true; if (drag.moved) { t.x = drag.tx + dx; t.y = drag.ty + dy; apply(); } });
  el.addEventListener("pointerup", () => { if (drag && !drag.moved && drag.node) onSelect(drag.node.dataset.s); drag = null; });
  $(".fctl", el).addEventListener("click", (e) => { const z = e.target.dataset.z; if (!z) return; const W = el.clientWidth / 2, H = el.clientHeight / 2;
    z === "fit" ? fit() : zoomAt(z === "in" ? 1.2 : 1 / 1.2, W, H); });
  new ResizeObserver(fit).observe(el); fit();
  return edges;
}

function updateFlow(el, edges, d, selected) {
  const st = Object.fromEntries(d.stages.map((s) => [s.key, { ...s }]));
  if (d.review && GATE_STAGE[d.review.gate]) { const g = GATE_STAGE[d.review.gate]; st[g].status = "waiting";
    const src = { pick: "edit", mesh_check: "mesh", rig_check: "rig" }[g]; if (src && st[src].status === "running") st[src].status = "done"; }
  for (const s of ORDER) {
    const n = $(`.node[data-s="${s}"]`, el), x = st[s];
    n.className = `node ${x.status}${selected === s ? " sel" : ""}`;
    $(".nl", n).textContent = x.label; $(".nm", n).textContent = x.status === "waiting" ? "waiting for your call" : x.model;
    $(".ic", n).textContent = x.status === "done" ? "✓" : x.status === "failed" ? "!" : x.status === "running" ? "" : x.status === "skipped" ? "–" : NUM[s];
    const tg = $(".tm", n); tg.hidden = !x.seconds; if (x.seconds) tg.textContent = dur(x.seconds);
  }
  const ok = (s) => ["done", "skipped"].includes(st[s].status);
  $$("path.edge", el).forEach((p) => { const e = edges[+p.dataset.e]; if (e.retry) return;
    p.setAttribute("class", "edge" + (ok(e.a) && ok(e.b) ? " done" : ok(e.a) && ["running", "waiting"].includes(st[e.b].status) ? " active" : "")); });
}

async function runPage(name) {
  app.innerHTML = `<div class="wrap">
    <a class="back" href="#/runs">‹ All runs</a>
    <header class="rhead"><img class="av" id="av" alt=""><div><h1>${esc(name)}</h1><div class="meta" id="meta"></div></div><div class="act" id="act"></div></header>
    <div id="alert"></div>
    <div class="flow" id="flow"></div>
    <div id="review"></div>
    <div class="rgrid"><div>${seg("tab", [["activity", "Activity"], ["looks", "Looks"], ["animate", "Animate"], ["model", "3D model"], ["repair", "Repair"], ["retex", "Retexture"], ["log", "Log"]], "activity").replace('class="seg"', 'class="seg tabs"')}<div id="tab"></div></div><aside class="side" id="side"></aside></div>
  </div>`;
  let d = null, sel = null, tab = "activity", sig = {}, offset = 0, viewer = null, sentFor = null;
  const edges = buildFlow($("#flow"), (s) => { sel = sel === s ? null : s; sig.tab = sig.side = ""; render(); });
  initSeg($('[data-seg="tab"]'), (v) => { tab = v; sig.tab = ""; render(); });
  onCleanup(() => viewer && viewer.dispose());

  function header() {
    $("#av").src = d.input || d.thumb || ""; $("#av").style.visibility = d.input ? "" : "hidden";
    const o = d.options;
    $("#meta").innerHTML = `${pill(d.status)}${d.repair ? `<span class="pill running"><i></i>Repairing · ${esc(({ queued: "waiting for the GPU", regions: "redrawing", merge: "joining", bake: "baking" })[d.repair.step] || "working")}</span>` : ""}<span>${esc(d.file)}</span><span class="dotsep">•</span><span>${d.mode === "mesh" ? "3D model input" : d.options.direct ? "picture as is" : esc(o.outfit)}</span><span class="dotsep">•</span><span>review ${esc(o.review)}</span><span class="dotsep">•</span><span class="clock" id="clock"></span>${d.forked_from ? `<span class="dotsep">•</span><span>forked from <a class="btn-link" href="#/run/${encodeURIComponent(d.forked_from.run)}">${esc(d.forked_from.run)}</a> at ${esc(d.forked_from.stage)}</span>` : ""}`;
    $("#act").innerHTML = (d.live ? `<button class="btn btn-danger btn-sm" id="stop">Stop run</button>` : `<button class="btn btn-ghost btn-sm" id="forkbtn" title="Restart from any stage with new instructions or options">${ICON.fork} Fork</button>`)
      + (d.zip ? `<a class="btn btn-ghost btn-sm" href="${d.zip}" download>Mixamo zip</a>` : "")
      + (d.live ? "" : `<button class="btn btn-ghost btn-sm" id="delbtn" title="Delete this run and all its files">Delete</button>`)
      + (d.models.length ? `<button class="btn btn-primary btn-sm" id="view3d">View in 3D</button>` : "");
    $("#stop") && ($("#stop").onclick = () => stopRun(name));
    $("#forkbtn") && ($("#forkbtn").onclick = () => openFork(d, sel));
    $("#delbtn") && ($("#delbtn").onclick = () => openDelete(name, () => { location.hash = "#/runs"; }));
    $("#view3d") && ($("#view3d").onclick = () => { $('[data-seg="tab"] [data-v="model"]').click(); $("#tab").scrollIntoView({ behavior: "smooth", block: "start" }); });
  }
  function tick() {
    if (!d) return; const now = Date.now() / 1000 + offset;
    const c = $("#clock"); if (c) c.textContent = d.t_total ? `took ${dur(d.t_total)}` : d.t_start ? (d.live ? `${dur(now - d.t_start)} elapsed` : `stopped`) : "";
    const r = d.review, ring = $("#ring");
    if (r && ring && !r.manual && r.grace > 0 && r.opened) {
      const left = Math.max(0, r.grace - (now - r.opened)), C = 2 * Math.PI * 32;
      $(".fg", ring).style.strokeDashoffset = C * (1 - left / r.grace); $("span", ring).textContent = left > 0 ? dur(left) : "…";
    }
  }
  every(1000, tick);

  function review() {
    const r = d.review, box = $("#review");
    const s = r ? JSON.stringify([r.gate, r.opened, r.verdict, r.images, r.judge_best, r.manual]) : "";
    if (s === sig.review) return; sig.review = s;
    if (!r) { box.innerHTML = ""; return; }
    const notes = $("#notes")?.value || "";   // keep what you typed while the judges were still voting
    const C = 2 * Math.PI * 32, jb = r.judge_best;
    const gateName = r.kind === "look" ? "Pick a look" : { pick: "Pick a redraw", mesh_check: "3D shape", rig_check: "Rig check", orient: "Front of the model" }[r.gate] || r.gate;
    const single = r.choose && r.images.length === 1;
    const acts = r.kind === "look"
      ? `<button class="btn btn-primary" data-a="choose" id="usesel" disabled>Use this look</button>
         <button class="btn btn-ghost" data-a="redo">Redraw all looks</button>`
      : single
      ? `<button class="btn btn-primary" data-a="useone">Use this</button>
         <button class="btn btn-ghost" data-a="redo">${r.gate === "pick" ? "Try another redraw" : "Try another shape"}</button>
         ${r.you_judge ? "" : `<button class="btn btn-ghost" data-a="none">Keep judges' decision</button>`}`
      : r.choose
      ? `<button class="btn btn-primary" data-a="choose" id="usesel" disabled>Use selected</button>
         <button class="btn btn-ghost" data-a="judge" ${jb ? "" : "disabled"}>Keep judges' pick${jb ? ` (#${jb})` : ""}</button>
         <button class="btn btn-danger" data-a="redo">${r.gate === "pick" ? "Redraw again" : "Make new candidates"}</button>`
      : `<button class="btn btn-ok" data-a="accept">Accept &amp; continue</button><button class="btn btn-danger" data-a="reject">Reject &amp; retry</button>
         ${r.you_judge ? "" : `<button class="btn btn-ghost" data-a="none">Keep judges' decision</button>`}`;
    box.innerHTML = `<section class="review">
      <div class="rv-head"><div><div class="eb">Your call · ${esc(gateName)}</div><h2>${esc(r.title)}</h2><div class="verdict"><b>Judges</b><span>${esc(r.verdict)}</span></div></div>
        ${r.manual || !r.grace ? `<div class="ring manual" id="ring"><span>${r.kind === "look" ? "pick a look · no time limit" : r.you_judge ? "you are the judge" : r.manual && r.grace === 0 && /voting/.test(r.verdict) ? "judges voting · you can choose now" : "waiting for you"}</span></div>`
          : `<div class="ring" id="ring"><svg width="74" height="74"><circle class="bg" cx="37" cy="37" r="32"/><circle class="fg" cx="37" cy="37" r="32" stroke-dasharray="${C}" stroke-dashoffset="0"/></svg><span></span></div>`}</div>
      <div class="cands">${r.images.map((u, i) => `<div class="cand" data-k="${i + 1}"><img src="${esc(u)}" alt="" loading="lazy"><span class="no">${i + 1}</span>
        ${r.choose && jb === i + 1 ? `<span class="jp">Judges' pick</span>` : ""}<button class="zm" data-zoom="${i}" title="Enlarge">${ICON.zoom}</button>
        <div class="cp">${esc(r.captions[i] || "")}</div></div>`).join("")}</div>
      <textarea class="notes" id="notes" autocomplete="off" placeholder="Your observations (optional): added to the next redraw prompt and shown to the judges"></textarea>
      <div class="rv-act">${acts}${r.gate === "mesh_check" && d.models.length ? `<button type="button" class="btn btn-ghost" data-v3d="1">Inspect in 3D</button>` : ""}<span class="rv-msg" id="rvmsg"></span></div></section>`;
    $("#notes").value = notes;
    let chosen = 0;
    const list = r.images.map((u, i) => ({ url: u, title: `#${i + 1} · ${r.captions[i] || ""}` }));
    box.onclick = async (e) => {
      const z = e.target.closest("[data-zoom]"); if (z) { e.stopPropagation(); return openLB(list, +z.dataset.zoom); }
      if (e.target.closest("[data-v3d]")) { $('[data-seg="tab"] [data-v="model"]').click(); return $("#tab").scrollIntoView({ behavior: "smooth", block: "start" }); }
      const c = e.target.closest(".cand");
      if (c && r.choose) { $$(".cand", box).forEach((x) => x.classList.toggle("sel", x === c)); chosen = +c.dataset.k; const b = $("#usesel"); b.disabled = false; b.textContent = r.kind === "look" ? `Use ${r.captions[chosen - 1] || "#" + chosen}` : `Use #${chosen}`; return; }
      if (c) return openLB(list, +c.dataset.k - 1);
      const a = e.target.closest("[data-a]"); if (!a) return;
      const act = a.dataset.a, body = { run: name, gate: r.gate, notes: $("#notes").value,
        action: act === "judge" || act === "useone" ? "choose" : act, choice: act === "choose" ? chosen : act === "judge" ? jb : act === "useone" ? 1 : 0 };
      $$(".rv-act button", box).forEach((b) => (b.disabled = true));
      try { await api("/api/review", { method: "POST", body: JSON.stringify(body) }); sentFor = s; $("#rvmsg").textContent = "Sent. The run continues in a moment."; $("#notes").value = ""; }
      catch { $("#rvmsg").textContent = "Could not reach the server."; $$(".rv-act button", box).forEach((b) => (b.disabled = false)); }
    };
    if (sentFor === s) { $$(".rv-act button", box).forEach((b) => (b.disabled = true)); $("#rvmsg").textContent = "Sent. The run continues in a moment."; }
    tick();
  }

  function side() {
    const x = sel && d.stages.find((s) => s.key === sel);
    const s = JSON.stringify([sel, x, d.plan, d.files, d.zip, d.options, d.human_reviews]);
    if (s === sig.side) return; sig.side = s;
    const fileIcon = (n) => (n.split(".").pop() || "").toUpperCase().slice(0, 4);
    $("#side").innerHTML = (x ? `<div class="panel"><h3>Stage ${NUM[x.key]} · ${esc(x.label)}</h3><dl class="kv">
        <dt>Status</dt><dd>${esc(x.status)}</dd><dt>Model</dt><dd>${esc(x.model)}</dd>${x.seconds ? `<dt>Time</dt><dd>${dur(x.seconds)}</dd>` : ""}
        ${x.peak_vram ? `<dt>Peak VRAM</dt><dd>${x.peak_vram} GB</dd>` : ""}${x.note ? `<dt>Result</dt><dd>${esc(x.note)}</dd>` : ""}</dl>
        ${!d.live && FORK_OF[x.key] ? `<button class="btn btn-ghost btn-sm" style="margin-top:16px" id="forkhere">${ICON.fork} Fork from ${esc(LABEL_OF(FORK_OF[x.key]))}</button>` : ""}</div>` : "")
      + (d.human_notes ? `<div class="panel"><h3>Instructions in effect</h3><p style="margin:0;color:var(--ink2);font-size:14px">${esc(d.human_notes)}</p></div>` : "")
      + (d.files.length || d.zip ? `<div class="panel"><h3>Downloads</h3><div class="files">
          ${d.zip ? `<a class="zip" href="${d.zip}" download><span class="fi">ZIP</span><span><b>Mixamo zip</b><small>OBJ + texture · built on first click</small></span></a>` : ""}
          ${d.files.map((f) => `<a href="${esc(f.url)}" download><span class="fi">${fileIcon(f.name)}</span><span><b>${esc(f.label)}</b><small>${esc(f.name)}</small></span></a>`).join("")}</div></div>` : "")
      + (Object.keys(d.plan).length ? `<div class="panel"><h3>What the planner saw</h3><dl class="kv">${Object.entries(d.plan).map(([k, v]) =>
          `<dt>${esc(k)}</dt><dd>${esc(Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : v)}</dd>`).join("")}</dl></div>` : "")
      + `<div class="panel"><h3>Options</h3><dl class="kv"><dt>Outfit</dt><dd>${esc(d.options.outfit)}</dd><dt>Review</dt><dd>${esc(d.options.review)} · ${esc(d.options.grace)} s</dd>
          <dt>Style</dt><dd>${esc(d.options.style || "auto")}</dd></dl></div>`
      + (d.human_reviews.length ? `<div class="panel"><h3>Your decisions</h3><dl class="kv">${d.human_reviews.map((h) =>
          `<dt>${esc(h.time)}</dt><dd>${esc(h.gate)}: ${esc(h.action)}${h.action === "choose" ? " #" + h.choice : ""}${h.notes ? ` · “${esc(h.notes)}”` : ""}</dd>`).join("")}</dl></div>` : "");
  }

  $("#side").addEventListener("click", (e) => { if (e.target.closest("#forkhere")) openFork(d, FORK_OF[sel]); });

  let repairCtl = null, retexCtl = null;
  async function tabView() {
    const T = $("#tab");
    if (tab !== "repair" && repairCtl) { repairCtl.dispose(); repairCtl = null; }
    if (tab !== "retex" && retexCtl) { retexCtl.dispose(); retexCtl = null; }
    if (tab === "activity") {
      const snaps = d.snapshots.filter((x) => !sel || x.stage === sel || (sel === "pick" && x.stage === "edit")).slice().reverse();
      const s = JSON.stringify(["a", sel, snaps.map((x) => [x.url, x.images.length])]); if (s === sig.tab) return; sig.tab = s;
      if (viewer) { viewer.dispose(); viewer = null; }
      const list = [];   // every image on the tab, in order, for the lightbox
      snaps.forEach((x) => (x._items = [], x.images.length ? x.images.map((im) => ({ url: im.url, title: `${x.label} · ${im.caption || x.title}` })) : x.url ? [{ url: x.url, title: `${x.time} · ${x.label} · ${x.title}` }] : [])
        .forEach((it) => { it.i = list.length; list.push(it); x._items = (x._items || []).concat(it); }));
      T.innerHTML = (sel ? `<div style="margin-bottom:18px"><span class="chip">Showing ${esc(d.stages.find((s) => s.key === sel)?.label)} <button id="clr">✕</button></span></div>` : "")
        + (snaps.length ? `<div class="tl">${snaps.map((x) => `<article class="ti${/FAILED/.test(x.title) ? " f" : ""}"><div class="hd"><time>${esc(x.time)}</time><span class="chip">${esc(x.label)}</span><b>${esc(x.title)}</b></div>
          ${x.images.length ? `<div class="gal${x.images.length === 1 ? " one" : ""}">${x._items.map((it, k) => `<figure><img src="${esc(it.url)}" loading="lazy" data-i="${it.i}" alt="">
              ${x.images[k].caption ? `<figcaption>${esc(x.images[k].caption)}</figcaption>` : ""}</figure>`).join("")}</div>${x.text ? `<pre class="note">${esc(x.text)}</pre>` : ""}`
            : x.url ? `<img class="sheet" src="${esc(x.url)}" loading="lazy" data-i="${x._items[0].i}" alt="">` : x.text ? `<pre class="note">${esc(x.text)}</pre>` : ""}</article>`).join("")}</div>`
          : `<div class="empty">Nothing here yet.</div>`);
      $("#clr") && ($("#clr").onclick = () => { sel = null; sig.tab = sig.side = ""; render(); });
      T.onclick = (e) => { const im = e.target.closest("img[data-i]"); if (im) openLB(list, +im.dataset.i); };
    } else if (tab === "looks") {
      const L = d.looks; const s = JSON.stringify(["k", L, d.live, d.status]); if (s === sig.tab) return; sig.tab = s;
      if (viewer) { viewer.dispose(); viewer = null; }
      const tiles = L ? [{ look: "raw", label: "Raw input", url: L.raw }, ...(L.asis ? [{ look: "asis", label: "As is (this run's redraw)", url: L.asis }] : []), ...L.items] : [];
      const lb2 = tiles.map((t) => ({ url: t.url, title: t.label }));
      const busy = L && ["queued", "running"].includes(L.status);
      T.innerHTML = `<div class="looks-head"><div><b>Target looks</b><span>One redraw per look from this run's input, to choose a style before forking.</span></div>
          <button class="btn ${L ? "btn-ghost" : "btn-glow"} btn-sm" id="genlooks" ${busy ? "disabled" : ""}>${busy ? (L.status === "queued" ? "Queued: waits for the GPU" : "Generating…") : L ? "Regenerate" : "Generate look previews"}</button></div>
        ${tiles.length ? `<div class="looks">${tiles.map((t, i) => `<figure class="lk"><img src="${esc(t.url)}" data-i="${i}" loading="lazy" alt=""><figcaption><b>${esc(t.label)}</b>
            ${t.look !== "raw" ? `<button class="btn btn-ghost btn-sm" data-forklook="${esc(t.look)}" ${d.live ? "disabled title='Available when the run is not running'" : ""}>${ICON.fork} Fork with this look</button>` : ""}</figcaption></figure>`).join("")}
            ${busy ? LOOKS.slice(2).filter(([k]) => !L.items.some((x) => x.look === k)).map(([k, l]) => `<figure class="lk pending"><div class="ph"><i></i></div><figcaption><b>${l}</b><small>waiting</small></figcaption></figure>`).join("") : ""}</div>`
          : `<div class="empty">No previews yet. They take about a minute per look and wait for the GPU if a run is busy.</div>`}`;
      T.onclick = async (e) => {
        const im = e.target.closest("img[data-i]"); if (im) return openLB(lb2, +im.dataset.i);
        const fl = e.target.closest("[data-forklook]"); if (fl) return openFork(d, "edit", { look: fl.dataset.forklook === "asis" ? "asis" : fl.dataset.forklook });
        if (e.target.closest("#genlooks")) { try { const r = await fetch("/api/looks", { method: "POST", body: JSON.stringify({ run: name }) }); const jj = await r.json();
          toast(r.ok ? "Look previews queued" : jj.error || "Could not queue", !r.ok); } catch { toast("Could not reach the server", true); } }
      };
    } else if (tab === "animate") {
      const A = d.animations, rigged = !!d.stages.find((x) => x.key === "rig" && x.status === "done") || d.files.some((f) => /rig/i.test(f.label));
      const s = JSON.stringify(["an", A, rigged, d.live]); if (s === sig.tab) return; sig.tab = s;
      const typed = $("#aprompts")?.value || ""; if (viewer) { viewer.dispose(); viewer = null; }
      const busy = A && ["queued", "running"].includes(A.status);
      T.innerHTML = `<div class="anim-form"><div><b>Text to animation</b><span>Describe one motion per line, in plain words (“walks forward”, “raises both arms and cheers”). UniMate animates your rigged character locally; clips take under a minute.</span></div>
        <textarea class="notes" id="aprompts" rows="3" placeholder="walks forward&#10;waves with the right hand&#10;jumps in place" ${rigged ? "" : "disabled"}></textarea><div id="apresets" class="presetbox"></div>
        <div class="rv-act"><label class="inl">Clips per prompt <select class="input" id="areps" style="width:70px;height:36px"><option>1</option><option selected>2</option><option>3</option><option>4</option></select></label>
          <button class="btn btn-glow" id="agen" ${rigged && !busy ? "" : "disabled"}>${busy ? (A.status === "queued" ? "Queued: waits for the GPU" : "Generating…") : "Generate clips"}</button>
          <span class="rv-msg" id="amsg">${rigged ? "" : "Available once the rig is built."}${A?.status === "failed" ? " Last attempt failed: " + esc(A.error || "see the log") : ""}</span></div></div>
        ${A && A.clips.length ? `<div class="viewer anim-view" id="avw"><div class="vload" id="avl"><div style="text-align:center">Loading clip<div class="p"><i></i></div></div></div>
            <div class="vbar"><button data-o="play" class="on">Pause</button><button data-o="slow">0.5×</button><button data-o="norm" class="on">1×</button><button data-o="bones">Bones</button></div></div>
          <div class="clips">${A.clips.map((c, i) => `<button class="clip" data-c="${i}"><b>${esc(c.prompt)}</b><small>take ${c.rep + 1}${c.textured ? " · textured" : ""}</small></button>`).join("")}</div>
          <div class="clipdl" id="clipdl"></div>`
          : `<div class="empty" style="margin-top:20px">${busy ? "Generating the first clips…" : "No clips yet. Type a prompt above."}</div>`}`;
      $("#aprompts").value = typed; presetPicker($("#aprompts"), $("#apresets"));
      $("#agen").onclick = async () => {
        const ps = $("#aprompts").value.split("\n").map((x) => x.trim()).filter(Boolean); if (!ps.length) { $("#amsg").textContent = "Type at least one prompt."; return; }
        $("#agen").disabled = true;
        try { const r = await fetch("/api/animate", { method: "POST", body: JSON.stringify({ run: name, prompts: ps, reps: +$("#areps").value }) }); const jj = await r.json();
          toast(r.ok ? "Generating clips…" : jj.error || "Could not start", !r.ok); if (!r.ok) $("#agen").disabled = false; else $("#aprompts").value = ""; }
        catch { toast("Could not reach the server", true); $("#agen").disabled = false; } };
      if (A && A.clips.length) {
        const { createViewer } = await import("/static/viewer.js"); if (!document.body.contains($("#avw"))) return;
        viewer = createViewer($("#avw"), {}); const st = { play: true, speed: 1, bones: false };
        const show = async (i) => { $$(".clip", T).forEach((x) => x.classList.toggle("on", +x.dataset.c === i)); $("#avl").hidden = false; const c = A.clips[i];
          try { await viewer.load(c.url); } catch { $("#avl").innerHTML = "Could not load this clip."; return; } $("#avl").hidden = true; viewer.set(st);
          $("#clipdl").innerHTML = `<a class="btn btn-ghost btn-sm" href="${esc(c.url)}" download>GLB</a>${c.fbx ? `<a class="btn btn-ghost btn-sm" href="${esc(c.fbx)}" download>FBX</a>` : ""}`; };
        $(".clips", T).onclick = (e) => { const b = e.target.closest(".clip"); if (b) show(+b.dataset.c); };
        $(".anim-view .vbar", T).onclick = (e) => { const b = e.target.closest("button"); if (!b) return; const o = b.dataset.o;
          if (o === "play") { st.play = !st.play; b.textContent = st.play ? "Pause" : "Play"; b.classList.toggle("on", st.play); viewer.set({ play: st.play }); }
          else if (o === "slow" || o === "norm") { st.speed = o === "slow" ? 0.5 : 1; $$('[data-o="slow"],[data-o="norm"]', T).forEach((x) => x.classList.toggle("on", x === b)); viewer.set({ speed: st.speed }); }
          else if (o === "bones") { st.bones = !st.bones; b.classList.toggle("on", st.bones); viewer.set({ bones: st.bones }); } };
        show(A.clips.length - 1);      // the newest clip
      }
    } else if (tab === "repair") {
      const s = JSON.stringify(["p", (d.models.find((m) => m.key === "mesh_glb") || {}).url]); if (s === sig.tab && repairCtl) return; sig.tab = s;
      if (viewer) { viewer.dispose(); viewer = null; } if (repairCtl) { repairCtl.dispose(); repairCtl = null; }
      const { createViewer } = await import("/static/viewer.js"); const { mountRepair } = await import("/static/repair.js"); if (!document.body.contains(T)) return;
      repairCtl = await mountRepair(T, d, { createViewer, toast });
    } else if (tab === "retex") {
      const s = JSON.stringify(["x", (d.models.find((m) => m.key === "final_glb") || {}).url, (d.models.find((m) => m.key === "mesh_glb") || {}).url]); if (s === sig.tab && retexCtl) return; sig.tab = s;
      if (viewer) { viewer.dispose(); viewer = null; } if (retexCtl) { retexCtl.dispose(); retexCtl = null; }
      const { createViewer } = await import("/static/viewer.js"); const { mountRetex } = await import("/static/retex.js"); if (!document.body.contains(T)) return;
      retexCtl = await mountRetex(T, d, { createViewer, toast });
    } else if (tab === "log") {
      const s = JSON.stringify(["l", d.log.length, d.log[d.log.length - 1]]); if (s === sig.tab) return; sig.tab = s;
      if (viewer) { viewer.dispose(); viewer = null; }
      const old = $(".log", T), stick = !old || old.scrollTop + old.clientHeight > old.scrollHeight - 30;
      const cls = (l) => /Traceback|Error|FAILED|failed/.test(l) ? "e" : /^\S+ !!|Waiting/.test(l) ? "w" : /--- stage|=== /.test(l) ? "s" : /done in|picked|PASS|accept/i.test(l) ? "k" : "";
      T.innerHTML = `<div class="log">${d.log.map((l) => { const m = l.match(/^(\d\d:\d\d:\d\d )(.*)$/); return m ? `<span class="d">${m[1]}</span><span class="${cls(l)}">${esc(m[2])}</span>` : `<span class="${cls(l)}">${esc(l)}</span>`; }).join("\n")}</div>`;
      const lg = $(".log", T); if (stick) lg.scrollTop = lg.scrollHeight; else lg.scrollTop = old.scrollTop;
    } else {
      const s = JSON.stringify(["m", d.models]); if (s === sig.tab) return; sig.tab = s;
      if (viewer) { viewer.dispose(); viewer = null; }
      if (!d.models.length) { T.innerHTML = `<div class="empty">No 3D model yet. The shape candidates appear here while you judge them, and the textured model as soon as it is built.</div>`; return; }
      T.innerHTML = `<div class="viewer" id="vw"><div class="vload" id="vl"><div style="text-align:center">Loading model<div class="p"><i></i></div></div></div><div class="vinfo" id="vi"></div>
        <div class="vbar">${d.models.map((m, i) => `<button data-m="${i}" class="${i === 0 ? "on" : ""}">${esc(m.label)}</button>`).join("")}<span class="sep"></span>
        <button data-o="clay">Clay</button><button data-o="wire">Wireframe</button><button data-o="bones" hidden>Bones</button><button data-o="rotate" class="on">Turntable</button><button data-o="reset">Reset</button></div></div>`;
      const { createViewer } = await import("/static/viewer.js");
      if (!document.body.contains($("#vw"))) return;
      const opts = { clay: false, wire: false, bones: false, rotate: true };
      viewer = createViewer($("#vw"), { onProgress: (p) => { const i = $("#vl .p i"); if (i) i.style.width = p * 100 + "%"; },
        onInfo: (i) => { $("#vi").textContent = `${i.tris.toLocaleString()} triangles${i.skinned ? ` · ${i.bones} bones` : ""}`; $('[data-o="bones"]').hidden = !i.skinned; } });
      const load = async (m) => { $("#vl").hidden = false; try { await viewer.load(m.url); } catch (e) { $("#vl").innerHTML = "Could not load this model."; return; } $("#vl").hidden = true; viewer.set(opts); };
      $(".vbar").onclick = (e) => { const b = e.target.closest("button"); if (!b) return;
        if (b.dataset.m) { $$(".vbar [data-m]").forEach((x) => x.classList.toggle("on", x === b)); load(d.models[+b.dataset.m]); }
        else if (b.dataset.o === "reset") viewer.reset();
        else { const k = b.dataset.o; opts[k] = !opts[k]; b.classList.toggle("on", opts[k]); viewer.set({ [k]: opts[k] }); } };
      load(d.models[0]);
    }
  }

  function alertBox() { const a = d.alert, el = $("#alert");
    el.innerHTML = a ? `<div class="alertbar"><b>${d.live ? "Needs your attention" : "Why it stopped"}</b><span>${esc(a.msg)}</span><time>${esc(a.time)}</time></div>` : ""; }
  function render() { if (!d) return; header(); alertBox(); updateFlow($("#flow"), edges, d, sel); review(); side(); tabView(); tick(); }
  let lastJSON = "";
  onCleanup(() => { if (repairCtl) { repairCtl.dispose(); repairCtl = null; } if (retexCtl) { retexCtl.dispose(); retexCtl = null; } });
  async function poll() {
    try {
      const j = await api("/api/run/" + encodeURIComponent(name));
      offset = j.now - Date.now() / 1000;
      const js = JSON.stringify({ ...j, now: 0 }); if (js === lastJSON) return; lastJSON = js; d = j; render();
    } catch (e) {
      if (e.status === 404 && !d) $("#meta").innerHTML = `<span class="pill running"><i></i>Starting</span><span>waiting for the run to begin…</span>`;
    }
  }
  await poll(); every(2000, poll);
}

/* ======================================================================= router */
async function route() {
  const h0 = decodeURIComponent(location.hash.replace(/^#/, "")) || "/";
  if (page.kind === "home" && ["/", "/new", "/runs", "/tips"].includes(h0)) {      // same page: just scroll
    $$(".nav-links a").forEach((a) => a.classList.toggle("on", (a.dataset.nav === "new" && h0 === "/new") || (a.dataset.nav === "tips" && h0 === "/tips") || (a.dataset.nav === "runs" && h0 !== "/new" && h0 !== "/tips")));
    return h0 === "/" ? scrollTo({ top: 0, behavior: "smooth" }) : document.getElementById(h0.slice(1))?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  disposePresetViewers(); page.cleanup.forEach((f) => { try { f(); } catch {} }); page = { cleanup: [], kind: /^\/run\//.test(h0) ? "run" : "home" };
  $("#lightbox").hidden = true;
  const h = decodeURIComponent(location.hash.replace(/^#/, "")) || "/";
  const m = h.match(/^\/run\/(.+)$/);
  $$(".nav-links a").forEach((a) => a.classList.toggle("on", (a.dataset.nav === "new" && h === "/new") || (a.dataset.nav === "tips" && h === "/tips") || (a.dataset.nav === "runs" && (h === "/runs" || h === "/"))));
  scrollTo({ top: 0, behavior: "instant" });
  if (m) { document.title = `${m[1]} · homunculus`; await runPage(m[1]); }
  else { document.title = "homunculus"; await home(h === "/new" ? "new" : h === "/runs" ? "runs" : h === "/tips" ? "tips" : null); }
}
$("#tourbtn").onclick = () => startTour(page.kind === "run" ? "run" : "home");
addEventListener("hashchange", () => { stopTour(); route(); });
route();
