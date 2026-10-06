// three.js model viewer: hero turntable on the home page and the inspect view on a run page.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

export function createViewer(host, { hero = false, onProgress, onInfo } = {}) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.75;

  const camera = new THREE.PerspectiveCamera(hero ? 26 : 32, 1, 0.01, 100);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.06;
  controls.autoRotate = true; controls.autoRotateSpeed = hero ? 1.1 : 0.8;
  controls.enablePan = !hero; controls.enableZoom = !hero;
  if (hero) { controls.minPolarAngle = Math.PI * 0.32; controls.maxPolarAngle = Math.PI * 0.56; }

  const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(2.5, 4, 3); key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048); key.shadow.camera.near = 0.5; key.shadow.camera.far = 15;
  Object.assign(key.shadow.camera, { left: -2, right: 2, top: 3, bottom: -1 }); key.shadow.bias = -0.0004; key.shadow.radius = 6;
  const rim = new THREE.DirectionalLight(0x9db8ff, 1.6); rim.position.set(-3, 2.5, -3);
  const fill = new THREE.HemisphereLight(0xffffff, 0x222233, 0.5);
  scene.add(key, rim, fill);
  const ground = new THREE.Mesh(new THREE.CircleGeometry(1.4, 64), new THREE.ShadowMaterial({ opacity: hero ? 0 : 0.28 }));
  ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);

  let root = null, skel = null, wire = false, clay = false, bones = false, raf = 0, visible = true, disposed = false;
  let mixer = null, action = null, clips = [];
  const clock = new THREE.Clock();
  const originals = new Map();
  const clayMat = new THREE.MeshStandardMaterial({ color: 0xd9d9de, roughness: 0.55, metalness: 0 });

  function resize() {
    const w = host.clientWidth, h = host.clientHeight; if (!w || !h) return;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize); ro.observe(host); resize();
  const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { threshold: 0.01 }); io.observe(host);

  function frame(obj) {
    const box = new THREE.Box3().setFromObject(obj), size = box.getSize(new THREE.Vector3()), c = box.getCenter(new THREE.Vector3());
    const s = 1.8 / Math.max(size.y, size.x * 0.8, size.z * 0.8, 1e-6);
    obj.scale.setScalar(s); obj.position.set(-c.x * s, -box.min.y * s, -c.z * s);
    const h = size.y * s, dist = (h * (hero ? 0.62 : 0.74)) / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    controls.target.set(0, h * (hero ? 0.5 : 0.44), 0);   // leave room under the feet for the toolbar
    camera.position.set(dist * 0.35, h * (hero ? 0.62 : 0.6), dist * 0.94);
    controls.minDistance = dist * 0.25; controls.maxDistance = dist * 3; controls.update();
  }

  function applyMaterials() {
    if (!root) return;
    root.traverse((o) => {
      if (!o.isMesh) return;
      if (!originals.has(o)) originals.set(o, o.material);
      o.material = clay ? clayMat : originals.get(o);
      (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => { m.wireframe = wire; });
    });
    if (skel) skel.visible = bones;
  }

  async function load(url) {
    if (mixer) { mixer.stopAllAction(); mixer = null; action = null; } clips = [];
    if (root) { scene.remove(root); root.traverse((o) => { if (o.isMesh) { o.geometry.dispose(); } }); root = null; originals.clear(); }
    if (skel) { scene.remove(skel); skel = null; }
    const gltf = await new GLTFLoader().loadAsync(url, (e) => onProgress && e.total && onProgress(e.loaded / e.total));
    if (disposed) return;
    root = gltf.scene; let tris = 0, hasSkin = false;
    root.traverse((o) => {
      if (o.isMesh) {
        o.castShadow = true; o.receiveShadow = false; o.frustumCulled = false;
        tris += (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3;
        (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => { if (m.map) m.map.anisotropy = 8; m.side = THREE.FrontSide;
          if ('roughness' in m) { m.roughness = Math.max(m.roughness, 0.62); m.metalness = Math.min(m.metalness, 0.05); } });   // generated PBR maps read as wet plastic otherwise
      }
      if (o.isSkinnedMesh) hasSkin = true;
    });
    scene.add(root); frame(root);
    if (gltf.animations && gltf.animations.length) {      // an animated file: play its first clip in a loop (the turntable would fight the motion)
      clips = gltf.animations; mixer = new THREE.AnimationMixer(root); action = mixer.clipAction(clips[0]); action.play(); controls.autoRotate = false;
    }
    if (hasSkin) { skel = new THREE.SkeletonHelper(root); skel.visible = bones; skel.material.linewidth = 2; scene.add(skel); }
    applyMaterials();
    onInfo && onInfo({ tris: Math.round(tris), skinned: hasSkin, bones: hasSkin ? skel.bones.length : 0 });
    return { skinned: hasSkin, clips: clips.map((c) => ({ name: c.name, seconds: c.duration })) };
  }

  function loop() {
    raf = requestAnimationFrame(loop);
    if (!visible || document.hidden) return;
    const dt = clock.getDelta(); if (mixer) mixer.update(dt);
    controls.update(); renderer.render(scene, camera);
  }
  loop();

  // a hero model reacts gently to the pointer on top of its turntable
  if (hero) {
    host.addEventListener("pointermove", (e) => {
      const r = host.getBoundingClientRect(); const x = (e.clientX - r.left) / r.width - 0.5;
      key.position.x = 2.5 + x * 3;
    });
  }

  return {
    load,
    set(opts) {
      if ("wire" in opts) wire = opts.wire; if ("clay" in opts) clay = opts.clay; if ("bones" in opts) bones = opts.bones;
      if ("rotate" in opts) controls.autoRotate = opts.rotate;
      if ("play" in opts && action) action.paused = !opts.play;
      if ("speed" in opts && mixer) mixer.timeScale = opts.speed;
      applyMaterials();
    },
    reset() { if (root) { root.scale.setScalar(1); root.position.set(0, 0, 0); frame(root); } },
    dispose() {
      disposed = true; cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); controls.dispose();
      scene.traverse((o) => { if (o.isMesh) { o.geometry.dispose(); } });
      renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
    },
  };
}
