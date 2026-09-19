(() => {
  const micSelect = document.getElementById("mic-select");
  const requestMicBtn = document.getElementById("request-mic-btn");
  const themeLightBtn = document.getElementById("theme-light");
  const themeDarkBtn = document.getElementById("theme-dark");
  const rememberToggle = document.getElementById("remember-theme-toggle");

  function applyThemeButtons() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    themeLightBtn.classList.toggle("active", !isDark);
    themeDarkBtn.classList.toggle("active", isDark);
  }

  function setTheme(theme) {
    if (theme === "dark") document.documentElement.setAttribute("data-theme", "dark");
    else document.documentElement.removeAttribute("data-theme");
    if (rememberToggle.checked) {
      localStorage.setItem("pd-app-theme", theme);
    }
    applyThemeButtons();
  }

  themeLightBtn.addEventListener("click", () => setTheme("light"));
  themeDarkBtn.addEventListener("click", () => setTheme("dark"));
  rememberToggle.addEventListener("change", () => {
    if (!rememberToggle.checked) localStorage.removeItem("pd-app-theme");
    else localStorage.setItem("pd-app-theme", document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light");
  });

  async function populateMicList() {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const devices = await navigator.mediaDevices.enumerateDevices();
    const mics = devices.filter((d) => d.kind === "audioinput");
    micSelect.innerHTML = '<option value="">Default device</option>';
    mics.forEach((mic, i) => {
      const opt = document.createElement("option");
      opt.value = mic.deviceId;
      opt.textContent = mic.label || `Microphone ${i + 1}`;
      micSelect.appendChild(opt);
    });
  }

  requestMicBtn.addEventListener("click", async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      await populateMicList();
      showToast("Microphone access granted.");
    } catch (err) {
      showToast("Microphone access was denied.");
    }
  });

  applyThemeButtons();
  populateMicList();
})();
