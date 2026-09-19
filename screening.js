(() => {
  const el = (id) => document.getElementById(id);

  const stateRecord = el("state-record");
  const stateAnalyzing = el("state-analyzing");
  const stateResults = el("state-results");
  const errorBanner = el("error-banner");

  const metaId = el("meta-id");
  const metaTime = el("meta-time");
  const statusDot = el("status-dot");
  const statusText = el("status-text");

  const micBtn = el("mic-btn");
  const micSupportBadge = el("mic-support-badge");
  const recordTimerEl = el("record-timer");
  const recordStatusLabel = el("record-status-label");
  const recordHint = el("record-hint");
  const waveformCanvas = el("waveform-canvas");
  const liveControls = el("recording-live-controls");
  const pauseBtn = el("pause-btn");
  const stopBtn = el("stop-btn");

  const uploadRow = el("upload-row");
  const fileInput = el("file-input");
  const reviewRow = el("review-row");
  const audioPreview = el("audio-preview");
  const previewDuration = el("preview-duration");
  const previewSource = el("preview-source");
  const rerecordBtn = el("rerecord-btn");
  const analyzeBtn = el("analyze-btn");

  const newScreeningBtn = el("new-screening-btn");
  const patientIdInput = el("patient-id-input");

  let mediaRecorder = null;
  let mediaStream = null;
  let audioContext = null;
  let analyser = null;
  let animationFrame = null;
  let recordedChunks = [];
  let recordedBlob = null;
  let recordedSource = null; // "Microphone recording" | "Uploaded file"
  let recordedDurationSec = null;
  let timerInterval = null;
  let elapsedMs = 0;
  let isPaused = false;

  function pad(n) { return String(n).padStart(2, "0"); }

  function formatTimer(ms) {
    const total = Math.floor(ms / 1000);
    return `${pad(Math.floor(total / 60))}:${pad(total % 60)}`;
  }

  function setStatus(kind, label) {
    statusDot.className = `status-dot ${kind}`;
    statusText.textContent = label;
  }

  function generateScreeningId() {
    const now = new Date();
    const stamp = now.toISOString().replace(/[-:T]/g, "").slice(0, 14);
    const suffix = Math.random().toString(16).slice(2, 6).toUpperCase();
    return `SCR-${stamp.slice(0, 8)}-${suffix}`;
  }

  function initMeta() {
    metaId.textContent = generateScreeningId();
    metaTime.textContent = new Date().toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
    setStatus("idle", "Awaiting recording");
  }

  function showError(message) {
    errorBanner.textContent = message;
    errorBanner.style.display = "flex";
  }
  function clearError() {
    errorBanner.style.display = "none";
    errorBanner.textContent = "";
  }

  // ---------- Microphone support check ----------
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    micSupportBadge.textContent = "Microphone available";
    micSupportBadge.className = "badge badge-accent";
  } else {
    micSupportBadge.textContent = "Microphone unavailable — upload instead";
    micSupportBadge.className = "badge badge-caution";
    micBtn.disabled = true;
  }

  // ---------- Waveform drawing ----------
  function drawWaveform() {
    const ctx = waveformCanvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const rect = waveformCanvas.getBoundingClientRect();
    waveformCanvas.width = rect.width * dpr;
    waveformCanvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const data = new Uint8Array(analyser.fftSize);

    function frame() {
      animationFrame = requestAnimationFrame(frame);
      analyser.getByteTimeDomainData(data);
      ctx.clearRect(0, 0, rect.width, rect.height);
      ctx.lineWidth = 1.6;
      ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--accent");
      ctx.beginPath();
      const slice = rect.width / data.length;
      let x = 0;
      for (let i = 0; i < data.length; i++) {
        const v = data[i] / 128.0;
        const y = (v * rect.height) / 2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        x += slice;
      }
      ctx.stroke();
    }
    frame();
  }

  function stopWaveform() {
    if (animationFrame) cancelAnimationFrame(animationFrame);
    animationFrame = null;
    const ctx = waveformCanvas.getContext("2d");
    ctx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);
  }

  // ---------- Recording ----------
  async function startRecording() {
    clearError();
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      showError("Microphone access was denied or is unavailable. You can upload a .wav file instead.");
      return;
    }

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(mediaStream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);

    recordedChunks = [];
    mediaRecorder = new MediaRecorder(mediaStream);
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) recordedChunks.push(e.data); };
    mediaRecorder.onstop = onRecordingStopped;
    mediaRecorder.start();

    isPaused = false;
    elapsedMs = 0;
    timerInterval = setInterval(() => {
      if (!isPaused) {
        elapsedMs += 200;
        recordTimerEl.textContent = formatTimer(elapsedMs);
      }
    }, 200);

    recordHint.style.display = "none";
    waveformCanvas.style.display = "block";
    liveControls.style.display = "flex";
    uploadRow.style.display = "none";
    micBtn.classList.add("is-recording");
    micBtn.setAttribute("aria-label", "Recording in progress");
    recordStatusLabel.textContent = "Listening…";
    setStatus("active", "Recording");
    drawWaveform();
  }

  function togglePause() {
    if (!mediaRecorder) return;
    if (mediaRecorder.state === "recording") {
      mediaRecorder.pause();
      isPaused = true;
      pauseBtn.textContent = "Resume";
      recordStatusLabel.textContent = "Paused";
    } else if (mediaRecorder.state === "paused") {
      mediaRecorder.resume();
      isPaused = false;
      pauseBtn.textContent = "Pause";
      recordStatusLabel.textContent = "Listening…";
    }
  }

  function stopRecording() {
    if (!mediaRecorder) return;
    mediaRecorder.stop();
    clearInterval(timerInterval);
    mediaStream.getTracks().forEach((t) => t.stop());
    if (audioContext) audioContext.close();
    stopWaveform();
    micBtn.classList.remove("is-recording");
    micBtn.setAttribute("aria-label", "Start recording");
    liveControls.style.display = "none";
    waveformCanvas.style.display = "none";
    recordStatusLabel.textContent = "Not recording";
    pauseBtn.textContent = "Pause";
  }

  function onRecordingStopped() {
    recordedBlob = new Blob(recordedChunks, { type: "audio/webm" });
    recordedSource = "Microphone recording";
    recordedDurationSec = elapsedMs / 1000;
    presentReview(recordedBlob, "recording.webm");
  }

  // ---------- Upload ----------
  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (!file) return;
    clearError();
    recordedBlob = file;
    recordedSource = "Uploaded file";
    recordedDurationSec = null;
    presentReview(file, file.name);
  });

  function presentReview(blob, filename) {
    const url = URL.createObjectURL(blob);
    audioPreview.src = url;
    audioPreview.onloadedmetadata = () => {
      const d = isFinite(audioPreview.duration) ? audioPreview.duration : recordedDurationSec;
      previewDuration.textContent = d ? `${d.toFixed(1)}s` : "Unknown";
    };
    previewSource.textContent = recordedSource;
    reviewRow.style.display = "block";
    recordHint.style.display = "none";
    uploadRow.style.display = "none";
    recordTimerEl.textContent = recordedDurationSec ? formatTimer(recordedDurationSec * 1000) : "00:00";
    setStatus("idle", "Ready to analyze");
  }

  function resetToIdle() {
    recordedBlob = null;
    recordedSource = null;
    recordedDurationSec = null;
    fileInput.value = "";
    audioPreview.removeAttribute("src");
    reviewRow.style.display = "none";
    uploadRow.style.display = "block";
    recordHint.style.display = "block";
    recordTimerEl.textContent = "00:00";
    clearError();
    setStatus("idle", "Awaiting recording");
    stateRecord.style.display = "block";
    stateAnalyzing.style.display = "none";
    stateResults.style.display = "none";
    el("compare-link").style.display = "none";
    initMeta();
  }

  micBtn.addEventListener("click", () => {
    if (mediaRecorder && mediaRecorder.state === "recording") return;
    startRecording();
  });
  pauseBtn.addEventListener("click", togglePause);
  stopBtn.addEventListener("click", stopRecording);
  rerecordBtn.addEventListener("click", resetToIdle);
  newScreeningBtn.addEventListener("click", resetToIdle);

  // ---------- Analysis ----------
  const STAGE_ORDER = ["quality", "processing", "features", "model", "results"];

  function setStageState(stageKey, state) {
    const row = document.querySelector(`.stage-row[data-stage="${stageKey}"]`);
    if (!row) return;
    row.classList.remove("done", "active");
    if (state) row.classList.add(state);
  }

  function resetStages() {
    STAGE_ORDER.forEach((s) => setStageState(s, null));
  }

  async function runStageAnimation() {
    // Purely visual pacing; the real work happens in the API call running in parallel.
    for (let i = 0; i < STAGE_ORDER.length - 1; i++) {
      setStageState(STAGE_ORDER[i], "active");
      await new Promise((r) => setTimeout(r, 550));
      setStageState(STAGE_ORDER[i], "done");
    }
    setStageState(STAGE_ORDER[STAGE_ORDER.length - 1], "active");
  }

  analyzeBtn.addEventListener("click", async () => {
    if (!recordedBlob) return;
    clearError();
    stateRecord.style.display = "none";
    stateAnalyzing.style.display = "block";
    resetStages();
    setStatus("active", "Analyzing");

    const filename = recordedSource === "Uploaded file" ? (fileInput.files[0]?.name || "upload.wav") : "recording.webm";

    try {
      const [response] = await Promise.all([
        apiSubmitScreening(recordedBlob, filename, patientIdInput.value.trim()),
        runStageAnimation(),
      ]);
      setStageState("results", "done");
      await new Promise((r) => setTimeout(r, 250));

      if (response.status === "rejected") {
        setStatus("caution", "Recording rejected");
        stateAnalyzing.style.display = "none";
        stateRecord.style.display = "block";
        showError(response.message);
        return;
      }

      renderResults(response);
      stateAnalyzing.style.display = "none";
      stateResults.style.display = "block";
      setStatus("active", "Screening complete");
    } catch (err) {
      stateAnalyzing.style.display = "none";
      stateRecord.style.display = "block";
      setStatus("caution", "Analysis failed");
      showError(err.message || "Something went wrong while analyzing this recording.");
    }
  });

  function renderResults(response) {
    const { result, audio, features } = response;
    const pct = Math.round(result.probability * 100);
    const circumference = 289; // 2 * pi * 46, matches SVG r=46

    const ringFill = el("ring-fill");
    ringFill.style.strokeDashoffset = String(circumference - (circumference * pct) / 100);
    ringFill.style.stroke = pct >= 50
      ? getComputedStyle(document.documentElement).getPropertyValue("--elevated")
      : getComputedStyle(document.documentElement).getPropertyValue("--accent");

    el("ring-value").textContent = `${pct}%`;

    const badge = el("result-badge");
    if (result.label === "parkinsonian") {
      badge.className = "badge badge-elevated";
      badge.textContent = "Elevated pattern indication";
    } else {
      badge.className = "badge badge-accent";
      badge.textContent = "Typical pattern indication";
    }

    el("result-label").textContent = result.label_display;
    el("result-sentence").textContent =
      result.label === "parkinsonian"
        ? "The recorded voice shows a model-predicted pattern associated with Parkinson's disease."
        : "The recorded voice shows a model-predicted pattern consistent with typical, healthy voice characteristics.";

    const grid = el("summary-grid");
    grid.innerHTML = "";

    const durationTile = document.createElement("div");
    durationTile.className = "metric-tile";
    durationTile.innerHTML = `<div class="metric-label">Recording duration</div><div class="metric-value">${audio.duration_sec}<span class="metric-unit">s</span></div>`;
    grid.appendChild(durationTile);

    Object.entries(features).forEach(([key, f]) => {
      const tile = document.createElement("div");
      tile.className = "metric-tile";
      tile.innerHTML = `<div class="metric-label">${f.label}</div><div class="metric-value">${f.value}${f.unit ? `<span class="metric-unit">${f.unit}</span>` : ""}</div>`;
      grid.appendChild(tile);
    });

    const compareLink = el("compare-link");
    const pid = response.patient_id;
    if (pid) {
      compareLink.href = `compare.html?patient=${encodeURIComponent(pid)}`;
      compareLink.style.display = "inline-flex";
    } else {
      compareLink.style.display = "none";
    }
  }

  initMeta();
})();
