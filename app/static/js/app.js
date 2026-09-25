const state = {
  profile: "av",
  flip_horizontal: false,
  flip_vertical: false,
  running: false,
  busy: false,
};

const $ = (id) => document.getElementById(id);
const statusPill = $("statusPill");
const startButton = $("startButton");
const stopButton = $("stopButton");
const flipH = $("flipH");
const flipV = $("flipV");
const flipCard = $("flipCard");
const profileHint = $("profileHint");
const message = $("message");
const waylandState = $("waylandState");

function setMessage(text = "", error = false) {
  message.textContent = text;
  message.className = error ? "message error" : "message";
}

function setBusy(value) {
  state.busy = value;
  document.querySelectorAll("button").forEach((button) => {
    button.disabled = value;
  });
}

function updateFlipButton(button, enabled) {
  button.setAttribute("aria-pressed", String(enabled));
  button.querySelector(".toggle-state").textContent = enabled ? "On" : "Off";
}

function render() {
  statusPill.textContent = state.running ? "Running" : "Stopped";
  statusPill.className = state.running ? "pill pill-on" : "pill pill-off";
  startButton.textContent = state.running ? "Apply & restart" : "Start receiver";
  stopButton.disabled = state.busy || !state.running;

  document.querySelectorAll("[data-profile]").forEach((button) => {
    button.classList.toggle("active", button.dataset.profile === state.profile);
  });

  flipCard.classList.toggle("hidden", state.profile !== "av");
  profileHint.textContent = state.profile === "av"
    ? "Low-latency screen mirroring with HDMI audio."
    : "AirPlay Audio with album-art rendering; no mirrored video.";

  updateFlipButton(flipH, state.flip_horizontal);
  updateFlipButton(flipV, state.flip_vertical);
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

async function refresh() {
  if (state.busy) return;
  try {
    const data = await api("/api/session");
    state.running = data.running;
    waylandState.textContent = data.wayland_ready ? "labwc ready" : "labwc not ready";

    if (data.spec) {
      state.profile = data.spec.profile;
      state.flip_horizontal = data.spec.flip_horizontal;
      state.flip_vertical = data.spec.flip_vertical;
    }
    render();
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function start() {
  if (state.busy) return;
  setBusy(true);
  setMessage(state.running ? "Applying settings…" : "Starting…");

  try {
    const data = await api("/api/session", {
      method: "PUT",
      body: JSON.stringify({
        profile: state.profile,
        flip_horizontal: state.flip_horizontal,
        flip_vertical: state.flip_vertical,
      }),
    });

    state.running = true;
    setMessage(data.changed ? "Receiver ready" : "Already running with these settings");
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    setBusy(false);
    await refresh();
  }
}

async function stop() {
  if (state.busy) return;
  setBusy(true);
  setMessage("Stopping…");

  try {
    const data = await api("/api/session", { method: "DELETE" });
    state.running = false;
    setMessage(data.changed ? "Receiver stopped" : "Receiver was already stopped");
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    setBusy(false);
    await refresh();
  }
}

async function applyIfRunning() {
  render();
  if (state.running) await start();
}

document.querySelectorAll("[data-profile]").forEach((button) => {
  button.addEventListener("click", async () => {
    state.profile = button.dataset.profile;
    await applyIfRunning();
  });
});

flipH.addEventListener("click", async () => {
  state.flip_horizontal = !state.flip_horizontal;
  await applyIfRunning();
});

flipV.addEventListener("click", async () => {
  state.flip_vertical = !state.flip_vertical;
  await applyIfRunning();
});

async function refreshDisplay() {
  try {
    const data = await api("/api/display");
    document.querySelectorAll("[data-mode]").forEach((button) => {
      const selected = button.dataset.mode === data.mode;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    $("displayState").textContent = `${data.output} · ${data.mode || data.transform}`;
  } catch (error) {
    $("displayState").textContent = error.message;
    document.querySelectorAll("[data-mode]").forEach((button) => {
      button.classList.remove("active");
      button.setAttribute("aria-pressed", "false");
    });
  }
}

document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (state.busy) return;
    setBusy(true);
    setMessage("Rotating display…");
    try {
      await api("/api/display", {
        method: "PUT",
        body: JSON.stringify({ mode: button.dataset.mode }),
      });
      setMessage("Display orientation applied");
    } catch (error) {
      setMessage(error.message, true);
    } finally {
      await refreshDisplay();
      setBusy(false);
      render();
    }
  });
});

refreshDisplay();
startButton.addEventListener("click", start);
stopButton.addEventListener("click", stop);

refresh();
setInterval(refresh, 5000);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/static/sw.js"));
}
