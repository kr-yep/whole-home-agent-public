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
    kind: "sprite",
    image: "/characters/nailong/idle.png",
    note: "單張立繪 · 身體朝向滑鼠",
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

function spriteActor(definition) {
  const sprite = PIXI.Sprite.from(definition.image);
  sprite.anchor.set(0.5, 0.5);

  let scale = 1;
  let baseX = 0;
  let baseY = 0;
  let clock = 0;
  let mood = "idle";
  let moodAge = 0;
  let hop = 0;
  let lean = 0;
  let leanTarget = 0;

  const ease = (from, to, rate, dt) => from + (to - from) * Math.min(1, rate * dt);

  return {
    definition,
    display: sprite,
    attach(app) {
      app.stage.addChild(sprite);
    },
    detach(app) {
      app.stage.removeChild(sprite);
    },
    bounds() {
      const b = sprite.getBounds();
      return { left: b.left, top: b.top, right: b.right, bottom: b.bottom };
    },
    get naturalHeight() {
      // Sprite.from resolves the texture asynchronously; before it lands the
      // size is 1x1, and dividing by that would fling her off the canvas.
      const height = sprite.texture && sprite.texture.height;
      return height > 1 ? height : 0;
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
      // A flat image has no eyes to move on their own, so attention is the whole
      // body turning slightly towards the pointer. It is a weaker gesture than
      // Rem's, and it is the honest limit of a single drawing.
      leanTarget = Math.max(-0.2, Math.min(0.2, (x - baseX) / window.innerWidth));
    },
    async ready() {
      // A missing image is not an error PIXI reports: the texture stays 1x1 and
      // invalid, so she lays out to nothing and is simply absent. Say so instead,
      // because the art is deliberately outside version control and a fresh
      // clone will not have it.
      for (let i = 0; i < 40; i++) {
        if (sprite.texture && sprite.texture.valid && sprite.texture.height > 1) return true;
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
      const dt = Math.min(0.05, deltaMs / 1000);
      clock += dt;
      moodAge += dt;

      lean = ease(lean, leanTarget, 4, dt);
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
      sprite.scale.set(scaleX, scaleY);
      sprite.rotation = lean * 0.28 + (mood === "refuse" ? 0.05 : 0);

      // Keep her feet where they were: shrinking around a centred anchor would
      // otherwise lift her off the floor every time she breathes out.
      const settled = ((scale - scaleY) * this.naturalHeight) / 2;
      sprite.x = baseX + lean * 26;
      sprite.y = baseY + settled - hop * 52;
    },
    destroy() {
      sprite.destroy();
    },
  };
}

async function createActor(id) {
  const definition = CHARACTERS[id] || CHARACTERS[DEFAULT_CHARACTER_ID];
  if (definition.kind === "sprite") return spriteActor(definition);
  return live2dActor(definition);
}
