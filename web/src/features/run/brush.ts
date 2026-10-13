// Brush painting on a model in the Viewer, shared by Repair and Retexture (a port of the classic repair.js / retex.js mechanics).
// Dabs are spheres [x, y, z, r] in the model ROOT's local (glTF) coordinates: the viewer scales models to 1.8 units tall, so r = size% * 1.8 / root.scale.x.
import * as THREE from "three";
import { computeBoundsTree, disposeBoundsTree, acceleratedRaycast } from "three-mesh-bvh";
import type { Viewer } from "@/viewer/Viewer";

(THREE.BufferGeometry.prototype as any).computeBoundsTree = computeBoundsTree;
(THREE.BufferGeometry.prototype as any).disposeBoundsTree = disposeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;

export type Dab = [number, number, number, number];
export const MAX_DABS = 1500;

export class Brush {
  private v: Viewer; private root: THREE.Object3D | null = null; private inst: THREE.InstancedMesh | null = null; private cursor: THREE.Mesh;
  private ray = new THREE.Raycaster(); private ptr = new THREE.Vector2(); private down = false; private last = 0;
  size = 3;                      // % of the model's height
  erase = false; enabled = true;
  strokes: Dab[] = []; extra: Dab[] = [];      // extra: kept parts, drawn but not edited
  onChange?: () => void;
  private el: HTMLCanvasElement; private color: number;
  private handlers: [string, any, any?][] = [];

