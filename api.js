// Thin wrapper around the FastAPI backend. Change API_BASE if the backend
// is served from a different origin than the frontend.
const API_BASE = "";

async function apiHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  return res.json();
}

async function apiSubmitScreening(blob, filename, patientId) {
  const form = new FormData();
  form.append("audio", blob, filename || "recording.wav");
  if (patientId) form.append("patient_id", patientId);
  const res = await fetch(`${API_BASE}/api/screening`, { method: "POST", body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message = data.detail || "The server could not process this recording.";
    throw new Error(message);
  }
  return data;
}

async function apiGetHistory() {
  const res = await fetch(`${API_BASE}/api/history`);
  if (!res.ok) throw new Error("Could not load screening history.");
  const data = await res.json();
  return data.screenings || [];
}

async function apiGetPatients() {
  const res = await fetch(`${API_BASE}/api/patients`);
  if (!res.ok) throw new Error("Could not load patient list.");
  const data = await res.json();
  return data.patients || [];
}

async function apiGetPatientScreenings(patientId) {
  const res = await fetch(`${API_BASE}/api/patients/${encodeURIComponent(patientId)}/screenings`);
  if (!res.ok) throw new Error("Could not load this patient's screenings.");
  const data = await res.json();
  return data.screenings || [];
}

async function apiDeleteHistoryItem(id) {
  const res = await fetch(`${API_BASE}/api/history/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Could not delete this screening.");
  return res.json();
}

function showToast(message) {
  let toast = document.querySelector(".toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove("visible"), 2800);
}
