/* Character front end. Everything factual comes from /api/ask; this file only
   decides how it looks and where she is looking. */

const MODEL_URL = "/live2d/rem/REM.model3.json";

const stage = document.getElementById("stage");
const panel = document.getElementById("panel");
const bubble = document.getElementById("bubble");
const log = document.getElementById("log");
const form = document.getElementById("ask");
const question = document.getElementById("question");
const send = document.getElementById("send");
const chips = document.getElementById("chips");

const LABELS = { key: "🔑 鑰匙", bag: "👜 包包", sofa: "🛋 沙發" };
const WORDS = { key: "鑰匙", bag: "包包", sofa: "沙發" };
const RELATION = { inside: "在…裡面", at_zone: "位於" };

const label = (id) => LABELS[id] || id;

/* ---------- Live2D ---------- */

let model = null;

const VIEW_KEY = "wha.character.view";
const DEFAULT_VIEW = { x: 0.74, y: 0.54, scale: 0.92 };

function readView() {
  try {
    const saved = JSON.parse(localStorage.getItem(VIEW_KEY) || "null");
    if (saved && ["x", "y", "scale"].every((k) => typeof saved[k] === "number")) {
      return saved;
    }
  } catch (_) { /* a corrupt entry is not worth a broken page */ }
  return { ...DEFAULT_VIEW };
}

let view = readView();

function saveView() {
  try { localStorage.setItem(VIEW_KEY, JSON.stringify(view)); } catch (_) { /* private mode */ }
}

const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

// The bubble sits in whatever gap is left between the panel and wherever she is
// standing now. Deriving it from her actual bounds is why this moved out of CSS:
// the stylesheet had to assume a position, and she is no longer at one.
function placeBubble() {
  if (!model) return;
  const bounds = model.getBounds();
  const left = panel.getBoundingClientRect().right + 16;
  const right = Math.max(16, window.innerWidth - bounds.left + 16);
  const usable = window.innerWidth - right - left;
  bubble.style.left = `${left}px`;
  bubble.style.right = `${right}px`;
  // Squeezed into a sliver it is less readable than not being there; the log
  // still carries the line either way.
  bubble.style.visibility = usable < 200 ? "hidden" : "";
}


