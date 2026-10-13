// three.js model viewer (a port of the classic static/viewer.js, same framing rules, so the Repair and Retexture brushes keep their coordinates):
// every model is scaled to 1.8 units tall and stands on y = 0; tools reach the scene, camera, controls and model root through internals().
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

export interface ViewerOptions { hero?: boolean; onProgress?: (fraction: number) => void; onInfo?: (info: { tris: number; skinned: boolean; bones: number }) => void }
export interface ViewerSettings { wire?: boolean; clay?: boolean; bones?: boolean; rotate?: boolean; play?: boolean; speed?: number; grid?: boolean }
export interface LoadResult { skinned: boolean; clips: { name: string; seconds: number }[] }

const gridVert = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position,1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const gridFrag = `varying vec3 vW; uniform vec3 uColor; uniform float uFade;
  float line(float c, float w){ float d = abs(fract(c - 0.5) - 0.5) / fwidth(c); return 1.0 - min(d / w, 1.0); }
  void main(){
    float minor = max(line(vW.x * 4.0, 1.0), line(vW.z * 4.0, 1.0)) * 0.35;
    float major = max(line(vW.x, 1.2), line(vW.z, 1.2)) * 0.7;
    float r = length(vW.xz); float fade = 1.0 - smoothstep(0.4, uFade, r);
    float a = max(minor, major) * fade * 0.55;
    if (a < 0.01) discard;
    gl_FragColor = vec4(uColor, a);
  }`;

export class Viewer {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly camera: THREE.PerspectiveCamera;
  readonly controls: OrbitControls;
  private host: HTMLElement;
  private hero: boolean;
  private opts: ViewerOptions;
  private root: THREE.Object3D | null = null;
  private skel: THREE.SkeletonHelper | null = null;
  private mixer: THREE.AnimationMixer | null = null;
  private action: THREE.AnimationAction | null = null;
  private clock = new THREE.Clock();
  private originals = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>();
  private clayMat = new THREE.MeshStandardMaterial({ color: 0xd4d6dc, roughness: 0.55, metalness: 0 });
  private grid: THREE.Mesh;
  private ground: THREE.Mesh;
  private state = { wire: false, clay: false, bones: false };
  private raf = 0; private visible = true; private disposed = false;
  private ro: ResizeObserver; private io: IntersectionObserver;
  private onPointer?: (e: PointerEvent) => void;

