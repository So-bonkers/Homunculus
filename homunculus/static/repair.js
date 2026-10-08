// The Repair tab: paint the broken part of the pre-rig 3D model (brush, "select hands"), send it to the repair job and follow the result.
// Strokes are spheres [x, y, z, r] in the glTF scene's own coordinates (the model's frame, not the viewer's scaled one): the backend recomputes the vertex mask from them,
// so no vertex numbering has to match between the browser and Blender.
import * as THREE from "three";
import { computeBoundsTree, disposeBoundsTree, acceleratedRaycast } from "three-mesh-bvh";
THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const STEP = { queued: "Waiting for the GPU", regions: "Finding the region", running: "Working", merge: "Joining the new part", done: "Done" };
// Named regions of a T/A-posed figure (fractions of the height; glTF y is up): hands = the outer 10.5 % at each side, head = the top 13.5 %, crown = the top 7 % (a helmet's dome), feet = the lowest 5 %.
const PRESETS = { hands: { label: "hands", view: "front" }, head: { label: "head", view: "auto" }, crown: { label: "top of the head or helmet", view: "top" }, feet: { label: "feet", view: "auto" } };

export async function mountRepair(host, d, { createViewer, toast }) {
  const meshDone = (d.stages.find((s) => s.key === "mesh") || {}).status === "done";
  const mesh = meshDone ? (d.models.find((m) => m.key === "mesh_glb") || d.models.find((m) => m.key === "final_glb")) : null;
  if (!mesh) { host.innerHTML = `<div class="empty">No finished 3D model yet. The Repair tab works on the model before rigging, once the 3D shape stage has finished (you can already inspect the model in the 3D model tab).</div>`; return { dispose() {} }; }
  host.innerHTML = `<div class="repair">
    <div class="rp-left"><div class="viewer rp-view" id="rpv"><div class="vload" id="rpl"><div style="text-align:center">Loading model<div class="p"><i></i></div></div></div>
        <div class="rp-hint" id="rphint">Drag to paint the broken part · right-drag or scroll to move the view</div>
        <div class="vbar rp-bar"><button data-t="paint" class="on">Paint</button><button data-t="erase">Erase</button>
          <label class="rp-size" title="[ and ] change it, or Alt + scroll">Brush <input type="range" id="rpsize" min="0.3" max="25" step="0.1" value="3"><output id="rpsizeo">3%</output></label><span class="sep"></span>
          <button data-t="hands">Hands</button><button data-t="head">Head</button><button data-t="crown">Crown</button><button data-t="feet">Feet</button><button data-t="clear">Clear</button></div></div></div>
    <div class="rp-right"><h3>Repair a region</h3>
      <p class="hint">Paint over anything that came out broken (cut-off or fused fingers, a crumpled helmet top, a melted foot, a dented limb), a little of the neighbouring part included, or press a region button. The image model redraws that part from the side it faces, Pixal3D turns the redraw into a mesh again and it is joined where the broken part met the rest. Works on the model before rigging.</p>
      <div class="row2"><div class="field"><label class="flabel" for="rplabel">What is it?</label><input class="input" id="rplabel" maxlength="80" placeholder="e.g. the top of the helmet" spellcheck="false"></div>
        <div class="field"><label class="flabel" for="rpview">Redraw from</label><select class="input" id="rpview"><option value="auto">Automatic</option><option value="front">Front</option><option value="back">Back</option><option value="left">Left side</option><option value="right">Right side</option><option value="top">Above</option></select></div></div>
      <textarea class="notes" id="rpnotes" rows="2" placeholder="Optional: e.g. the glove has a white wrist band; a smooth round dome with no crease"></textarea>
      <div class="rp-go" style="margin-top:8px"><button class="btn btn-ghost btn-sm" id="rpadd" disabled title="Keep this selection (with its label and view) and select another part: each part is redrawn with its own prompt and checks">Add this part, select another</button></div>
      <div id="rpstaged" class="hint" style="margin:6px 0"></div>
      <div class="rp-go"><button class="btn btn-glow" id="rpgo" disabled>Repair painted region</button><span class="hint" id="rpmsg" style="margin:0"></span></div>
      <div id="rpjobs"></div></div></div>`;
  const $ = (s, r = host) => r.querySelector(s);
  let strokes = [], staged = [], tool = "paint", down = false, last = 0, disposed = false, timer = 0, root = null, inst = null, curUrl = mesh.url, viewing = "original";
  const viewer = createViewer($("#rpv"), { onProgress: (p) => { const i = $("#rpl .p i"); if (i) i.style.width = p * 100 + "%"; } });
  const X = viewer.internals(); const { camera, controls, renderer, scene } = X;
  const cursor = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 14), new THREE.MeshBasicMaterial({ color: 0xff375f, transparent: true, opacity: 0.28, depthWrite: false })); cursor.visible = false; scene.add(cursor);
  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
  const brushWorld = () => (+$("#rpsize").value / 100) * 1.8;        // the viewer scales every model to 1.8 units tall; the slider is % of the height
  const brushLocal = () => brushWorld() / (root ? root.scale.x : 1);

  async function show(url) {
    $("#rpl").hidden = false; strokes = [];
    try { await viewer.load(url); } catch { $("#rpl").innerHTML = "Could not load this model."; return; }
    if (disposed) return; $("#rpl").hidden = true; viewer.set({ rotate: false }); root = X.root();
    root.traverse((o) => { if (o.isMesh && !o.geometry.boundsTree) o.geometry.computeBoundsTree(); });
    if (inst) { inst.parent && inst.parent.remove(inst); inst.dispose(); }
    inst = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 10, 8), new THREE.MeshBasicMaterial({ color: 0xff375f, transparent: true, opacity: 0.55, depthWrite: false }), 1500); inst.count = 0; inst.frustumCulled = false; inst.raycast = () => {}; root.add(inst);
    update(); curUrl = url;
  }

  function update() {
    const m = new THREE.Matrix4(), all = [...staged.flatMap((g) => g.strokes), ...strokes].slice(0, 1500);      // kept parts stay visible while you select the next one
    all.forEach((s, i) => { m.compose(new THREE.Vector3(s[0], s[1], s[2]), new THREE.Quaternion(), new THREE.Vector3(s[3], s[3], s[3])); inst.setMatrixAt(i, m); });
    inst.count = all.length; inst.instanceMatrix.needsUpdate = true;
    const n = staged.length + (strokes.length ? 1 : 0);
    $("#rpgo").disabled = !n || viewing !== "original"; $("#rpgo").textContent = n > 1 ? `Repair ${n} parts` : strokes.length ? `Repair painted region (${strokes.length} dabs)` : "Repair painted region";
    $("#rpadd").disabled = !strokes.length || viewing !== "original" || staged.length >= 5;
    $("#rpstaged").innerHTML = staged.map((g, i) => `<span class="pill running" style="margin-right:6px"><i></i>${esc(g.label || "painted part")} · ${esc(g.view)} <a href="#" data-unstage="${i}" title="remove">✕</a></span>`).join("");
  }

  function hit(e) {
    const r = renderer.domElement.getBoundingClientRect(); ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ptr, camera); ray.firstHitOnly = true; const h = ray.intersectObject(root, true).find((x) => x.object.isMesh && x.object !== inst); return h ? h.point : null;
  }
  function dab(e) {
    if (!root || viewing !== "original") return; const p = hit(e); if (!p) { cursor.visible = false; return; }
    cursor.visible = true; cursor.position.copy(p); cursor.scale.setScalar(brushWorld());
    if (!down) return;
    const l = root.worldToLocal(p.clone()), r = brushLocal();
    if (tool === "erase") strokes = strokes.filter((s) => Math.hypot(s[0] - l.x, s[1] - l.y, s[2] - l.z) > r);
    else if (!strokes.length || !strokes.some((s) => Math.hypot(s[0] - l.x, s[1] - l.y, s[2] - l.z) < r * 0.35 && Math.abs(s[3] - r) < 1e-9) ) { if (strokes.length < 1500) strokes.push([l.x, l.y, l.z, r]); }
    update();
  }
  const el = renderer.domElement;
  el.addEventListener("pointerdown", (e) => { if (e.button !== 0 || viewing !== "original") return; down = true; controls.enabled = false; el.setPointerCapture(e.pointerId); dab(e); }, true);   // capture: before OrbitControls sees it
  el.addEventListener("pointermove", (e) => { const t = performance.now(); if (t - last < 30) return; last = t; dab(e); });
  el.addEventListener("pointerup", (e) => { down = false; controls.enabled = true; try { el.releasePointerCapture(e.pointerId); } catch {} });
  el.addEventListener("pointerleave", () => { cursor.visible = false; });
  controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };

  function selectRegion(name) {      // a named region of a T/A-posed figure, as voxels of 2.2 % of the height (the same rules as the backend's presets)
    const pts = [], v = new THREE.Vector3(); let lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
    root.updateMatrixWorld(true);
    root.traverse((o) => { if (!o.isMesh || o === inst) return; const a = o.geometry.attributes.position;
      for (let i = 0; i < a.count; i++) { v.fromBufferAttribute(a, i).applyMatrix4(o.matrixWorld); root.worldToLocal(v); pts.push(v.x, v.y, v.z);
        lo = [Math.min(lo[0], v.x), Math.min(lo[1], v.y), Math.min(lo[2], v.z)]; hi = [Math.max(hi[0], v.x), Math.max(hi[1], v.y), Math.max(hi[2], v.z)]; } });
    const height = hi[1] - lo[1], xc = (lo[0] + hi[0]) / 2, lim = (hi[0] - lo[0]) / 2 - 0.105 * height, cell = 0.022 * height, seen = new Map();
    const inside = { hands: (x, y) => Math.abs(x - xc) > lim, head: (x, y) => y > hi[1] - 0.135 * height, crown: (x, y) => y > hi[1] - 0.07 * height, feet: (x, y) => y < lo[1] + 0.05 * height }[name];
    for (let i = 0; i < pts.length; i += 3) if (inside(pts[i], pts[i + 1])) { const k = [Math.floor(pts[i] / cell), Math.floor(pts[i + 1] / cell), Math.floor(pts[i + 2] / cell)].join(","); if (!seen.has(k)) seen.set(k, [(Math.floor(pts[i] / cell) + 0.5) * cell, (Math.floor(pts[i + 1] / cell) + 0.5) * cell, (Math.floor(pts[i + 2] / cell) + 0.5) * cell, cell * 0.8]); }
    strokes = [...seen.values()].slice(0, 1500); update();
    if (strokes.length) { $("#rplabel").value = PRESETS[name].label; $("#rpview").value = PRESETS[name].view; }
    $("#rpmsg").textContent = strokes.length ? `${PRESETS[name].label} selected (${strokes.length} dabs). Check them, then press Repair.` : `Could not find the ${PRESETS[name].label}: paint them by hand.`;
  }

  $(".rp-bar").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; const t = b.dataset.t;
    if (t === "paint" || t === "erase") { tool = t; host.querySelectorAll('.rp-bar [data-t="paint"],.rp-bar [data-t="erase"]').forEach((x) => x.classList.toggle("on", x === b)); }
    else if (t === "clear") { strokes = []; update(); $("#rpmsg").textContent = ""; }
    else if (PRESETS[t] && root && viewing === "original") selectRegion(t); };
  const setSize = (v) => { const el = $("#rpsize"); el.value = Math.max(+el.min, Math.min(+el.max, v)); $("#rpsizeo").textContent = (+el.value).toFixed(+el.value < 10 ? 1 : 0) + "%"; cursor.scale.setScalar(brushWorld()); };
  $("#rpsize").oninput = () => setSize(+$("#rpsize").value); setSize(3);
  const keySize = (e) => { if (e.target.closest && e.target.closest("input,textarea,select")) return; if (e.key === "[") setSize(+$("#rpsize").value * 0.85); else if (e.key === "]") setSize(+$("#rpsize").value * 1.18); };
  addEventListener("keydown", keySize); renderer.domElement.addEventListener("wheel", (e) => { if (!e.altKey) return; e.preventDefault(); e.stopPropagation(); setSize(+$("#rpsize").value * (e.deltaY < 0 ? 1.12 : 0.89)); }, { passive: false, capture: true });

  const current = () => ({ strokes: strokes.slice(), label: $("#rplabel").value.trim(), view: $("#rpview").value });
  $("#rpadd").onclick = () => { if (!strokes.length) return; staged.push(current()); strokes = []; $("#rplabel").value = ""; $("#rpview").value = "auto"; update(); $("#rpmsg").textContent = `${staged.length} part${staged.length > 1 ? "s" : ""} kept. Select the next one, then press Repair.`; };
  $("#rpstaged").onclick = (e) => { const a = e.target.closest("[data-unstage]"); if (!a) return; e.preventDefault(); staged.splice(+a.dataset.unstage, 1); update(); };
  $("#rpgo").onclick = async () => {
    const b = $("#rpgo"), msg = $("#rpmsg"); b.disabled = true; msg.textContent = "Starting…";
    try {
      const groups = [...staged, ...(strokes.length ? [current()] : [])];
      const r = await fetch("/api/repair", { method: "POST", body: JSON.stringify({ run: d.name, groups, notes: $("#rpnotes").value.trim() }) }); const j = await r.json();
      if (!r.ok) { msg.textContent = j.error || "Could not start the repair."; update(); return; }
      staged = []; strokes = []; update();
      msg.textContent = ""; toast && toast("Repair started"); poll();
    } catch { msg.textContent = "Could not reach the server."; update(); }
  };

  async function poll() {
    if (disposed) return; let jobs = [];
    try { jobs = await (await fetch("/api/repair/" + encodeURIComponent(d.name), { cache: "no-store" })).json(); } catch {}
    render(jobs); clearTimeout(timer); if (!disposed && jobs.some((j) => ["queued", "running"].includes(j.status))) timer = setTimeout(poll, 2500);
  }
  function render(jobs) {
    const box = $("#rpjobs"); if (!box) return;
    box.innerHTML = jobs.map((j) => `<div class="rp-job ${esc(j.status)}"><div class="rp-jh"><b>${esc(j.job.replace(/^(\d{4})(\d\d)(\d\d)_(\d\d)(\d\d)(\d\d)$/, "$3.$2. $4:$5"))}</b>
        <span class="pill ${j.status === "done" ? "finished" : j.status === "failed" ? "failed" : "running"}"><i></i>${esc(j.status === "running" || j.status === "queued" ? (STEP[j.step] || j.status) : j.status)}</span>${j.seconds ? `<small>${j.seconds} s</small>` : ""}</div>
      ${j.error ? `<div class="alertbar"><span>${esc(j.error)}</span></div>` : ""}
      ${j.regions.map((r) => `<div class="rp-reg"><div class="rp-imgs">${r.crop ? `<figure><img src="${esc(r.crop)}" alt=""><figcaption>before</figcaption></figure>` : ""}
          ${(r.candidates || []).map((c) => `<figure class="${c === r.chosen ? "pick" : ""}"><img src="${esc(c)}" alt="" loading="lazy"><figcaption>${c === r.chosen ? "chosen" : "redraw"}</figcaption></figure>`).join("")}
          ${r.after ? `<figure class="after"><img src="${esc(r.after)}" alt=""><figcaption>after${r.after_fingers ? ` · ${r.after_fingers} fingers counted` : ""}</figcaption></figure>` : ""}</div>
          <small>${r.label ? esc(r.label) + " · " : ""}${esc(r.status || "")}${r.five_fingers === false ? " · no redraw had five fingers: best effort" : r.checked === false ? " · no redraw passed the check: best effort" : ""}</small></div>`).join("")}
      ${j.status === "running" || j.status === "queued" ? `<div class="rp-log">${j.log.map((l) => `<div>${esc(l)}</div>`).join("")}</div>` : ""}
      ${j.result ? `<div class="rp-act"><button class="btn btn-primary btn-sm" data-show="${esc(j.result)}">View repaired model</button><button class="btn btn-ghost btn-sm" data-show="orig">View original</button>
        <a class="btn btn-ghost btn-sm" href="${esc(j.result)}" download>Download .glb</a>${j.can_use ? `<button class="btn btn-glow btn-sm" data-use="${esc(j.job)}">Use for this run</button>` : ""}</div>${j.can_use ? `<div class="rp-use" id="use_${esc(j.job)}" hidden></div>` : ""}` : ""}</div>`).join("") || `<div class="hint" style="margin-top:14px">No repairs yet.</div>`;
  }
  $("#rpjobs").onclick = async (e) => {
    const u = e.target.closest("[data-use]");
    if (u) { const job = u.dataset.use, box = $("#use_" + job); box.hidden = false;
      box.innerHTML = `<div class="hint">One mesh with the original texture continues from the Colour stage (colour, rig, rig check, animation, texture). Needs the run to be stopped or finished.</div>
        <div class="row2"><div class="field"><span class="flabel">Where</span><select class="input" id="uw_${esc(job)}"><option value="new">New run (keeps this one)</option><option value="same">Replace in this run</option></select></div>
        <div class="field"><label class="flabel">Name</label><input class="input" id="un_${esc(job)}" value="${esc(d.name)}_repaired" maxlength="40" spellcheck="false"></div></div>
        <button class="btn btn-glow btn-sm" id="ug_${esc(job)}">Continue the run with it</button> <span class="hint" id="um_${esc(job)}"></span>`;
      $("#uw_" + job).onchange = (ev) => { $("#un_" + job).disabled = ev.target.value === "same"; };
      $("#ug_" + job).onclick = async () => { const msg = $("#um_" + job); msg.textContent = "Starting…";
        try { const r = await fetch("/api/repair_use", { method: "POST", body: JSON.stringify({ run: d.name, job, mode: $("#uw_" + job).value, name: $("#un_" + job).value.trim() }) }); const j = await r.json();
          if (!r.ok) { msg.textContent = j.error || "Could not start."; return; } toast && toast("Continuing with the repaired mesh"); location.hash = "#/run/" + encodeURIComponent(j.run); } catch { msg.textContent = "Could not reach the server."; } };
      return; }
    const b = e.target.closest("[data-show]"); if (!b) return; viewing = b.dataset.show === "orig" ? "original" : "repaired";
    $("#rphint").textContent = viewing === "original" ? "Drag to paint the broken part · right-drag or scroll to move the view" : "The repaired model (the original and the new part are separate shells joined where the broken part met the rest)";
    await show(viewing === "original" ? mesh.url : b.dataset.show); };

  await show(mesh.url); poll();
  return { dispose() { disposed = true; clearTimeout(timer); removeEventListener("keydown", keySize); try { viewer.dispose(); } catch {} } };
}
