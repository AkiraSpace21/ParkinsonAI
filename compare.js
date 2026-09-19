(() => {
  const patientSelect = document.getElementById("patient-select");
  const noPatientsState = document.getElementById("no-patients-state");
  const compareContent = document.getElementById("compare-content");
  const trendWrap = document.getElementById("trend-chart-wrap");
  const trendCount = document.getElementById("trend-count");
  const earlierSelect = document.getElementById("earlier-select");
  const laterSelect = document.getElementById("later-select");
  const resultGrid = document.getElementById("result-comparison-grid");
  const featureBody = document.getElementById("feature-diff-body");

  let currentScreenings = [];

  function fmtDate(iso) {
    return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  }
  function fmtShortDate(iso) {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  async function loadPatients() {
    let patients = [];
    try {
      patients = await apiGetPatients();
    } catch (err) {
      showToast(err.message || "Could not load patients.");
    }

    if (patients.length === 0) {
      noPatientsState.style.display = "block";
      compareContent.style.display = "none";
      return;
    }
    noPatientsState.style.display = "none";

    patientSelect.innerHTML = '<option value="">Select a patient…</option>';
    patients.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.patient_id;
      opt.textContent = `${p.patient_id} (${p.screening_count} screening${p.screening_count === 1 ? "" : "s"})`;
      patientSelect.appendChild(opt);
    });

    const params = new URLSearchParams(location.search);
    const preselect = params.get("patient");
    if (preselect && patients.some((p) => p.patient_id === preselect)) {
      patientSelect.value = preselect;
      await loadPatientScreenings(preselect);
    }
  }

  async function loadPatientScreenings(patientId) {
    try {
      currentScreenings = await apiGetPatientScreenings(patientId);
    } catch (err) {
      showToast(err.message || "Could not load screenings for this patient.");
      currentScreenings = [];
    }

    if (currentScreenings.length === 0) {
      compareContent.style.display = "none";
      return;
    }

    compareContent.style.display = "block";
    trendCount.textContent = `${currentScreenings.length} screening${currentScreenings.length === 1 ? "" : "s"}`;

    populateTimePointSelects();
    renderTrendChart();
    renderComparison();
  }

  function populateTimePointSelects() {
    const optionsHtml = currentScreenings
      .map((s, i) => `<option value="${i}">${fmtDate(s.timestamp)} — ${Math.round(s.result.probability * 100)}%</option>`)
      .join("");
    earlierSelect.innerHTML = optionsHtml;
    laterSelect.innerHTML = optionsHtml;
    earlierSelect.selectedIndex = 0;
    laterSelect.selectedIndex = currentScreenings.length - 1;
  }

  function renderTrendChart() {
    const width = Math.max(360, currentScreenings.length * 70);
    const height = 160;
    const padX = 28;
    const padY = 20;
    const plotW = width - padX * 2;
    const plotH = height - padY * 2;

    const points = currentScreenings.map((s, i) => {
      const x = padX + (currentScreenings.length === 1 ? plotW / 2 : (i / (currentScreenings.length - 1)) * plotW);
      const y = padY + plotH - (s.result.probability * plotH);
      return { x, y, s };
    });

    const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
    const midY = padY + plotH / 2;

    const circles = points
      .map(
        (p) => `
      <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="4" fill="var(--surface)" stroke="var(--accent)" stroke-width="2"/>
      <text x="${p.x.toFixed(1)}" y="${height - 4}" text-anchor="middle" font-size="10" fill="var(--ink-faint)" font-family="var(--font-mono)">${fmtShortDate(p.s.timestamp)}</text>
    `
      )
      .join("");

    trendWrap.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" style="min-width:${width}px;">
        <line x1="${padX}" y1="${padY}" x2="${padX}" y2="${padY + plotH}" stroke="var(--border)" stroke-width="1"/>
        <line x1="${padX}" y1="${padY + plotH / 2}" x2="${width - padX}" y2="${padY + plotH / 2}" stroke="var(--border)" stroke-width="1" stroke-dasharray="3 3"/>
        <text x="${padX - 6}" y="${padY + 4}" text-anchor="end" font-size="10" fill="var(--ink-faint)" font-family="var(--font-mono)">100%</text>
        <text x="${padX - 6}" y="${midY + 3}" text-anchor="end" font-size="10" fill="var(--ink-faint)" font-family="var(--font-mono)">50%</text>
        <text x="${padX - 6}" y="${padY + plotH + 3}" text-anchor="end" font-size="10" fill="var(--ink-faint)" font-family="var(--font-mono)">0%</text>
        <path d="${pathD}" fill="none" stroke="var(--accent)" stroke-width="2"/>
        ${circles}
      </svg>
    `;
  }

  function resultCard(screening, positionLabel) {
    const pct = Math.round(screening.result.probability * 100);
    const badgeClass = screening.result.label === "parkinsonian" ? "badge-elevated" : "badge-accent";
    const badgeText = screening.result.label === "parkinsonian" ? "Elevated pattern" : "Typical pattern";
    return `
      <div class="card" style="margin:0;">
        <div class="card-eyebrow">${positionLabel}</div>
        <div style="font-family:var(--font-mono); font-size:12px; color:var(--ink-faint); margin-bottom:8px;">${fmtDate(screening.timestamp)}</div>
        <div class="badge ${badgeClass}" style="margin-bottom:10px;">${badgeText}</div>
        <div style="font-family:var(--font-mono); font-size:28px; font-weight:600;">${pct}%</div>
        <div style="font-size:12.5px; color:var(--ink-faint);">Estimated probability</div>
      </div>
    `;
  }

  function renderComparison() {
    const earlier = currentScreenings[Number(earlierSelect.value)];
    const later = currentScreenings[Number(laterSelect.value)];
    if (!earlier || !later) return;

    const deltaPts = Math.round((later.result.probability - earlier.result.probability) * 100);
    const arrow = deltaPts > 0 ? "▲" : deltaPts < 0 ? "▼" : "→";
    const deltaLabel = deltaPts === 0 ? "No change" : `${arrow} ${Math.abs(deltaPts)} pts`;

    resultGrid.innerHTML = `
      ${resultCard(earlier, "Earlier")}
      <div style="text-align:center;">
        <div class="badge badge-info mono">${deltaLabel}</div>
        <div style="font-size:11.5px; color:var(--ink-faint); margin-top:6px;">probability change</div>
      </div>
      ${resultCard(later, "Later")}
    `;

    featureBody.innerHTML = "";
    const keys = Array.from(
      new Set([...Object.keys(earlier.features || {}), ...Object.keys(later.features || {})])
    );

    keys.forEach((key) => {
      const ef = earlier.features[key];
      const lf = later.features[key];
      if (!ef || !lf) return;

      const change = lf.value - ef.value;
      const arrowIcon = change > 0 ? "↑" : change < 0 ? "↓" : "→";
      const changeText = `${arrowIcon} ${Math.abs(change).toFixed(3)}${lf.unit ? " " + lf.unit : ""}`;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td data-label="Feature">${ef.label}</td>
        <td class="mono" data-label="Earlier">${ef.value}${ef.unit ? " " + ef.unit : ""}</td>
        <td class="mono" data-label="Later">${lf.value}${lf.unit ? " " + lf.unit : ""}</td>
        <td class="mono" data-label="Change">${changeText}</td>
      `;
      featureBody.appendChild(tr);
    });
  }

  patientSelect.addEventListener("change", () => {
    if (patientSelect.value) loadPatientScreenings(patientSelect.value);
    else compareContent.style.display = "none";
  });
  earlierSelect.addEventListener("change", renderComparison);
  laterSelect.addEventListener("change", renderComparison);

  loadPatients();
})();
