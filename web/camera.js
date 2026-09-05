/* The camera lives here, in the client. The server never opens one.

   Two things this page relies on that a native capture path has to build itself.
   `exact` constraints with `resizeMode: "none"` mean the browser refuses a camera
   that cannot produce the registered format rather than quietly rescaling one
   that cannot -- v4l2, asked for a size it does not have, inserts a scaler and
   reports back the size it was asked for, so the obvious check there passes
   always. And `deviceId` is stable for this origin, which is the registered
   identity the pipeline wants and the thing every project in this space
   struggles to obtain natively.

   Quality 90 is measured rather than chosen. On real frames, the high-detail
   regions where a small object sits keep 92% of their detail at q90 and 98% at
   q95, and those six points cost half again as much bandwidth. Raw frames would
   be 27 MB/s. */

const WIDTH = 1280;
const HEIGHT = 720;
const FPS = 10;
const QUALITY = 0.9;

const deviceSelect = document.getElementById("device");
const deviceNote = document.getElementById("device-note");
const grantButton = document.getElementById("grant");
const startButton = document.getElementById("start");
const stopButton = document.getElementById("stop");
const statsBox = document.getElementById("stats");
const logBox = document.getElementById("log");
const preview = document.getElementById("preview");
const grab = document.getElementById("grab");
const indicator = document.getElementById("indicator");

grab.width = WIDTH;
grab.height = HEIGHT;
const context = grab.getContext("2d", { willReadFrequently: false });

let stream = null;
let session = null;
let timer = null;
let sequence = 0;
let sent = 0;
let accepted = 0;
let refused = 0;
let bytes = 0;
let startedAt = 0;
let inFlight = false;

function say(text, kind = "") {
  const line = document.createElement("div");
  line.className = "turn " + kind;
  line.textContent = text;
  logBox.appendChild(line);
  logBox.scrollTop = logBox.scrollHeight;
}

function setIndicator(on, text) {
  indicator.className = "indicator " + (on ? "on" : "off");
  indicator.textContent = text;
}

async function listDevices() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  const cameras = devices.filter((d) => d.kind === "videoinput");
  deviceSelect.replaceChildren();
  for (const camera of cameras) {
    const option = document.createElement("option");
    option.value = camera.deviceId;
    // A blank label means permission has not been granted yet; the identifier is
    // still stable, so the page works either way.
    option.textContent = camera.label || `鏡頭 ${camera.deviceId.slice(0, 8)}…`;
    deviceSelect.appendChild(option);
  }
  deviceNote.textContent = cameras.length
    ? `找到 ${cameras.length} 個鏡頭`
    : "找不到任何鏡頭";
  startButton.disabled = cameras.length === 0;
  return cameras.length;
}

grantButton.addEventListener("click", async () => {
  try {
    // Asking for anything at all is what makes labels visible. The track is
    // released immediately; this is a permission prompt, not a capture.
    const probe = await navigator.mediaDevices.getUserMedia({ video: true });
    probe.getTracks().forEach((t) => t.stop());
    await listDevices();
    say("已取得鏡頭權限。");
  } catch (error) {
    say(`取得權限失敗：${error.name} ${error.message}`, "refused");
  }
});

async function openCamera(deviceId) {
  // exact, not ideal. An ideal constraint is a suggestion the browser may ignore;
  // an exact one it must satisfy or reject, which is the fail-closed behaviour
  // the pipeline is specified around.
  const constraints = {
    audio: false,
    video: {
      deviceId: { exact: deviceId },
      width: { exact: WIDTH },
      height: { exact: HEIGHT },
      frameRate: { ideal: FPS },
      resizeMode: { exact: "none" },
    },
  };
  return navigator.mediaDevices.getUserMedia(constraints);
}

function negotiated() {
  const track = stream?.getVideoTracks?.()[0];
  if (!track) return {};
  const settings = track.getSettings();
  return {
    width: settings.width,
    height: settings.height,
    frameRate: settings.frameRate,
    deviceId: settings.deviceId,
    resizeMode: settings.resizeMode,
  };
}