async function mountModel() {
  // The browser bundle does not wire itself to a ticker. Without this the model
  // renders but never updates: focus targets are set and nothing interpolates
  // toward them, so the eyes stay dead ahead.
  PIXI.live2d.Live2DModel.registerTicker(PIXI.Ticker);

  // This model's texture is 1500x1500, which is not a power of two, and PIXI
  // only mipmaps power-of-two textures by default. She is drawn about 660px
  // tall, so every frame was minifying a 1500px texture with no mip chain and
  // no anisotropic filtering, which is what made the hair and the outlines
  // crawl. WebGL2 mipmaps a non-power-of-two texture happily. PIXI clamps the
  // anisotropy request to whatever the GPU reports.
  PIXI.settings.MIPMAP_TEXTURES = PIXI.MIPMAP_MODES.ON;
  PIXI.settings.ANISOTROPIC_LEVEL = 16;

  const app = new PIXI.Application({
    view: stage,
    autoStart: true,
    resizeTo: window,
    backgroundAlpha: 0,
    antialias: true,
    // Without these the canvas renders at CSS pixels and the display scales it
    // up, which costs half the detail on any HiDPI screen.
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  });

  try {
    model = await PIXI.live2d.Live2DModel.from(MODEL_URL, { autoInteract: false });
  } catch (error) {
    console.warn("no model at", MODEL_URL, error);
    return;
  }

  app.stage.addChild(model);
  indexMotions();

  // Cubism draws every clipped part -- hair over the face, layered clothing --
  // into one mask buffer and samples it back. The SDK default is 256x256, so
  // those edges were being magnified roughly three times before they reached
  // the screen; they were the most visible jaggies of the three causes.
  const renderer = model.internalModel.renderer;
  if (renderer && typeof renderer.setClippingMaskBufferSize === "function") {
    renderer.setClippingMaskBufferSize(2048);
  }

  // Drive the model from this app's ticker rather than the plugin's own wiring:
  // the browser bundle reports autoUpdate true while never attaching, which
  // renders a model that cannot blink, breathe, or follow anything.
  model.autoUpdate = false;
  app.ticker.add(() => model.update(app.ticker.deltaMS));

  layout();
  window.addEventListener("resize", layout);
  // A tab that mounts while hidden reports zero height, which would scale the
  // model to nothing and leave it there. Keep asking until the page has a size.
  new ResizeObserver(layout).observe(document.body);

  // Start her moving straight away rather than after the first interval.
  idleLoop();

  // Eyes and head follow the cursor anywhere on the page, not only over the
  // canvas, so she keeps looking at you while you type in the panel.
  window.addEventListener("pointermove", (event) => {
    model.focus(event.clientX, event.clientY);
  });

  function layout() {
    const height = window.innerHeight;
    const width = window.innerWidth;
    if (!height || !width) return;
    model.scale.set((height * view.scale) / model.internalModel.originalHeight);
    model.anchor.set(0.5, 0.5);
    model.x = width * view.x;
    model.y = height * view.y;
    placeBubble();
  }

  // Drag her anywhere. The bubble follows, so moving her out of its way is the
  // fix for the bubble covering her rather than a set of numbers I guessed.
  //
  // The grab is decided against her bounding box rather than through the
  // plugin's hit test: this model declares two hit areas with empty names, and
  // a pointerdown over her middle never reached a handler registered that way.
  let drag = null;

  stage.addEventListener("pointerdown", (event) => {
    const box = model.getBounds();
    const inside =
      event.clientX >= box.left && event.clientX <= box.right &&
      event.clientY >= box.top && event.clientY <= box.bottom;
    if (!inside) return;
    drag = { x: model.x - event.clientX, y: model.y - event.clientY };
    stage.style.cursor = "grabbing";
    stage.setPointerCapture(event.pointerId);
  });

  window.addEventListener("pointermove", (event) => {
    if (!drag) return;
    // Keep a grip on her: she can go mostly off-screen but never entirely.
    const margin = 80;
    model.x = clamp(event.clientX + drag.x, margin, window.innerWidth - margin);
    model.y = clamp(event.clientY + drag.y, -window.innerHeight, window.innerHeight * 1.5);
    placeBubble();
  });

  window.addEventListener("pointerup", () => {
    if (!drag) return;
    drag = null;
    stage.style.cursor = "";
    view.x = model.x / window.innerWidth;
    view.y = model.y / window.innerHeight;
    saveView();
  });

  // Her own zoom. Browser zoom cannot make her bigger: she is sized as a share
  // of the viewport height, and zooming in shrinks the viewport in CSS pixels by
  // the same factor, so she keeps her size on screen while the text around her
  // grows. This is the control that actually does what that gesture meant.
  window.addEventListener(
    "wheel",
    (event) => {
      if (event.target.closest && event.target.closest("#panel")) return;
      event.preventDefault();
      view.scale = clamp(view.scale * (event.deltaY > 0 ? 0.92 : 1.08), 0.25, 3);
      layout();
      saveView();
    },
    { passive: false }
  );

  // Put her back where she started.
  stage.addEventListener("dblclick", () => {
    view = { ...DEFAULT_VIEW };
    layout();
    saveView();
  });
}

// This model files all 96 motions under one unnamed group, so a motion cannot be
// asked for by group the way the sample model allowed. Index them by filename
// once, then play by name -- a model that names things differently plays nothing
// rather than throwing.
const MOTIONS = {};

