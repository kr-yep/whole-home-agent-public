/* Who can stand on the canvas, and how each one is animated.

   Two kinds, because the two characters arrived in different shapes. Rem is a
   Cubism 4 model with a rig, physics and separable eyes. Nailong is one flat
   image, so everything she does here is arithmetic on a sprite.

   Both expose the same handful of methods, so the page's layout, drag, wheel and
   bubble code never asks which kind it is holding. */

const CHARACTERS = {
  rem: {
    id: "rem",
    name: "雷姆",
    kind: "live2d",
    model: "/live2d/rem/REM.model3.json",
    note: "Live2D · 眼球跟隨滑鼠",
  },
  nailong: {
    id: "nailong",
    name: "奶龍",
    kind: "gltf",
    model: "/characters/nailong/model.glb",
    // Rigify's spine chain runs waist to head. Note the missing dots: the glTF
    // importer strips them from bone names, so the file says "DEF-spine.006"
    // and the scene says "DEF-spine006". Looking up the file's spelling finds
    // nothing, silently, and the head simply never turns.
    headBone: "DEF-spine006_30_15",
    neckBone: "DEF-spine005_31_14",
    note: "3D 模型 · 轉動頭骨",
    credit: "Nailong by okstepanova2012 (Sketchfab, CC Attribution)",
  },
  nailongFlat: {
    id: "nailongFlat",
    name: "奶龍（平面）",
    speaksAs: "奶龍",
    kind: "sprite",
    image: "/characters/nailong/idle.png",
    note: "單張立繪 · 網格變形",
  },
};

const DEFAULT_CHARACTER_ID = "rem";

/* ---------- Live2D ---------- */

async function live2dActor(definition) {
  // The browser bundle does not wire itself to a ticker. Without this the model
  // renders but never updates: focus targets are set and nothing interpolates
  // toward them, so the eyes stay dead ahead.
  PIXI.live2d.Live2DModel.registerTicker(PIXI.Ticker);

  const model = await PIXI.live2d.Live2DModel.from(definition.model, {
    autoInteract: false,
  });
  model.anchor.set(0.5, 0.5);
  // The plugin's own updating is driven from the page's ticker instead, so a
  // bundle that reports autoUpdate true while never attaching cannot leave the
  // model unable to blink, breathe or follow anything.
  model.autoUpdate = false;

  // Cubism draws every clipped part -- hair over the face, layered clothing --
  // into one mask buffer and samples it back. The SDK default is 256x256, so
  // those edges were being magnified roughly three times before they reached
  // the screen; they were the most visible jaggies of the three causes.
  const renderer = model.internalModel.renderer;
  if (renderer && typeof renderer.setClippingMaskBufferSize === "function") {
    renderer.setClippingMaskBufferSize(2048);
  }

  // This model files all 96 motions under one unnamed group, so a motion cannot
  // be asked for by group the way the sample model allowed. Index them by
  // filename once, then play by name.
  const motions = {};
  const groups = (model.internalModel.settings || {}).motions || {};
  for (const [group, entries] of Object.entries(groups)) {
    (entries || []).forEach((entry, index) => {
      const stem = String(entry.File || "").split("/").pop().replace(".motion3.json", "");
      if (stem && !(stem in motions)) motions[stem] = [group, index];
    });
  }

  // Every motion in this model is marked Loop, so none of them ever end. Two
  // consequences, both measured against the model rather than assumed:
  //
  //   IDLE   succeeds once, then never again -- it is refused while anything plays
  //   NORMAL succeeds once, then never again -- priority never falls back
  //   FORCE  succeeds every time
  //
  // So everything plays at FORCE, and the idle rotation runs on a timer instead
  // of waiting for a motion to finish, because waiting would wait forever.
  function playFirst(candidates) {
    const usable = candidates.filter((name) => name in motions);
    if (!usable.length) return;
    const [group, index] = motions[usable[0]];
    try {
      model.motion(group, index, PIXI.live2d.MotionPriority.FORCE);
    } catch (_) { /* not loadable */ }
  }

  // Calm families only. The model also carries angry, startled and suffering
  // sets; they are good motions, but they would read as noise from something
  // whose whole job is to wait quietly until you ask where your keys are.
  const IDLE_FAMILIES = [
    "act_normal", "act_hohoemu", "act_egao",
    "face_normal", "face_hohoemu", "face_egao",
  ];

  function idlePool() {
    const all = Object.keys(motions).filter((name) =>
      IDLE_FAMILIES.some((family) => name.startsWith(family))
    );
    // The "_w" variants are the ones drawn to be held rather than performed once.
    const held = all.filter((name) => name.endsWith("_w"));
    return held.length ? held : all;
  }

  return {
    definition,
    display: model,
    naturalHeight: model.internalModel.originalHeight,
    attach(app) {
      app.stage.addChild(model);
    },
    detach(app) {
      app.stage.removeChild(model);
    },
    bounds() {
      const b = model.getBounds();
      return { left: b.left, top: b.top, right: b.right, bottom: b.bottom };
    },
    setScale(value) {
      model.scale.set(value);
    },
    setPosition(x, y) {
      model.x = x;
      model.y = y;
    },
    position() {
      return { x: model.x, y: model.y };
    },
    focus(x, y) {
      model.focus(x, y);
    },
    express(kind) {
      // Names are the model's own: unazuku nods, nayamu is troubled, komaru is
      // at a loss, kangaeru thinks.
      if (kind === "refuse") playFirst(["act_nayamu", "face_komaru", "act_tameiki"]);
      else if (kind === "thinking") playFirst(["act_kangaeru", "act_shinken"]);
      else if (kind === "answer") playFirst(["act_unazuku", "act_egao", "act_hohoemu"]);
      else {
        const pool = idlePool();
        if (pool.length) playFirst([pool[Math.floor(Math.random() * pool.length)]]);
      }
    },
    async ready() {
      return true;
    },
    update(deltaMs) {
      model.update(deltaMs);
    },
    destroy() {
      model.destroy();
    },
  };
}