  constructor(v: Viewer, color = 0xff375f) {
    this.v = v; this.color = color; this.el = v.renderer.domElement;
    this.cursor = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 14), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.28, depthWrite: false }));
    this.cursor.visible = false; this.cursor.userData.tool = true; v.scene.add(this.cursor);
    const { controls } = v.internals();
    controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };
    const on = (t: string, f: any, o?: any) => { this.el.addEventListener(t, f, o); this.handlers.push([t, f, o]); };
    on("pointerdown", (e: PointerEvent) => { if (e.button !== 0 || !this.enabled) return; this.down = true; controls.enabled = false; this.el.setPointerCapture(e.pointerId); this.dab(e); }, true);   // capture: before OrbitControls
    on("pointermove", (e: PointerEvent) => { const t = performance.now(); if (t - this.last < 30) return; this.last = t; this.dab(e); });
    on("pointerup", (e: PointerEvent) => { this.down = false; controls.enabled = true; try { this.el.releasePointerCapture(e.pointerId); } catch { /* not captured */ } });
    on("pointerleave", () => { this.cursor.visible = false; });
    on("wheel", (e: WheelEvent) => { if (!e.altKey) return; e.preventDefault(); e.stopPropagation(); this.setSize(this.size * (e.deltaY < 0 ? 1.12 : 0.89)); }, { passive: false, capture: true });
  }

  /** Call after the viewer loaded a model. */
  attach() {
    const root = (this.root = this.v.internals().root());
    if (!root) return;
    root.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh && !(m.geometry as any).boundsTree) (m.geometry as any).computeBoundsTree(); });
    if (this.inst) { this.inst.parent?.remove(this.inst); this.inst.dispose(); }
    const inst = (this.inst = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 10, 8), new THREE.MeshBasicMaterial({ color: this.color, transparent: true, opacity: 0.5, depthWrite: false }), MAX_DABS));
    inst.count = 0; inst.frustumCulled = false; inst.raycast = () => {}; inst.userData.tool = true; root.add(inst);
    this.strokes = []; this.redraw();
  }

  setSize(v: number) { this.size = Math.max(0.3, Math.min(25, v)); this.cursor.scale.setScalar(this.world()); this.onChange?.(); }
  world() { return (this.size / 100) * 1.8; }
  local() { return this.world() / (this.root ? this.root.scale.x : 1); }

  redraw() {
    if (!this.inst) return;
    const m = new THREE.Matrix4(), all = [...this.extra, ...this.strokes].slice(0, MAX_DABS);
    all.forEach((s, i) => { m.compose(new THREE.Vector3(s[0], s[1], s[2]), new THREE.Quaternion(), new THREE.Vector3(s[3], s[3], s[3])); this.inst!.setMatrixAt(i, m); });
    this.inst.count = all.length; this.inst.instanceMatrix.needsUpdate = true; this.onChange?.();
  }

  private hit(e: PointerEvent) {
    const r = this.el.getBoundingClientRect(); const { camera } = this.v.internals();
    this.ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    this.ray.setFromCamera(this.ptr, camera); (this.ray as any).firstHitOnly = true;
    const h = this.ray.intersectObject(this.root!, true).find((x) => (x.object as THREE.Mesh).isMesh && x.object !== this.inst); return h ? h.point : null;
  }

  private dab(e: PointerEvent) {
    if (!this.root || !this.enabled) { this.cursor.visible = false; return; }
    const p = this.hit(e); if (!p) { this.cursor.visible = false; return; }
    this.cursor.visible = true; this.cursor.position.copy(p); this.cursor.scale.setScalar(this.world());
    if (!this.down) return;
    const l = this.root.worldToLocal(p.clone()), r = this.local();
    if (this.erase) this.strokes = this.strokes.filter((s) => Math.hypot(s[0] - l.x, s[1] - l.y, s[2] - l.z) > r);
    else if (!this.strokes.some((s) => Math.hypot(s[0] - l.x, s[1] - l.y, s[2] - l.z) < r * 0.35 && Math.abs(s[3] - r) < 1e-9) && this.strokes.length < MAX_DABS) this.strokes.push([l.x, l.y, l.z, r]);
    this.redraw();
  }

  /** A named region of a T/A-posed figure as voxels of 2.2 % of the height (the same rules as the backend's presets). */
  region(name: "hands" | "head" | "crown" | "feet") {
    const root = this.root; if (!root) return 0;
    const pts: number[] = [], v = new THREE.Vector3(); let lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
    root.updateMatrixWorld(true);
    root.traverse((o) => {
      const m = o as THREE.Mesh; if (!m.isMesh || m === this.inst) return; const a = m.geometry.attributes.position;
      for (let i = 0; i < a.count; i++) {
        v.fromBufferAttribute(a, i).applyMatrix4(m.matrixWorld); root.worldToLocal(v); pts.push(v.x, v.y, v.z);
        lo = [Math.min(lo[0], v.x), Math.min(lo[1], v.y), Math.min(lo[2], v.z)]; hi = [Math.max(hi[0], v.x), Math.max(hi[1], v.y), Math.max(hi[2], v.z)];
      }
    });
    const height = hi[1] - lo[1], xc = (lo[0] + hi[0]) / 2, lim = (hi[0] - lo[0]) / 2 - 0.105 * height, cell = 0.022 * height, seen = new Map<string, Dab>();
    const inside = { hands: (x: number) => Math.abs(x - xc) > lim, head: (_x: number, y: number) => y > hi[1] - 0.135 * height, crown: (_x: number, y: number) => y > hi[1] - 0.07 * height, feet: (_x: number, y: number) => y < lo[1] + 0.05 * height }[name];
    for (let i = 0; i < pts.length; i += 3) if (inside(pts[i], pts[i + 1])) {
      const a = Math.floor(pts[i] / cell), b = Math.floor(pts[i + 1] / cell), c = Math.floor(pts[i + 2] / cell), k = `${a},${b},${c}`;
      if (!seen.has(k)) seen.set(k, [(a + 0.5) * cell, (b + 0.5) * cell, (c + 0.5) * cell, cell * 0.8]);
    }
    this.strokes = [...seen.values()].slice(0, MAX_DABS); this.redraw(); return this.strokes.length;
  }

  clear() { this.strokes = []; this.redraw(); }

  dispose() {
    this.handlers.forEach(([t, f, o]) => this.el.removeEventListener(t, f, o));
    this.cursor.parent?.remove(this.cursor); this.inst?.parent?.remove(this.inst); this.inst?.dispose();
  }
}
