/* Character front end. Everything factual comes from /api/ask; this file only
   decides how it looks and where she is looking.

   Who is standing there lives in characters.js. Nothing below asks which of them
   it is holding -- layout, drag, wheel and bubble all speak to the same handful
   of methods, so a third character would be a definition and an image. */

const stage = document.getElementById("stage");
const panel = document.getElementById("panel");
const bubble = document.getElementById("bubble");
const log = document.getElementById("log");
const form = document.getElementById("ask");
const question = document.getElementById("question");
const send = document.getElementById("send");
const chips = document.getElementById("chips");
const cast = document.getElementById("cast");

const LABELS = { key: "🔑 鑰匙", bag: "👜 包包", sofa: "🛋 沙發" };
const WORDS = { key: "鑰匙", bag: "包包", sofa: "沙發" };
const RELATION = { inside: "在…裡面", at_zone: "位於" };

const label = (id) => LABELS[id] || id;
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

/* ---------- who is on stage ---------- */

let app = null;
let actor = null;

const CHOICE_KEY = "wha.character.who";
const VIEW_KEY = "wha.character.view";
const DEFAULT_VIEW = { x: 0.74, y: 0.54, scale: 0.92 };

function readChoice() {
  try {
    const saved = localStorage.getItem(CHOICE_KEY);
    if (saved && saved in CHARACTERS) return saved;
  } catch (_) { /* private mode */ }
  return DEFAULT_CHARACTER_ID;
}

let who = readChoice();

// Views are per character: they are different heights and shapes, so a position
// that suits one puts the other's head through the ceiling.
function readView(id) {
  try {
    const all = JSON.parse(localStorage.getItem(VIEW_KEY) || "null");
    const saved = all && all[id];
    if (saved && ["x", "y", "scale"].every((k) => typeof saved[k] === "number")) {
      return saved;
    }
  } catch (_) { /* a corrupt entry is not worth a broken page */ }
  return { ...DEFAULT_VIEW };
}

let view = readView(who);

function saveView() {
  try {
    const all = JSON.parse(localStorage.getItem(VIEW_KEY) || "null") || {};
    all[who] = view;
    localStorage.setItem(VIEW_KEY, JSON.stringify(all));
  } catch (_) { /* private mode */ }
}

// The bubble sits in whatever gap is left between the panel and wherever she is
// standing now. Deriving it from her actual bounds is why this is not in CSS:
// the stylesheet had to assume a position, and she is no longer at one.
function placeBubble() {
  if (!actor) return;
  const bounds = actor.bounds();
  const left = panel.getBoundingClientRect().right + 16;
  const right = Math.max(16, window.innerWidth - bounds.left + 16);
  const usable = window.innerWidth - right - left;
  bubble.style.left = `${left}px`;
  bubble.style.right = `${right}px`;
  // Squeezed into a sliver it is less readable than not being there; the log
  // still carries the line either way.
  bubble.style.visibility = usable < 200 ? "hidden" : "";
}

function layout() {
  const height = window.innerHeight;
  const width = window.innerWidth;
  if (!actor || !height || !width || !actor.naturalHeight) return;
  actor.setScale((height * view.scale) / actor.naturalHeight);
  actor.setPosition(width * view.x, height * view.y);
  placeBubble();
}