  constructor(host: HTMLElement, opts: ViewerOptions = {}) {
    this.host = host; this.hero = !!opts.hero; this.opts = opts;
    const r = (this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance", preserveDrawingBuffer: true }));
    r.setPixelRatio(Math.min(devicePixelRatio, 2)); r.outputColorSpace = THREE.SRGBColorSpace; r.toneMapping = THREE.ACESFilmicToneMapping; r.toneMappingExposure = 1.05;
    r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFShadowMap;
    r.domElement.style.display = "block"; r.domElement.style.width = "100%"; r.domElement.style.height = "100%"; r.domElement.style.touchAction = "none";
    host.appendChild(r.domElement);

    const pmrem = new THREE.PMREMGenerator(r);
    this.scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture; this.scene.environmentIntensity = 0.75;

    this.camera = new THREE.PerspectiveCamera(this.hero ? 26 : 32, 1, 0.01, 100);
    const c = (this.controls = new OrbitControls(this.camera, r.domElement));
    c.enableDamping = true; c.dampingFactor = 0.06; c.autoRotate = true; c.autoRotateSpeed = this.hero ? 1.1 : 0.8;
    c.enablePan = !this.hero; c.enableZoom = !this.hero;
    if (this.hero) { c.minPolarAngle = Math.PI * 0.32; c.maxPolarAngle = Math.PI * 0.56; }

    const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(2.5, 4, 3); key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048); key.shadow.camera.near = 0.5; key.shadow.camera.far = 15;
    Object.assign(key.shadow.camera, { left: -2, right: 2, top: 3, bottom: -1 }); key.shadow.bias = -0.0004; key.shadow.radius = 6;
    const rim = new THREE.DirectionalLight(0xa79bff, 1.6); rim.position.set(-3, 2.5, -3);
    const fill = new THREE.HemisphereLight(0xffffff, 0x1c1a2b, 0.5);
    this.scene.add(key, rim, fill);

    this.ground = new THREE.Mesh(new THREE.CircleGeometry(1.4, 64), new THREE.ShadowMaterial({ opacity: this.hero ? 0.18 : 0.3 }));
    this.ground.rotation.x = -Math.PI / 2; this.ground.receiveShadow = true; this.scene.add(this.ground);
    this.grid = new THREE.Mesh(new THREE.PlaneGeometry(12, 12), new THREE.ShaderMaterial({
      vertexShader: gridVert, fragmentShader: gridFrag, transparent: true, depthWrite: false,
      uniforms: { uColor: { value: new THREE.Color(0x9a8cff) }, uFade: { value: 3.2 } },
    }));
    this.grid.rotation.x = -Math.PI / 2; this.grid.position.y = -0.001; this.grid.visible = !this.hero; this.grid.raycast = () => {};
    this.scene.add(this.grid);

    this.ro = new ResizeObserver(() => this.resize()); this.ro.observe(host); this.resize();
    this.io = new IntersectionObserver(([e]) => { this.visible = e.isIntersecting; }, { threshold: 0.01 }); this.io.observe(host);
    if (this.hero) {
      this.onPointer = (e) => { const b = host.getBoundingClientRect(); key.position.x = 2.5 + ((e.clientX - b.left) / b.width - 0.5) * 3; };
      host.addEventListener("pointermove", this.onPointer);
    }
    this.loop();
  }

  private resize() {
    const w = this.host.clientWidth, h = this.host.clientHeight; if (!w || !h) return;
    this.renderer.setSize(w, h, false); this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
  }

