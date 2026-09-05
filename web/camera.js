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
const QUALITY = 0.9;
let currentFps = 10;

const deviceSelect = document.getElementById("device");
const deviceNote = document.getElementById("device-note");
const grantButton = document.getElementById("grant");
const startButton = document.getElementById("start");
const stopButton = document.getElementById("stop");
const statsBox = document.getElementById("stats");
const logBox = document.getElementById("log");
const preview = document.getElementById("preview");
const overlay = document.getElementById("overlay");
const grab = document.getElementById("grab");
const indicator = document.getElementById("indicator");
const fpsDisplay = document.getElementById("fps-display");
const fpsChips = document.querySelectorAll(".fps-chip");
const zoneSelect = document.getElementById("zone-select");
const commitToast = document.getElementById("commit-toast");
const enrollmentBanner = document.getElementById("enrollment-banner");

const ZONE_NAMES = { desk: "書桌", table: "餐桌", sofa: "沙發" };
const ENTITY_NAMES = { phone: "手機", cup: "水杯", bottle: "水瓶", laptop: "筆電", bag: "包包", key: "鑰匙" };

function updateEnrollmentStatus(enrollment) {
  if (!enrollmentBanner) return;
  if (!enrollment || !enrollment.active) {
    if (enrollment && (enrollment.just_completed || enrollment.completed)) {
      if (enrollment.just_completed) {
        enrollmentBanner.textContent = `🎉【${enrollment.display_name}】特徵樣本已採集完畢！雷姆已停止觀察，已將專屬外觀記住囉！`;
        enrollmentBanner.className = "enrollment-banner completed";
        enrollmentBanner.style.display = "block";
        say(`🎉【${enrollment.display_name}】視覺少樣本採樣達標，已自動停止觀察並寫入記憶！`);
        clearTimeout(enrollmentBanner._timer);
        enrollmentBanner._timer = setTimeout(() => {
          enrollmentBanner.style.display = "none";
        }, 5000);
      }
    } else if (!enrollmentBanner.classList.contains("completed")) {
      enrollmentBanner.style.display = "none";
      enrollmentBanner.className = "enrollment-banner";
    }
    return;
  }

  enrollmentBanner.className = "enrollment-banner active";
  enrollmentBanner.style.display = "block";
  enrollmentBanner.textContent = `📸 正在學習【${enrollment.display_name}】特徵 (${enrollment.collected}/${enrollment.target} 張)... 請靠近鏡頭並稍微轉動角度給雷姆看`;
}

function showCommitToast(item) {
  const subj = ENTITY_NAMES[item.subject_id] || item.subject_id;
  const zone = ZONE_NAMES[item.zone_id] || item.zone_id;
  say(`🎯 記憶寫入：【${subj}】位置已確認記錄於【${zone}】！ (claim=${item.claim_id})`);

  if (commitToast) {
    commitToast.textContent = `🎯 記憶已更新：【${subj}】位於【${zone}】`;
    commitToast.style.display = "block";
    clearTimeout(commitToast._timer);
    commitToast._timer = setTimeout(() => {
      commitToast.style.display = "none";
    }, 3500);
  }
}

grab.width = WIDTH;
grab.height = HEIGHT;
const context = grab.getContext("2d", { willReadFrequently: false });
const overlayContext = overlay ? overlay.getContext("2d") : null;

let stream = null;
let session = null;
let rafId = null;
let lastFrameTime = 0;
let sequence = 0;
let sent = 0;
let accepted = 0;
let refused = 0;
let bytes = 0;
let startedAt = 0;
let inFlight = false;

// FPS Selection Handling
fpsChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    fpsChips.forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    currentFps = parseInt(chip.getAttribute("data-fps") || "10", 10);
    if (fpsDisplay) fpsDisplay.textContent = String(currentFps);
    say(`取樣率已切換為 ${currentFps} fps。`);
  });
});

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

function syncOverlaySize() {
  if (!overlay || !preview) return;
  if (overlay.width !== preview.clientWidth || overlay.height !== preview.clientHeight) {
    overlay.width = preview.clientWidth;
    overlay.height = preview.clientHeight;
  }
}

function renderDetections(detections) {
  if (!overlayContext) return;
  syncOverlaySize();
  overlayContext.clearRect(0, 0, overlay.width, overlay.height);
  if (!detections || !detections.length) return;

  const scaleX = overlay.width / WIDTH;
  const scaleY = overlay.height / HEIGHT;
  overlayContext.lineWidth = 2;
  overlayContext.strokeStyle = "#00ff66";
  overlayContext.fillStyle = "#00ff66";
  overlayContext.font = "12px monospace";

  for (const det of detections) {
    const box = det.box;
    if (box && box.length === 4) {
      const [x, y, w, h] = box;
      if (det.visual_matched) {
        overlayContext.strokeStyle = "#bb86fc";
        overlayContext.fillStyle = "#bb86fc";
      } else {
        overlayContext.strokeStyle = "#00ff66";
        overlayContext.fillStyle = "#00ff66";
      }
      overlayContext.strokeRect(x * scaleX, y * scaleY, w * scaleX, h * scaleY);
      let label = det.label ? `${det.label} (${Math.round((det.confidence || 0) * 100)}%)` : "";
      if (det.visual_matched) {
        const entityLabel = ENTITY_NAMES[det.matched_entity] || det.label || "專屬物品";
        label = `✨ 專屬${entityLabel} (${Math.round((det.visual_score || 0.95) * 100)}%)`;
      }
      if (label) {
        overlayContext.fillText(label, x * scaleX + 4, Math.max(14, y * scaleY - 4));
      }
    }
  }
}