/* ---------- one flat image ---------- */

// Measured from the silhouette of this drawing: the head holds a roughly constant
// width down to 16% of the image, the shoulders open out between there and 28%,
// and below that is body. So displacement is full over the head, fades across the
// shoulders, and is nothing below them -- which is what makes a turn read as a
// head turning rather than the whole picture sliding sideways.
const HEAD_BOTTOM = 0.16;
const SHOULDER_BOTTOM = 0.32;
const GRID_X = 14;
const GRID_Y = 18;

function headWeight(v) {
  if (v <= HEAD_BOTTOM) return 1;
  if (v >= SHOULDER_BOTTOM) return 0;
  const t = (v - HEAD_BOTTOM) / (SHOULDER_BOTTOM - HEAD_BOTTOM);
  return 1 - t * t * (3 - 2 * t); // smoothstep, so the neck does not crease
}

function spriteActor(definition) {
  // A plane rather than a sprite, because a flat drawing can still turn its head
  // if the drawing itself is allowed to bend. The vertices carry the turn; the
  // mesh transform carries breathing, hopping and the sink of a refusal.
  const texture = PIXI.Texture.from(definition.image);
  const mesh = new PIXI.SimplePlane(texture, GRID_X, GRID_Y);
  const buffer = mesh.geometry.getBuffer("aVertexPosition");

  let rest = null;
  let scale = 1;
  let baseX = 0;
  let baseY = 0;
  let clock = 0;
  let mood = "idle";
  let moodAge = 0;
  let hop = 0;
  let yaw = 0;
  let yawTarget = 0;
  let pitch = 0;
  let pitchTarget = 0;

  const ease = (from, to, rate, dt) => from + (to - from) * Math.min(1, rate * dt);

  function capture() {
    if (rest || !texture.valid) return;
    mesh.pivot.set(texture.width / 2, texture.height / 2);
    rest = Float32Array.from(buffer.data);
  }

  function warp() {
    if (!rest) return;
    const data = buffer.data;
    const width = texture.width;
    const height = texture.height;
    const headCentre = width / 2;
    for (let i = 0; i < rest.length; i += 2) {
      const x = rest[i];
      const y = rest[i + 1];
      const weight = headWeight(y / height);
      if (weight === 0) {
        data[i] = x;
        data[i + 1] = y;
        continue;
      }
      // Sideways travel, plus a squeeze towards the middle: a head turning away
      // gets narrower, and without that the turn reads as a slide.
      // 0.05 of the width. The first value here was picked from a render 272px
      // tall and it was three times too much: she is drawn about 900px tall on
      // the page, and the same proportion that looks like a turn in a thumbnail
      // is a stretched neck at full size. Judged again at 1:1, 0.07 begins to
      // straighten the neck on the far side and 0.10 pulls the head off it.
      const squeeze = 1 - Math.abs(yaw) * 0.06 * weight;
      data[i] = headCentre + (x - headCentre) * squeeze + yaw * width * 0.05 * weight;
      // A turn drops the head slightly, and a nod uses the same channel.
      data[i + 1] = y + (Math.abs(yaw) * 0.012 + pitch * 0.03) * height * weight;
    }
    buffer.update();
  }

  return {
    definition,
    display: mesh,
    attach(app) {
      app.stage.addChild(mesh);
    },
    detach(app) {
      app.stage.removeChild(mesh);
    },
    bounds() {
      const b = mesh.getBounds();
      return { left: b.left, top: b.top, right: b.right, bottom: b.bottom };
    },
    get naturalHeight() {
      // Texture.from resolves asynchronously; before it lands the size is 1x1,
      // and dividing by that would fling her off the canvas.
      return texture.valid && texture.height > 1 ? texture.height : 0;
    },
    setScale(value) {
      scale = value;
    },
    setPosition(x, y) {
      baseX = x;
      baseY = y;
    },
    position() {
      return { x: baseX, y: baseY };
    },
    focus(x, y) {
      // A page that mounts in a background tab reports a viewport of zero, and
      // the obvious division is then 0/0. NaN survives every later frame through
      // the easing, every vertex it touches stops being a number, and the head
      // simply never comes back. Ask for a size before dividing by one.
      const width = window.innerWidth;
      const height = window.innerHeight;
      if (!width || !height) return;
      // Where the head points, not where the whole body leans. The range is
      // deliberately short of the full screen: a head that swings to the very
      // edge looks unhinged rather than attentive.
      yawTarget = Math.max(-1, Math.min(1, ((x - baseX) / width) * 3.2));
      pitchTarget = Math.max(-1, Math.min(1, ((y - baseY) / height) * 2.4));
    },
    async ready() {
      // A missing image is not an error PIXI reports: the texture stays 1x1 and
      // invalid, so she lays out to nothing and is simply absent. Say so instead,
      // because the art is deliberately outside version control and a fresh
      // clone will not have it.
      for (let i = 0; i < 40; i++) {
        if (texture.valid && texture.height > 1) {
          capture();
          return true;
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      return false;
    },
    express(kind) {
      mood = kind;
      moodAge = 0;
      if (kind === "answer") hop = 1;
    },
    update(deltaMs) {
      capture();
      const dt = Math.min(0.05, deltaMs / 1000);
      clock += dt;
      moodAge += dt;

      // Slower than the pointer on purpose: a head that snaps to the cursor
      // frame for frame looks mechanical, and the lag is most of what reads as
      // "she noticed and turned".
      yaw = ease(yaw, yawTarget, 3.4, dt);
      pitch = ease(pitch, pitchTarget, 3, dt);
      // Belt and braces after the above: one non-finite frame from anywhere
      // would otherwise be permanent, because it feeds back through the easing.
      if (!Number.isFinite(yaw)) yaw = yawTarget = 0;
      if (!Number.isFinite(pitch)) pitch = pitchTarget = 0;
      hop *= Math.exp(-dt * 4.5);
      if (mood !== "idle" && moodAge > 6) mood = "idle";

      // Breathing is one sine used twice with opposite sign, so she widens as
      // she flattens and keeps her area roughly constant. Anything else reads as
      // the picture being resized.
      const breath = Math.sin(clock * 1.5) * 0.012;
      const fidget = mood === "thinking" ? Math.sin(clock * 7) * 0.010 : 0;
      const sink = mood === "refuse" ? Math.min(1, moodAge * 1.5) * 0.045 : 0;

      const scaleX = scale * (1 - breath + fidget);
      const scaleY = scale * (1 + breath - sink);
      mesh.scale.set(scaleX, scaleY);
      // The body does not follow the head at all. It did, by a couple of degrees,
      // and rotating the whole figure moves the head again in the direction it
      // has already travelled -- the two compounded into the broken-neck look
      // that the warp on its own does not have.
      mesh.rotation = mood === "refuse" ? 0.05 : 0;

      // Keep her feet where they were: shrinking around a centred pivot would
      // otherwise lift her off the floor every time she breathes out.
      const settled = ((scale - scaleY) * this.naturalHeight) / 2;
      mesh.x = baseX;
      mesh.y = baseY + settled - hop * 52;

      warp();
    },
    destroy() {
      mesh.destroy();
    },
  };
}

async function createActor(id) {
  const definition = CHARACTERS[id] || CHARACTERS[DEFAULT_CHARACTER_ID];
  if (definition.kind === "sprite") return spriteActor(definition);
  if (definition.kind === "gltf") return gltfActor(definition);
  return live2dActor(definition);
}

/* ---------- a rigged 3D model ---------- */

// three.js cannot draw into PIXI's canvas, so this actor brings its own and
// shows it only while it is on stage. An orthographic camera sized in pixels
// keeps the arithmetic the same as the other two: one world unit of the model
// becomes whatever setScale was handed, and screen positions stay screen
// positions.
async function gltfActor(definition) {
  const canvas = document.createElement("canvas");
  canvas.className = "stage3d";

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.outputEncoding = THREE.sRGBEncoding;

  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -5000, 5000);

  // Flat-ish lighting: the model is a soft toy and a hard key light turns its
  // belly into a spotlight. One fill from the front, one from above.
  scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.15));
  const key = new THREE.DirectionalLight(0xffffff, 0.85);
  key.position.set(0.4, 1, 1.2);
  scene.add(key);

  const gltf = await new Promise((resolve, reject) => {
    new THREE.GLTFLoader().load(definition.model, resolve, undefined, reject);
  });

  const root = gltf.scene;
  const pivot = new THREE.Group();
  pivot.add(root);
  scene.add(pivot);

  // Sit the model on its own feet and centre it, so setPosition means the same
  // thing here as it does for a sprite with a centred anchor.
  const box = new THREE.Box3().setFromObject(root);
  const size = new THREE.Vector3();
  const centre = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(centre);
  root.position.sub(centre);

  const bones = {};
  root.traverse((node) => {
    if (node.isBone) bones[node.name] = node;
  });
  const head = bones[definition.headBone] || null;
  const neck = bones[definition.neckBone] || null;
  const headRest = head ? head.rotation.clone() : null;
  const neckRest = neck ? neck.rotation.clone() : null;

  let scale = 1;
  let baseX = 0;
  let baseY = 0;
  let clock = 0;
  let mood = "idle";
  let moodAge = 0;
  let hop = 0;
  let yaw = 0;
  let yawTarget = 0;
  let pitch = 0;
  let pitchTarget = 0;

  const ease = (from, to, rate, dt) => from + (to - from) * Math.min(1, rate * dt);

  function resize() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.left = -width / 2;
    camera.right = width / 2;
    camera.top = height / 2;
    camera.bottom = -height / 2;
    camera.updateProjectionMatrix();
  }

  return {
    definition,
    naturalHeight: size.y,
    attach() {
      document.body.insertBefore(canvas, document.body.firstChild);
      resize();
      window.addEventListener("resize", resize);
    },
    detach() {
      window.removeEventListener("resize", resize);
      canvas.remove();
    },
    setScale(value) {
      scale = value;
    },
    setPosition(x, y) {
      baseX = x;
      baseY = y;
    },
    position() {
      return { x: baseX, y: baseY };
    },
    bounds() {
      const w = size.x * scale;
      const h = size.y * scale;
      return {
        left: baseX - w / 2, right: baseX + w / 2,
        top: baseY - h / 2, bottom: baseY + h / 2,
      };
    },
    focus(x, y) {
      // A viewport of zero is what a background tab reports, and dividing by it
      // gives NaN that never washes out of the easing.
      const width = window.innerWidth;
      const height = window.innerHeight;
      if (!width || !height) return;
      yawTarget = Math.max(-1, Math.min(1, ((x - baseX) / width) * 3.2));
      pitchTarget = Math.max(-1, Math.min(1, ((y - baseY) / height) * 2.4));
    },
    async ready() {
      return true;
    },
    express(kind) {
      mood = kind;
      moodAge = 0;
      if (kind === "answer") hop = 1;
    },
    update(deltaMs) {
      const dt = Math.min(0.05, deltaMs / 1000);
      clock += dt;
      moodAge += dt;
      yaw = ease(yaw, yawTarget, 3.4, dt);
      pitch = ease(pitch, pitchTarget, 3, dt);
      if (!Number.isFinite(yaw)) yaw = yawTarget = 0;
      if (!Number.isFinite(pitch)) pitch = pitchTarget = 0;
      hop *= Math.exp(-dt * 4.5);
      if (mood !== "idle" && moodAge > 6) mood = "idle";

      // Rotating a bone is a real rotation, so this can be generous where the
      // flat version had to be timid: nothing is being stretched.
      if (head && headRest) {
        head.rotation.set(
          headRest.x + pitch * 0.28 + (mood === "refuse" ? 0.22 : 0),
          headRest.y - yaw * 0.55,
          headRest.z
        );
      }
      if (neck && neckRest) {
        neck.rotation.set(neckRest.x + pitch * 0.10, neckRest.y - yaw * 0.22, neckRest.z);
      }

      const breath = Math.sin(clock * 1.5) * 0.012;
      const sink = mood === "refuse" ? Math.min(1, moodAge * 1.5) * 0.04 : 0;
      pivot.scale.set(scale * (1 - breath), scale * (1 + breath - sink), scale);

      const height = window.innerHeight || 0;
      pivot.position.set(
        baseX - window.innerWidth / 2,
        height / 2 - baseY + hop * 52 + ((size.y * scale) * (breath - sink)) / 2,
        0
      );
      renderer.render(scene, camera);
    },
    destroy() {
      canvas.remove();
      renderer.dispose();
    },
  };
}
