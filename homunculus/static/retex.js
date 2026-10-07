// The Retexture tab: brush the part of the model to change, then either describe it and let the image model generate that view (default), or use a reference image
// lined up with the model (orbit until it matches, paint which pixels to use). The picture is projected from the locked camera onto the brushed area on the CPU.
import * as THREE from "three";
import { computeBoundsTree, disposeBoundsTree, acceleratedRaycast } from "three-mesh-bvh";
THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree; THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree; THREE.Mesh.prototype.raycast = acceleratedRaycast;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const readFile = (f) => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(f); });

export async function mountRetex(host, d, { createViewer, toast }) {
  let info = null; try { info = await (await fetch("/api/retex/" + encodeURIComponent(d.name), { cache: "no-store" })).json(); } catch {}
  if (!info || !info.base) { host.innerHTML = `<div class="empty">No textured 3D model yet. Retexture works on the model after the colour or texture stage.</div>`; return { dispose() {} }; }
  host.innerHTML = `<div class="repair retex">
    <div class="rp-left"><div class="rt-stage" id="rts"><div class="viewer rp-view" id="rtv" style="height:100%"><div class="vload" id="rtl"><div style="text-align:center">Loading model<div class="p"><i></i></div></div></div>
        <img class="rt-ref" id="rtref" alt="" hidden><canvas class="rt-mask" id="rtmask"></canvas><div class="rp-hint" id="rthint">Brush the part to change</div>
        <div class="vbar rp-bar"><button data-t="model" class="on">Brush model</button><button data-t="mask" id="rtmaskbtn" disabled>Mask picture</button><button data-t="orbit">Orbit</button><button data-t="erase">Erase</button>
          <label class="rp-size" title="[ and ] change it, or Alt + scroll">Size <input type="range" id="rtsize" min="0.3" max="25" step="0.1" value="3"><output id="rtsizeo">3%</output></label><span class="sep"></span>
          <button data-t="clear">Clear brush</button><button data-t="clearmask" disabled id="rtclearmask">Clear mask</button></div></div></div>
      <div class="rt-views"><span class="hint" style="margin:0">Quick views</span><button class="btn btn-ghost btn-sm" data-az="0">Front</button><button class="btn btn-ghost btn-sm" data-az="90">Right</button>
        <button class="btn btn-ghost btn-sm" data-az="180">Back</button><button class="btn btn-ghost btn-sm" data-az="270">Left</button>
        <label class="rp-size" id="rtopwrap" hidden>Picture <input type="range" id="rtop" min="0" max="100" value="55"></label></div></div>
    <div class="rp-right"><h3>Retexture a part</h3>
      <p class="hint">1. Brush the part to change. 2. Orbit to a view that shows it. 3. Pick where the new look comes from. The picture is projected onto the brushed area from that view, on the CPU.</p>
      ${seg2()}
      <div id="rtsrc_gen"><textarea class="notes" id="rtnotes" rows="3" placeholder="Describe what this part should look like: e.g. a worn brown leather jacket with white stitching and a small red patch on the shoulder"></textarea>
        <div class="rp-go"><button class="btn btn-glow" id="rtgen">Generate this view</button><span class="hint" id="rtgenmsg" style="margin:0"></span></div>
        <div class="hint">The image model redraws what you see in the viewer; the result is aligned with it and appears here (needs the GPU, about a minute).</div></div>
      <div id="rtsrc_ref" hidden><label class="drop rt-drop"><input type="file" id="rtfile" accept="image/*" hidden><b>Choose a reference picture</b><span>seen from any angle; then orbit until the model matches it (use the Picture slider), and paint on it which pixels to use</span></label></div>
      <div id="rtgenerated"></div>
      <div class="rp-go" style="margin-top:12px"><button class="btn btn-primary" id="rtapply" disabled>Apply to the brushed area</button><span class="hint" id="rtmsg" style="margin:0"></span></div>
      <div id="rtjobs"></div></div></div>`;
  const $ = (s, r = host) => r.querySelector(s);
  let strokes = [], mstrokes = [], tool = "model", erase = false, down = false, last = 0, disposed = false, timer = 0, root = null, inst = null, src = "gen", curUrl = info.base, view = "base";
  let refUrl = null, refFile = null, refGen = null, genCam = null, refAspect = null;
  const viewer = createViewer($("#rtv"), { onProgress: (p) => { const i = $("#rtl .p i"); if (i) i.style.width = p * 100 + "%"; } });
  const X = viewer.internals(); const { camera, controls, renderer, scene } = X;
  const cursor = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 14), new THREE.MeshBasicMaterial({ color: 0x2997ff, transparent: true, opacity: 0.3, depthWrite: false })); cursor.visible = false; scene.add(cursor);
  const ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
  const bw = () => (+$("#rtsize").value / 100) * 1.8, bl = () => bw() / (root ? root.scale.x : 1);

  async function show(url) {
    $("#rtl").hidden = false; strokes = [];
    try { await viewer.load(url); } catch { $("#rtl").innerHTML = "Could not load this model."; return; }
    if (disposed) return; $("#rtl").hidden = true; viewer.set({ rotate: false }); root = X.root();
    root.traverse((o) => { if (o.isMesh && !o.geometry.boundsTree) o.geometry.computeBoundsTree(); });
    if (inst) { inst.parent && inst.parent.remove(inst); inst.dispose(); }
    inst = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 10, 8), new THREE.MeshBasicMaterial({ color: 0x2997ff, transparent: true, opacity: 0.45, depthWrite: false }), 1500); inst.count = 0; inst.frustumCulled = false; inst.raycast = () => {}; root.add(inst);
    upd(); curUrl = url;
  }
  function upd() {
    const m = new THREE.Matrix4(); strokes.forEach((s, i) => { m.compose(new THREE.Vector3(s[0], s[1], s[2]), new THREE.Quaternion(), new THREE.Vector3(s[3], s[3], s[3])); inst.setMatrixAt(i, m); });
    inst.count = strokes.length; inst.instanceMatrix.needsUpdate = true; check();
  }
  function check() {
    const b = $("#rtapply"), ok = view === "base" && (src === "ref" ? !!(refFile || refGen) : !!refGen);
    b.disabled = !ok; $("#rtmsg").textContent = view !== "base" ? "Showing a result: go back to the model to apply another." : !ok ? (src === "ref" ? "Choose a reference picture first." : "Generate a view first.") : strokes.length ? "" : "No brush: the whole visible surface will change.";
  }
  const camJSON = () => {
    const m = root.matrixWorld.clone().invert().multiply(camera.matrixWorld);
    return { elements: m.elements.slice(), fov: camera.fov, aspect: camera.aspect, min_cos: 0.15, feather: 0.35 };
  };
  function setCamera(elements) {      // snap the viewer back to the camera a view was generated from
    const w = root.matrixWorld.clone().multiply(new THREE.Matrix4().fromArray(elements)), p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3(); w.decompose(p, q, s);
    const dist = camera.position.distanceTo(controls.target) || 3; camera.position.copy(p); camera.quaternion.copy(q);
    controls.target.copy(p).add(new THREE.Vector3(0, 0, -dist).applyQuaternion(q)); controls.update();
  }
  function setAspect(a) { refAspect = a; const st = $("#rts"); st.style.aspectRatio = a ? String(a) : "0.75"; st.style.maxWidth = a ? `min(100%, ${Math.round(a * 620)}px)` : ""; }

  function hit(e) {
    const r = renderer.domElement.getBoundingClientRect(); ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ptr, camera); ray.firstHitOnly = true; const h = ray.intersectObject(root, true).find((x) => x.object.isMesh && x.object !== inst); return h ? h.point : null;
  }
  function dab(e) {
    if (!root || tool !== "model" || view !== "base") return; const p = hit(e); if (!p) { cursor.visible = false; return; }
    cursor.visible = true; cursor.position.copy(p); cursor.scale.setScalar(bw()); if (!down) return;
    const l = root.worldToLocal(p.clone()), r = bl();
    if (erase) strokes = strokes.filter((s) => Math.hypot(s[0] - l.x, s[1] - l.y, s[2] - l.z) > r);
    else if (!strokes.some((s) => Math.hypot(s[0] - l.x, s[1] - l.y, s[2] - l.z) < r * 0.35 && Math.abs(s[3] - r) < 1e-9) && strokes.length < 1500) strokes.push([l.x, l.y, l.z, r]);
    upd();
  }
  const el = renderer.domElement;
  el.addEventListener("pointerdown", (e) => { if (e.button !== 0 || tool !== "model" || view !== "base") return; down = true; controls.enabled = false; el.setPointerCapture(e.pointerId); dab(e); }, true);
  el.addEventListener("pointermove", (e) => { const t = performance.now(); if (t - last < 30) return; last = t; dab(e); });
  el.addEventListener("pointerup", (e) => { down = false; controls.enabled = true; try { el.releasePointerCapture(e.pointerId); } catch {} });
  el.addEventListener("pointerleave", () => { cursor.visible = false; });
  controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };

  // ---- the picture's own mask (which pixels may be used): painted on a canvas laid over the viewport
  const mc = $("#rtmask"), mx = mc.getContext("2d");
  const sizeMask = () => { const r = mc.getBoundingClientRect(); mc.width = Math.max(1, Math.round(r.width)); mc.height = Math.max(1, Math.round(r.height)); drawMask(); };
  const drawMask = () => { mx.clearRect(0, 0, mc.width, mc.height); mx.fillStyle = "rgba(41,151,255,.45)"; mstrokes.forEach(([x, y, r]) => { mx.beginPath(); mx.arc(x * mc.width, y * mc.height, r * mc.width, 0, 7); mx.fill(); }); };
  new ResizeObserver(sizeMask).observe(mc);
  mc.addEventListener("pointerdown", (e) => { if (tool !== "mask") return; mc.setPointerCapture(e.pointerId); mc._d = true; mdab(e); });
  mc.addEventListener("pointermove", (e) => { if (mc._d) mdab(e); });
  mc.addEventListener("pointerup", () => { mc._d = false; });
  function mdab(e) { const r = mc.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height, rad = (+$("#rtsize").value / 100) * 0.6;
    if (erase) mstrokes = mstrokes.filter(([a, b, c]) => Math.hypot((a - x) * r.width, (b - y) * r.height) > rad * r.width); else mstrokes.push([x, y, rad]); drawMask(); }
  const maskDataURL = () => { if (!mstrokes.length || !refAspect) return null; const W = 768, H = Math.round(768 / refAspect), c = document.createElement("canvas"); c.width = W; c.height = H; const g = c.getContext("2d");
    g.fillStyle = "#000"; g.fillRect(0, 0, W, H); g.fillStyle = "#fff"; mstrokes.forEach(([x, y, r]) => { g.beginPath(); g.arc(x * W, y * H, r * W, 0, 7); g.fill(); }); return c.toDataURL("image/png"); };

  function setRef(url, aspect) { refUrl = url; const im = $("#rtref"); im.src = url; im.hidden = false; $("#rtopwrap").hidden = false; im.style.opacity = $("#rtop").value / 100; $("#rtmaskbtn").disabled = false; $("#rtclearmask").disabled = false; setAspect(aspect); }
  $("#rtop").oninput = (e) => { $("#rtref").style.opacity = e.target.value / 100; };
  $("#rtfile").onchange = async (e) => { const f = e.target.files[0]; if (!f) return; const url = await readFile(f), im = new Image(); im.onload = () => { refFile = url; refGen = null; mstrokes = []; setRef(url, im.naturalWidth / im.naturalHeight); check(); }; im.src = url; };

  host.querySelectorAll(".rt-views [data-az]").forEach((b) => (b.onclick = () => { const az = +b.dataset.az * Math.PI / 180, t = controls.target, d = camera.position.distanceTo(t) || 3;
    camera.position.set(t.x + Math.sin(az) * d, t.y, t.z + Math.cos(az) * d); controls.update(); }));
  $(".rp-bar").onclick = (e) => { const b = e.target.closest("button"); if (!b || b.disabled) return; const t = b.dataset.t;
    if (t === "erase") { erase = !erase; b.classList.toggle("on", erase); return; }
    if (t === "clear") { strokes = []; upd(); return; } if (t === "clearmask") { mstrokes = []; drawMask(); return; }
    tool = t; host.querySelectorAll('.rp-bar [data-t="model"],.rp-bar [data-t="mask"],.rp-bar [data-t="orbit"]').forEach((x) => x.classList.toggle("on", x === b));
    mc.style.pointerEvents = t === "mask" ? "auto" : "none"; $("#rthint").textContent = t === "model" ? "Brush the part to change on the model" : t === "mask" ? "Paint the pixels of the picture that may be used" : "Drag to orbit"; };
  const setSize = (v) => { const el = $("#rtsize"); el.value = Math.max(+el.min, Math.min(+el.max, v)); $("#rtsizeo").textContent = (+el.value).toFixed(+el.value < 10 ? 1 : 0) + "%"; cursor.scale.setScalar(bw()); };
  $("#rtsize").oninput = () => setSize(+$("#rtsize").value); setSize(3);
  const keySize = (e) => { if (e.target.closest && e.target.closest("input,textarea,select")) return; if (e.key === "[") setSize(+$("#rtsize").value * 0.85); else if (e.key === "]") setSize(+$("#rtsize").value * 1.18); };
  addEventListener("keydown", keySize); const onWheel = (e) => { if (!e.altKey) return; e.preventDefault(); e.stopPropagation(); setSize(+$("#rtsize").value * (e.deltaY < 0 ? 1.12 : 0.89)); };
  renderer.domElement.addEventListener("wheel", onWheel, { passive: false, capture: true }); mc.addEventListener("wheel", onWheel, { passive: false, capture: true });
  const segBtns = () => host.querySelectorAll("[data-src]");
  segBtns().forEach((b) => (b.onclick = () => { src = b.dataset.src; segBtns().forEach((x) => x.classList.toggle("on", x === b)); $("#rtsrc_gen").hidden = src !== "gen"; $("#rtsrc_ref").hidden = src !== "ref"; check(); }));

  // ---- jobs
  async function post(body) { const r = await fetch("/api/retex", { method: "POST", body: JSON.stringify({ run: d.name, ...body }) }); const j = await r.json(); if (!r.ok) throw new Error(j.error || "Could not start."); return j; }
  $("#rtgen").onclick = async () => { const b = $("#rtgen"), m = $("#rtgenmsg"); b.disabled = true; m.textContent = "Starting…";
    try { await post({ mode: "generate", camera: camJSON(), notes: $("#rtnotes").value.trim() }); m.textContent = ""; poll(); } catch (e) { m.textContent = e.message; } finally { b.disabled = false; } };
  $("#rtapply").onclick = async () => { const b = $("#rtapply"), m = $("#rtmsg"); b.disabled = true; m.textContent = "Starting…";
    try { const body = { mode: "project", strokes, mask: maskDataURL() };
      if (src === "ref" && refFile) { body.camera = camJSON(); body.ref = refFile; } else if (refGen) { body.camera = refGen.camera; body.ref_job = refGen.job; body.ref_name = refGen.name; } else throw new Error("Choose or generate a picture first.");
      await post(body); m.textContent = ""; poll(); } catch (e) { m.textContent = e.message; } finally { check(); } };

  async function poll() {
    if (disposed) return; let I = null; try { I = await (await fetch("/api/retex/" + encodeURIComponent(d.name), { cache: "no-store" })).json(); } catch {}
    if (I) { info = I; render(I.jobs || []); } clearTimeout(timer); if (!disposed && (info.jobs || []).some((j) => ["queued", "running"].includes(j.status))) timer = setTimeout(poll, 2500);
  }
  function render(jobs) {
    const gen = jobs.filter((j) => j.mode === "generate" && j.generated && j.generated.length)[0];
    $("#rtgenerated").innerHTML = gen ? `<div class="hint" style="margin-top:12px">Generated views, pick one (the viewer snaps back to the camera it was made from):</div><div class="rp-imgs">${gen.generated.map((g, i) =>
      `<figure class="${refGen && refGen.job === gen.job && refGen.name === g.name ? "pick" : ""}"><img src="${esc(g.url)}" data-gen="${esc(gen.job)}|${esc(g.name)}" alt=""><figcaption>${i === 0 ? "first take" : "second take"}</figcaption></figure>`).join("")}</div>` : "";
    $("#rtjobs").innerHTML = jobs.map((j) => `<div class="rp-job ${esc(j.status)}"><div class="rp-jh"><b>${esc(({ project: "Texture", generate: "Generate view", apply: "Keep" })[j.mode] || j.mode)}</b>
        <span class="pill ${j.status === "done" ? "finished" : j.status === "failed" ? "failed" : "running"}"><i></i>${esc(j.status)}</span><small>${esc(j.job.replace(/^(\d{4})(\d\d)(\d\d)_(\d\d)(\d\d)(\d\d)$/, "$3.$2. $4:$5"))}</small></div>
      ${j.notes ? `<div class="hint" style="margin:0 0 6px">${esc(j.notes)}</div>` : ""}${j.error ? `<div class="alertbar"><span>${esc(j.error)}</span></div>` : ""}
      ${j.before && j.after ? `<div class="rp-imgs"><figure><img src="${esc(j.before)}" alt=""><figcaption>before</figcaption></figure><figure class="after"><img src="${esc(j.after)}" alt=""><figcaption>after</figcaption></figure></div>` : ""}
      ${j.status === "running" || j.status === "queued" ? `<div class="rp-log">${(j.log || []).map((l) => `<div>${esc(l)}</div>`).join("")}</div>` : ""}
      ${j.mode === "project" && j.result ? `<div class="rp-act"><button class="btn btn-ghost btn-sm" data-view="${esc(j.result)}">View in 3D</button><button class="btn btn-ghost btn-sm" data-view="base">Back to the model</button>
        ${j.applied ? `<span class="hint">kept: on the rig and the clips</span>` : `<button class="btn btn-glow btn-sm" data-keep="${esc(j.job)}">Keep: put it on the rig and clips</button>`}</div>` : ""}</div>`).join("") || `<div class="hint" style="margin-top:14px">No retextures yet.</div>`;
  }
  $("#rtgenerated").onclick = (e) => { const g = e.target.closest("[data-gen]"); if (!g) return; const [job, name] = g.dataset.gen.split("|"), jj = (info.jobs || []).find((j) => j.job === job); if (!jj) return;
    refGen = { job, name, camera: jj.camera }; refFile = null; const im = new Image(); im.onload = () => { setRef(g.src, im.naturalWidth / im.naturalHeight); setCamera(jj.camera.elements); check(); render(info.jobs); }; im.src = g.src; };
  $("#rtjobs").onclick = async (e) => {
    const v = e.target.closest("[data-view]"); if (v) { view = v.dataset.view === "base" ? "base" : "result"; await show(v.dataset.view === "base" ? info.base : v.dataset.view); $("#rthint").textContent = view === "base" ? "Brush the part to change" : "The retextured model"; check(); return; }
    const k = e.target.closest("[data-keep]"); if (k) { k.disabled = true; try { await post({ mode: "apply", from_job: k.dataset.keep }); toast && toast("Putting the texture on the rig and clips…"); poll(); } catch (er) { toast && toast(er.message, true); k.disabled = false; } } };

  setAspect(null); await show(info.base); sizeMask(); render(info.jobs || []); if ((info.jobs || []).some((j) => ["queued", "running"].includes(j.status))) poll();
  return { dispose() { disposed = true; clearTimeout(timer); removeEventListener("keydown", keySize); try { viewer.dispose(); } catch {} } };

  function seg2() { return `<div class="seg" data-seg="rtsrc"><button type="button" class="on" data-src="gen">Describe it (generate)</button><button type="button" data-src="ref">Use a reference picture</button></div>`; }
}
