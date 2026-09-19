(() => {
  const savedTheme = localStorage.getItem("pd-app-theme");
  if (savedTheme === "dark") document.documentElement.setAttribute("data-theme", "dark");
})();

document.addEventListener("DOMContentLoaded", () => {
  const current = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".main-nav a").forEach((link) => {
    if (link.getAttribute("href") === current) link.classList.add("active");
  });

  const toggle = document.querySelector(".menu-toggle");
  const nav = document.querySelector(".main-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const isOpen = nav.style.display === "flex";
      nav.style.display = isOpen ? "none" : "flex";
      nav.style.flexDirection = "column";
      nav.style.position = "absolute";
      nav.style.top = "60px";
      nav.style.left = "0";
      nav.style.right = "0";
      nav.style.background = "var(--surface)";
      nav.style.borderBottom = "1px solid var(--border)";
      nav.style.padding = "8px";
      toggle.setAttribute("aria-expanded", String(!isOpen));
    });
  }
});