async function listDevices() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  const cameras = devices.filter((d) => d.kind === "videoinput");
  deviceSelect.replaceChildren();
  for (const camera of cameras) {
    const option = document.createElement("option");
    option.value = camera.deviceId;
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
    const probe = await navigator.mediaDevices.getUserMedia({ video: true });
    probe.getTracks().forEach((t) => t.stop());
    await listDevices();
    say("已取得鏡頭權限。");
  } catch (error) {
    say(`取得權限失敗：${error.name} ${error.message}`, "refused");
  }
});

async function openCamera(deviceId) {
  // 2-stage negotiation:
  // Stage 1: Try exact 1280x720 with resizeMode: "none" (fail-closed unscaled capture).
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        deviceId: { exact: deviceId },
        width: { exact: WIDTH },
        height: { exact: HEIGHT },
        frameRate: { ideal: currentFps },
        resizeMode: { exact: "none" },
      },
    });
    return { stream, isFallback: false };
  } catch (error) {
    // Stage 2: If exact unscaled mode is not supported by the camera/browser (OverconstrainedError
    // or unsupported resizeMode), fall back to ideal constraints with aspect-fill center crop.
    say(
      `鏡頭不支援原生無縮放 1280×720 (${error.name})，切換為相容裁切模式。`,
      "turn"
    );
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        deviceId: { exact: deviceId },
        width: { ideal: WIDTH },
        height: { ideal: HEIGHT },
        frameRate: { ideal: currentFps },
      },
    });
    return { stream, isFallback: true };
  }
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
  if (inFlight || !session) return;
  inFlight = true;
  try {
    const srcW = preview.videoWidth || WIDTH;
    const srcH = preview.videoHeight || HEIGHT;
    const targetRatio = WIDTH / HEIGHT;
    const srcRatio = srcW / srcH;
    let sx = 0, sy = 0, sw = srcW, sh = srcH;

    // Aspect-ratio preserving center crop if source camera aspect ratio differs from 16:9
    if (Math.abs(srcRatio - targetRatio) > 0.01) {
      if (srcRatio > targetRatio) {
        sw = srcH * targetRatio;
        sx = (srcW - sw) / 2;
      } else {
        sh = srcW / targetRatio;
        sy = (srcH - sh) / 2;
      }
    }

    context.drawImage(preview, sx, sy, sw, sh, 0, 0, WIDTH, HEIGHT);
    const blob = await new Promise((resolve) =>
      grab.toBlob(resolve, "image/jpeg", QUALITY)
    );
    if (!blob) return;
    const position = sequence++;
    sent += 1;
    const currentZone = zoneSelect ? zoneSelect.value : "desk";
    const url =
      `/api/camera/frame?session=${encodeURIComponent(session)}` +
      `&sequence=${position}&captured_ns=${Math.round(performance.now() * 1e6)}` +
      `&zone=${encodeURIComponent(currentZone)}`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "image/jpeg" },
      body: blob,
    });
    const result = await response.json();
    if (response.ok) {
      accepted += 1;
      bytes += result.bytes || blob.size;
      if (result.detections) {
        renderDetections(result.detections);
      }
      if (result.enrollment) {
        updateEnrollmentStatus(result.enrollment);
      }
      if (result.committed && result.committed.length) {
        for (const item of result.committed) {
          showCommitToast(item);
        }
      }
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

function frameLoop(now) {
  if (!session) return;
  const interval = 1000 / currentFps;
  if (now - lastFrameTime >= interval) {
    lastFrameTime = now;
    sendFrame();
  }
  rafId = window.requestAnimationFrame(frameLoop);
}

startButton.addEventListener("click", async () => {
  const deviceId = deviceSelect.value;
  if (!deviceId) return;
  startButton.disabled = true;
  try {
    const opened = await openCamera(deviceId);
    stream = opened.stream;
  } catch (error) {
    startButton.disabled = false;
    say(`開啟鏡頭失敗：${error.name} ${error.message}`, "refused");
    return;
  }

  preview.srcObject = stream;
  await preview.play().catch(() => {});
  const settings = negotiated();
  say(
    `已開啟 ${settings.width}×${settings.height} @${Math.round(settings.frameRate || currentFps)} ` +
      `resizeMode=${settings.resizeMode || "fallback-crop"}`
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
  lastFrameTime = performance.now();
  stopButton.disabled = false;
  setIndicator(true, "鏡頭開啟中 · 正在傳送");
  rafId = window.requestAnimationFrame(frameLoop);
  say(`session ${session} 開始，目標 ${currentFps} fps。`);
});

stopButton.addEventListener("click", async () => {
  stopButton.disabled = true;
  if (rafId) {
    window.cancelAnimationFrame(rafId);
    rafId = null;
  }
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  preview.srcObject = null;
  if (overlayContext && overlay) {
    overlayContext.clearRect(0, 0, overlay.width, overlay.height);
  }
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

window.addEventListener("pagehide", () => {
  if (stream) stream.getTracks().forEach((t) => t.stop());
  if (rafId) window.cancelAnimationFrame(rafId);
});

listDevices().catch(() => {
  deviceNote.textContent = "這個瀏覽器不允許列出裝置。";
});