function indexMotions() {
  const groups = (model.internalModel.settings || {}).motions || {};
  for (const [group, entries] of Object.entries(groups)) {
    (entries || []).forEach((entry, index) => {
      const stem = String(entry.File || "").split("/").pop().replace(".motion3.json", "");
      if (stem && !(stem in MOTIONS)) MOTIONS[stem] = [group, index];
    });
  }
}

// Every motion in this model is marked Loop, so none of them ever end. Two
// consequences, both measured against the model rather than assumed:
//
//   IDLE   succeeds once, then never again -- it is refused while anything plays
//   NORMAL succeeds once, then never again -- priority never falls back
//   FORCE  succeeds every time
//
// So everything plays at FORCE, and the idle rotation runs on a timer instead of
// waiting for a motion to finish, because waiting would wait forever.
function play(candidates) {
  const usable = candidates.filter((name) => name in MOTIONS);
  if (!model || !usable.length) return;
  const [group, index] = MOTIONS[usable[0]];
  try {
    model.motion(group, index, PIXI.live2d.MotionPriority.FORCE);
  } catch (_) { /* not loadable */ }
}

// Calm families only. The model also carries angry, startled and suffering sets;
// they are good motions, but they would read as noise from something whose whole
// job is to wait quietly until you ask it where your keys are.
const IDLE_FAMILIES = [
  "act_normal", "act_hohoemu", "act_egao",
  "face_normal", "face_hohoemu", "face_egao",
];

function idlePool() {
  const all = Object.keys(MOTIONS).filter((name) =>
    IDLE_FAMILIES.some((family) => name.startsWith(family))
  );
  // The "_w" variants are the ones drawn to be held rather than performed once.
  const held = all.filter((name) => name.endsWith("_w"));
  return held.length ? held : all;
}

// A reaction should get to play before the rotation takes the stage back.
const REACTION_HOLD_MS = 9000;
let lastReaction = 0;

function idleLoop() {
  if (model && Date.now() - lastReaction > REACTION_HOLD_MS) {
    const pool = idlePool();
    if (pool.length) play([pool[Math.floor(Math.random() * pool.length)]]);
  }
  // Uneven spacing, so she does not look like she is on a metronome. The idle
  // motions run one to four seconds and loop, so each is held a few times over.
  window.setTimeout(idleLoop, 12000 + Math.random() * 8000);
}

function express(result) {
  // Names are the model's own: unazuku nods, nayamu is troubled, komaru is at a
  // loss, kangaeru thinks.
  lastReaction = Date.now();
  if (result && result.refused) play(["act_nayamu", "face_komaru", "act_tameiki"]);
  else play(["act_unazuku", "act_egao", "act_hohoemu"]);
}

/* ---------- rendering an answer ---------- */

function speak(text) {
  bubble.textContent = text;
  bubble.hidden = false;
  placeBubble();
}