  private frame(obj: THREE.Object3D) {
    const box = new THREE.Box3().setFromObject(obj), size = box.getSize(new THREE.Vector3()), c = box.getCenter(new THREE.Vector3());
    const s = 1.8 / Math.max(size.y, size.x * 0.8, size.z * 0.8, 1e-6);
    obj.scale.setScalar(s); obj.position.set(-c.x * s, -box.min.y * s, -c.z * s);
    const h = size.y * s, dist = (h * (this.hero ? 0.62 : 0.74)) / Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2));
    this.controls.target.set(0, h * (this.hero ? 0.5 : 0.46), 0);
    this.camera.position.set(dist * 0.35, h * (this.hero ? 0.62 : 0.6), dist * 0.94);
    this.controls.minDistance = dist * 0.25; this.controls.maxDistance = dist * 3; this.controls.update();
  }

  private applyMaterials() {
    if (!this.root) return;
    this.root.traverse((o) => {
      const m = o as THREE.Mesh; if (!m.isMesh || m.userData.tool) return;
      if (!this.originals.has(m)) this.originals.set(m, m.material);
      m.material = this.state.clay ? this.clayMat : this.originals.get(m)!;
      (Array.isArray(m.material) ? m.material : [m.material]).forEach((x) => { (x as THREE.MeshStandardMaterial).wireframe = this.state.wire; });
    });
    if (this.skel) this.skel.visible = this.state.bones;
  }

  async load(url: string): Promise<LoadResult | undefined> {
    if (this.mixer) { this.mixer.stopAllAction(); this.mixer = null; this.action = null; }
    if (this.root) { this.scene.remove(this.root); this.root.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) m.geometry.dispose(); }); this.root = null; this.originals.clear(); }
    if (this.skel) { this.scene.remove(this.skel); this.skel = null; }
    const gltf = await new GLTFLoader().loadAsync(url, (e) => { if (this.opts.onProgress && e.total) this.opts.onProgress(e.loaded / e.total); });
    if (this.disposed) return;
    const root = (this.root = gltf.scene); let tris = 0, skinned = false;
    root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.castShadow = true; m.receiveShadow = false; m.frustumCulled = false;
        tris += (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3;
        (Array.isArray(m.material) ? m.material : [m.material]).forEach((x) => {
          const s = x as THREE.MeshStandardMaterial; if (s.map) s.map.anisotropy = 8; s.side = THREE.FrontSide;
          if ("roughness" in s) { s.roughness = Math.max(s.roughness, 0.62); s.metalness = Math.min(s.metalness, 0.05); }      // generated PBR maps read as wet plastic otherwise
        });
      }
      if ((o as THREE.SkinnedMesh).isSkinnedMesh) skinned = true;
    });
    this.scene.add(root); this.frame(root);
    if (gltf.animations?.length) {      // an animated file plays its first clip in a loop (a turntable would fight the motion)
      this.mixer = new THREE.AnimationMixer(root); this.action = this.mixer.clipAction(gltf.animations[0]); this.action.play(); this.controls.autoRotate = false;
    }
    if (skinned) { this.skel = new THREE.SkeletonHelper(root); this.skel.visible = this.state.bones; this.scene.add(this.skel); }
    this.applyMaterials();
    this.opts.onInfo?.({ tris: Math.round(tris), skinned, bones: skinned && this.skel ? this.skel.bones.length : 0 });
    return { skinned, clips: gltf.animations.map((c) => ({ name: c.name, seconds: c.duration })) };
  }

  private loop = () => {
    this.raf = requestAnimationFrame(this.loop);
    if (!this.visible || document.hidden) { this.clock.getDelta(); return; }
    const dt = this.clock.getDelta(); this.mixer?.update(dt);
    this.controls.update(); this.renderer.render(this.scene, this.camera);
  };

  set(o: ViewerSettings) {
    if (o.wire !== undefined) this.state.wire = o.wire;
    if (o.clay !== undefined) this.state.clay = o.clay;
    if (o.bones !== undefined) this.state.bones = o.bones;
    if (o.rotate !== undefined) this.controls.autoRotate = o.rotate;
    if (o.play !== undefined && this.action) this.action.paused = !o.play;
    if (o.speed !== undefined && this.mixer) this.mixer.timeScale = o.speed;
    if (o.grid !== undefined) this.grid.visible = o.grid;
    this.applyMaterials();
  }

  /** Clip time (0..1) for a scrubber; seek(f) moves the clip there. */
  clipTime() { return this.action ? (this.action.time % this.action.getClip().duration) / this.action.getClip().duration : 0; }
  seek(f: number) { if (this.action && this.mixer) { this.action.time = f * this.action.getClip().duration; this.mixer.update(0); } }

  /** Orbit to an azimuth in degrees (0 = front, 90 = the model's right side), keeping the distance. */
  view(azDeg: number, elevation = 0.12) {
    const t = this.controls.target, d = this.camera.position.distanceTo(t) || 3, az = (azDeg * Math.PI) / 180;
    this.camera.position.set(t.x + Math.sin(az) * d * Math.cos(elevation), t.y + Math.sin(elevation) * d, t.z + Math.cos(az) * d * Math.cos(elevation));
    this.controls.update();
  }

  screenshot(): string { this.renderer.render(this.scene, this.camera); return this.renderer.domElement.toDataURL("image/png"); }

  internals() { return { scene: this.scene, camera: this.camera, controls: this.controls, renderer: this.renderer, root: () => this.root }; }

  reset() { if (this.root) { this.root.scale.setScalar(1); this.root.position.set(0, 0, 0); this.frame(this.root); } }

  dispose() {
    this.disposed = true; cancelAnimationFrame(this.raf); this.ro.disconnect(); this.io.disconnect(); this.controls.dispose();
    if (this.onPointer) this.host.removeEventListener("pointermove", this.onPointer);
    this.scene.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) m.geometry.dispose(); });
    this.renderer.dispose(); this.renderer.forceContextLoss(); this.renderer.domElement.remove();
  }
}
