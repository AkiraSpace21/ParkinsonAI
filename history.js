(() => {
  const tbody = document.getElementById("history-body");
  const emptyState = document.getElementById("empty-state");
  const tableWrap = document.getElementById("table-wrap");
  const searchInput = document.getElementById("search-input");
  const rowCount = document.getElementById("row-count");

  let allScreenings = [];

  function formatDate(iso) {
    return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  }

  function statusBadge(record) {
    if (record.status === "rejected") return '<span class="badge badge-caution">Rejected</span>';
    if (record.result?.label === "parkinsonian") return '<span class="badge badge-elevated">Elevated pattern</span>';
    return '<span class="badge badge-accent">Typical pattern</span>';
  }

  function render(list) {
    tbody.innerHTML = "";
    rowCount.textContent = `${list.length} screening${list.length === 1 ? "" : "s"}`;

    if (list.length === 0) {
      tableWrap.style.display = "none";
      emptyState.style.display = "block";
      return;
    }
    tableWrap.style.display = "block";
    emptyState.style.display = "none";

    list.forEach((record) => {
      const tr = document.createElement("tr");

      const duration = record.audio ? `${record.audio.duration_sec}s` : "—";
      const resultText = record.status === "rejected" ? "Rejected" : record.result.label_display;
      const probText = record.status === "rejected" ? "—" : `${Math.round(record.result.probability * 100)}%`;

      const patientCell = record.patient_id
        ? `<a href="compare.html?patient=${encodeURIComponent(record.patient_id)}">${record.patient_id}</a>`
        : `<span style="color:var(--ink-faint);">—</span>`;

      tr.innerHTML = `
        <td class="mono" data-label="Screening ID">${record.screening_id}</td>
        <td class="mono" data-label="Patient ID">${patientCell}</td>
        <td data-label="Date">${formatDate(record.timestamp)}</td>
        <td class="mono" data-label="Duration">${duration}</td>
        <td data-label="Result">${resultText}</td>
        <td class="mono" data-label="Probability">${probText}</td>
        <td data-label="Status">${statusBadge(record)}</td>
        <td data-label="">
          <div class="row-actions">
            <button data-action="delete" data-id="${record.screening_id}" class="danger">Delete</button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  function applyFilter() {
    const q = searchInput.value.trim().toLowerCase();
    if (!q) { render(allScreenings); return; }
    const filtered = allScreenings.filter((r) => {
      const resultText = r.status === "rejected" ? "rejected" : r.result.label_display.toLowerCase();
      const patientText = (r.patient_id || "").toLowerCase();
      return (
        r.screening_id.toLowerCase().includes(q) ||
        resultText.includes(q) ||
        patientText.includes(q)
      );
    });
    render(filtered);
  }

  async function load() {
    try {
      allScreenings = await apiGetHistory();
      render(allScreenings);
    } catch (err) {
      showToast(err.message || "Could not load history.");
      render([]);
    }
  }

  tbody.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action='delete']");
    if (!btn) return;
    const id = btn.dataset.id;
    try {
      await apiDeleteHistoryItem(id);
      allScreenings = allScreenings.filter((r) => r.screening_id !== id);
      applyFilter();
      showToast("Screening deleted.");
    } catch (err) {
      showToast(err.message || "Could not delete screening.");
    }
  });

  searchInput.addEventListener("input", applyFilter);

  load();
})();