async function sendFrame() {
  // One frame at a time. Queueing on a slow link would turn a bandwidth problem
  // into a memory problem, and the gap the server records is the honest report.
  if (inFlight || !session) return;
  inFlight = true;
  try {
    context.drawImage(preview, 0, 0, WIDTH, HEIGHT);
    const blob = await new Promise((resolve) =>
      grab.toBlob(resolve, "image/jpeg", QUALITY)
    );
    if (!blob) return;
    const position = sequence++;
    sent += 1;
    const url =
      `/api/camera/frame?session=${encodeURIComponent(session)}` +
      `&sequence=${position}&captured_ns=${Math.round(performance.now() * 1e6)}`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "image/jpeg" },
      body: blob,
    });
    const result = await response.json();
    if (response.ok) {
      accepted += 1;
      bytes += result.bytes || blob.size;
    } else {
      refused += 1;
      say(`第 ${position} 格被拒：${result.error}`, "refused");
    }
  } catch (error) {
    refused += 1;
  } finally {
    inFlight = false;
    render();
  }
}

function render() {
  const seconds = (performance.now() - startedAt) / 1000 || 1;
  const rate = accepted / seconds;
  const mbps = (bytes / seconds) / 1048576;
  statsBox.textContent =
    `送出 ${sent} · 接受 ${accepted} · 拒絕 ${refused}\n` +
    `實測 ${rate.toFixed(1)} fps · ${mbps.toFixed(2)} MB/s\n` +
    `平均每格 ${accepted ? Math.round(bytes / accepted / 1024) : 0} KB`;
}

startButton.addEventListener("click", async () => {
  const deviceId = deviceSelect.value;
  if (!deviceId) return;
  startButton.disabled = true;
  try {
    stream = await openCamera(deviceId);
  } catch (error) {
    startButton.disabled = false;
    if (error.name === "OverconstrainedError") {
      // This is the case the whole format contract exists for, so it is reported
      // as the refusal it is rather than as a generic failure.
      say(
        `這個鏡頭做不到 ${WIDTH}×${HEIGHT}（受限於 ${error.constraint}）。` +
          "沒有退而求其次，所以不會開始。",
        "refused"
      );
    } else {
      say(`開啟鏡頭失敗：${error.name} ${error.message}`, "refused");
    }
    return;
  }

  preview.srcObject = stream;
  await preview.play().catch(() => {});
  const settings = negotiated();
  say(
    `已開啟 ${settings.width}×${settings.height} @${Math.round(settings.frameRate)} ` +
      `resizeMode=${settings.resizeMode}`
  );

  const response = await fetch("/api/camera/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      device_label: deviceSelect.selectedOptions[0]?.textContent || "unnamed",
      negotiated: settings,
    }),
  });
  const opened = await response.json();
  if (!response.ok) {
    say(`伺服器拒絕開始：${opened.error}`, "refused");
    stream.getTracks().forEach((t) => t.stop());
    startButton.disabled = false;
    return;
  }

  session = opened.session_id;
  sequence = sent = accepted = refused = bytes = 0;
  startedAt = performance.now();
  stopButton.disabled = false;
  setIndicator(true, "鏡頭開啟中 · 正在傳送");
  timer = window.setInterval(sendFrame, 1000 / FPS);
  say(`session ${session} 開始，目標 ${FPS} fps。`);
});

stopButton.addEventListener("click", async () => {
  stopButton.disabled = true;
  window.clearInterval(timer);
  timer = null;
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  preview.srcObject = null;
  setIndicator(false, "鏡頭未開啟");

  if (session) {
    const response = await fetch("/api/camera/end", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: session }),
    });
    const receipt = await response.json();
    session = null;
    if (response.ok) {
      say(
        `收據：接受 ${receipt.accepted} 格，遺失 ${receipt.missing_positions} 格` +
          `（${receipt.gaps} 段），平均 ${Math.round(receipt.mean_frame_bytes / 1024)} KB，` +
          `實測 ${receipt.observed_fps} fps，保留 ${receipt.retention}。`
      );
      say(`串流雜湊 ${receipt.stream_sha256.slice(0, 32)}…`);
    }
  }
  startButton.disabled = false;
});

// Stopping the tab must stop the camera. A page that keeps a light on after the
// person navigated away is the failure everyone remembers.
window.addEventListener("pagehide", () => {
  if (stream) stream.getTracks().forEach((t) => t.stop());
  if (timer) window.clearInterval(timer);
});

listDevices().catch(() => {
  deviceNote.textContent = "這個瀏覽器不允許列出裝置。";
});