function basisNode(result) {
  // A refusal now sounds like ordinary speech, which is the point, but it is the
  // one answer with nothing behind it. Say so, and show the machine's own wording
  // underneath -- that sentence is what actually decided the refusal.
  if (result.refused) {
    const note = document.createElement("details");
    note.className = "basis";
    note.innerHTML = `<summary>${result.action_receipt ? "安全防護閘攔截" : "沒有記憶佐證"}</summary>`;
    const body = document.createElement("div");
    body.className = "body";
    body.textContent = result.reason || "系統沒有給出原因。";
    note.appendChild(body);
    return note;
  }

  if (result.action_receipt) {
    const note = document.createElement("details");
    note.className = "basis";
    const statusLabel = result.action_receipt.status === "simulated" ? "模擬執行" : "實體執行";
    note.innerHTML = `<summary>⚡ 家電操作收據 · ${statusLabel}</summary>`;
    const body = document.createElement("div");
    body.className = "body";
    body.textContent = [
      `收據編號  ${result.action_receipt.action_id}`,
      `目標設備  ${result.action_receipt.target_device_id}`,
      `執行動作  ${result.action_receipt.action_type}`,
      `執行狀態  ${result.action_receipt.status}`,
      `執行時間  ${result.action_receipt.executed_at}`,
    ].join("\n");
    note.appendChild(body);
    return note;
  }

  const memory = result.memory;
  const projection = result.projection;
  if (!memory || !projection) return null;

  const walked = new Set(
    ((result.answer && result.answer.relation_path) || []).map((s) => s.source_claim_id)
  );
  const details = document.createElement("details");
  details.className = "basis";
  const count = memory.restored_claim_count;
  details.innerHTML = `<summary>根據 ${count} 筆記錄 · 走過 ${walked.size} 條關係</summary>`;

  const lines = [];
  lines.push(`來源      ${memory.source_id}@${memory.source_revision}  ${memory.use_class}`);
  lines.push(`內容雜湊  ${memory.content_hash.slice(0, 16)}…  已驗`);
  lines.push(`語意雜湊  ${memory.semantic_output_hash.slice(0, 16)}…  已驗`);
  lines.push("");
  lines.push("記憶裡的樹");
  for (const edge of projection.edges) {
    const mark = walked.has(edge.source_claim_id) ? "▸ " : "  ";
    const relation = RELATION[edge.predicate] || edge.predicate;
    lines.push(
      `${mark}${label(edge.subject_id)} ──${relation}──▸ ${label(edge.object_id)}   第 ${edge.source_sequence} 筆`
    );
  }
  if (result.interpretation) {
    const interpretation = result.interpretation;
    const resolved = Object.values(interpretation.resolved).map(label).join("、");
    lines.push("");
    lines.push(`判讀      把「${interpretation.matched_text}」理解成 ${resolved}（${interpretation.operation}）`);
  }

  const body = document.createElement("div");
  body.className = "body";
  body.textContent = lines.join("\n");
  details.appendChild(body);
  return details;
}

function render(asked, result) {
  const turn = document.createElement("div");
  turn.className = "turn" + (result.refused ? " refused" : "");

  const you = document.createElement("div");
  you.className = "you";
  you.textContent = `你：${asked}`;
  turn.appendChild(you);

  const spoken = result.refused
    ? result.text
    : (result.spoken && result.spoken.text) || "（沒有回應）";
  const her = document.createElement("div");
  her.className = "her";
  her.textContent = spoken;
  turn.appendChild(her);

  const basis = basisNode(result);
  if (basis) turn.appendChild(basis);

  log.appendChild(turn);
  log.scrollTop = log.scrollHeight;
  speak(spoken);
  express(result);
}

/* ---------- asking ---------- */

async function ask(text) {
  if (!text.trim()) return;
  send.disabled = true;
  speak("……");
  lastReaction = Date.now();
  play(["act_kangaeru", "act_shinken"]);
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text }),
    });
    render(text, await response.json());
  } catch (error) {
    render(text, { refused: true, text: "我這邊連不上記憶，稍等一下再問一次。" });
  } finally {
    send.disabled = false;
    question.value = "";
    question.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  ask(question.value);
});

async function loadChips() {
  try {
    const { entities } = await (await fetch("/api/entities")).json();
    for (const id of entities || []) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label(id);
      button.addEventListener("click", () => ask(`${WORDS[id] || id}在哪裡？`));
      chips.appendChild(button);
    }
    const actionSuggestions = [
      { text: "❄️ 開客廳冷氣", cmd: "幫我把客廳冷氣開到26度" },
      { text: "💡 開客廳燈", cmd: "開客廳燈" },
      { text: "🪟 拉開窗簾", cmd: "拉開窗簾" },
    ];
    for (const item of actionSuggestions) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = item.text;
      button.addEventListener("click", () => ask(item.cmd));
      chips.appendChild(button);
    }
  } catch (_) { /* the panel still works without chips */ }
}

mountModel();
loadChips();
speak("在的。想找什麼東西嗎？");