function createStage() {
  // This model's texture is 1500x1500, which is not a power of two, and PIXI
  // only mipmaps power-of-two textures by default. She is drawn about 660px
  // tall, so every frame was minifying a 1500px texture with no mip chain and
  // no anisotropic filtering, which is what made the hair and the outlines
  // crawl. WebGL2 mipmaps a non-power-of-two texture happily. PIXI clamps the
  // anisotropy request to whatever the GPU reports.
  PIXI.settings.MIPMAP_TEXTURES = PIXI.MIPMAP_MODES.ON;
  PIXI.settings.ANISOTROPIC_LEVEL = 16;

  app = new PIXI.Application({
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

  app.ticker.add(() => {
    if (actor) actor.update(app.ticker.deltaMS);
  });

  window.addEventListener("resize", layout);
  // A tab that mounts while hidden reports zero height, which would scale the
  // character to nothing and leave it there. Keep asking until the page has a
  // size -- and a sprite's texture arrives late, which this also catches.
  new ResizeObserver(layout).observe(document.body);

  // Eyes, or the whole body, follow the cursor anywhere on the page rather than
  // only over the canvas, so she keeps looking at you while you type.
  window.addEventListener("pointermove", (event) => {
    if (actor && !drag) actor.focus(event.clientX, event.clientY);
  });

  // Drag her anywhere. The bubble follows, so moving her out of its way is the
  // remedy for an overlap rather than a set of numbers guessed in a stylesheet.
  //
  // The grab is decided against her bounding box rather than through the
  // plugin's hit test: the Live2D model declares two hit areas with empty names,
  // and a handler registered the usual way never fired for a press over her
  // middle. A sprite has no hit areas at all.
  stage.addEventListener("pointerdown", (event) => {
    if (!actor) return;
    const box = actor.bounds();
    const inside =
      event.clientX >= box.left && event.clientX <= box.right &&
      event.clientY >= box.top && event.clientY <= box.bottom;
    if (!inside) return;
    const at = actor.position();
    drag = { x: at.x - event.clientX, y: at.y - event.clientY };
    stage.style.cursor = "grabbing";
    stage.setPointerCapture(event.pointerId);
  });

  window.addEventListener("pointermove", (event) => {
    if (!drag || !actor) return;
    // Keep a grip on her: she can go mostly off-screen but never entirely.
    const margin = 80;
    actor.setPosition(
      clamp(event.clientX + drag.x, margin, window.innerWidth - margin),
      clamp(event.clientY + drag.y, -window.innerHeight, window.innerHeight * 1.5)
    );
    placeBubble();
  });

  window.addEventListener("pointerup", () => {
    if (!drag || !actor) return;
    drag = null;
    stage.style.cursor = "";
    const at = actor.position();
    view.x = at.x / window.innerWidth;
    view.y = at.y / window.innerHeight;
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

let drag = null;

async function setCharacter(id) {
  if (!(id in CHARACTERS)) return;
  const previous = actor;
  let next;
  try {
    next = await createActor(id);
  } catch (error) {
    // The art is deliberately outside version control, so this is the ordinary
    // state of a fresh clone rather than a crash: keep whoever is on stage and
    // say what is missing.
    console.warn("cannot mount", id, error);
    speak(`${CHARACTERS[id].name}的模型還沒放進來，把檔案放到 ${CHARACTERS[id].model || CHARACTERS[id].image} 就會出現。`);
    return;
  }
  // Only now is the old one taken down, so a model that fails to load leaves
  // the page with the character it already had rather than an empty canvas.
  if (previous) {
    previous.detach(app);
    previous.destroy();
  }
  actor = next;
  actor.attach(app);
  who = id;
  view = readView(id);
  try { localStorage.setItem(CHOICE_KEY, id); } catch (_) { /* private mode */ }
  layout();
  actor.express("idle");
  drawCast();

  const arrived = await actor.ready();
  layout();
  speak(
    arrived
      ? `${CHARACTERS[id].speaksAs || CHARACTERS[id].name}在的。想找什麼東西嗎？`
      : `${CHARACTERS[id].name}的圖還沒放進來，把立繪放到 ${CHARACTERS[id].image} 就會出現。`
  );
}

function drawCast() {
  cast.replaceChildren();
  for (const [id, definition] of Object.entries(CHARACTERS)) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = definition.name;
    button.title = definition.note;
    button.className = id === who ? "on" : "";
    button.addEventListener("click", () => setCharacter(id));
    cast.appendChild(button);
  }
}

/* ---------- idle ---------- */

// The Live2D plugin's own idle loop looks for a group called "Idle", and that
// model files all 96 motions under one unnamed group, so the loop never found
// anything and she stood still between questions. The rotation is driven from
// here for both kinds instead.
const REACTION_HOLD_MS = 9000;
let lastReaction = 0;

function idleLoop() {
  if (actor && Date.now() - lastReaction > REACTION_HOLD_MS) actor.express("idle");
  // Uneven spacing, so she does not look like she is on a metronome.
  window.setTimeout(idleLoop, 12000 + Math.random() * 8000);
}

function express(kind) {
  lastReaction = Date.now();
  if (actor) actor.express(kind);
}

/* ---------- rendering an answer ---------- */

function speak(text) {
  bubble.textContent = text;
  bubble.hidden = false;
  placeBubble();
}

function basisNode(result) {
  // A refusal sounds like ordinary speech, which is the point, but it is the one
  // answer with nothing behind it. Say so, and show the machine's own wording
  // underneath -- that sentence is what actually decided the refusal.
  if (result.refused) {
    const note = document.createElement("details");
    note.className = "basis";
    note.innerHTML = "<summary>沒有記憶佐證</summary>";
    const body = document.createElement("div");
    body.className = "body";
    body.textContent = result.reason || "系統沒有給出原因。";
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
  express(result.refused ? "refuse" : "answer");
}

/* ---------- asking ---------- */

async function ask(text) {
  if (!text.trim()) return;
  send.disabled = true;
  speak("……");
  express("thinking");
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // The character decides the name in front of the answer, never the answer.
      body: JSON.stringify({ question: text, character: who }),
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
  } catch (_) { /* the panel still works without chips */ }
}

createStage();
drawCast();
setCharacter(who);
idleLoop();
loadChips();
