/* Character front end. Everything factual comes from /api/ask; this file only
   decides how it looks and where she is looking. */

const MODEL_URL = "/live2d/rem/REM.model3.json";

const stage = document.getElementById("stage");
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

async function mountModel() {
  // The browser bundle does not wire itself to a ticker. Without this the model
  // renders but never updates: focus targets are set and nothing interpolates
  // toward them, so the eyes stay dead ahead.
  PIXI.live2d.Live2DModel.registerTicker(PIXI.Ticker);

  const app = new PIXI.Application({
    view: stage,
    autoStart: true,
    resizeTo: window,
    backgroundAlpha: 0,
    antialias: true,
  });

  try {
    model = await PIXI.live2d.Live2DModel.from(MODEL_URL, { autoInteract: false });
  } catch (error) {
    console.warn("no model at", MODEL_URL, error);
    return;
  }

  app.stage.addChild(model);
  indexMotions();

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

  // Eyes and head follow the cursor anywhere on the page, not only over the
  // canvas, so she keeps looking at you while you type in the panel.
  window.addEventListener("pointermove", (event) => {
    model.focus(event.clientX, event.clientY);
  });

  function layout() {
    const height = window.innerHeight;
    const width = window.innerWidth;
    if (!height || !width) return;
    model.scale.set((height * 0.92) / model.internalModel.originalHeight);
    model.anchor.set(0.5, 0.5);
    model.x = width * 0.68;
    model.y = height * 0.54;
  }
}

// This model files all 96 motions under one unnamed group, so a motion cannot be
// asked for by group the way the sample model allowed. Index them by filename
// once, then play the first candidate that exists -- a model that names things
// differently simply plays nothing rather than throwing.
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

function play(...candidates) {
  if (!model) return;
  for (const name of candidates) {
    if (name in MOTIONS) {
      const [group, index] = MOTIONS[name];
      try { model.motion(group, index); } catch (_) { /* not loadable */ }
      return;
    }
  }
}

function express(result) {
  // Names are the model's own: unazuku nods, nayamu is troubled, kangaeru thinks.
  if (result && result.refused) play("act_nayamu", "act_komaru", "act_tameiki");
  else play("act_unazuku", "act_egao", "act_hohoemu");
}

/* ---------- rendering an answer ---------- */

function speak(text) {
  bubble.textContent = text;
  bubble.hidden = false;
}

function basisNode(result) {
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
  play("act_kangaeru", "act_shinken");
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
  } catch (_) { /* the panel still works without chips */ }
}

mountModel();
loadChips();
speak("在的。想找什麼東西嗎？");
