(() => {
  "use strict";
  const root = document.documentElement;
  const themeToggle = document.getElementById("theme-toggle");
  const themeIcon = document.getElementById("theme-icon");
  const fontButtons = document.querySelectorAll(".control-button[data-font-size]");
  const applyTheme = (value) => {
    const theme = value === "dark" ? "dark" : "light";
    root.dataset.theme = theme;
    if (themeToggle) themeToggle.setAttribute("aria-pressed", String(theme === "dark"));
    if (themeIcon) themeIcon.textContent = theme === "dark" ? "☀" : "☾";
    try { localStorage.setItem("reotoi-theme", theme); } catch (_) {}
  };
  const applyFontSize = (value) => {
    const size = ["small", "medium", "large"].includes(value) ? value : "medium";
    root.dataset.fontSize = size;
    fontButtons.forEach((button) => button.classList.toggle("is-active", button.dataset.fontSize === size));
    try { localStorage.setItem("reotoi-font-size", size); } catch (_) {}
  };
  try {
    applyTheme(localStorage.getItem("reotoi-theme") || root.dataset.theme);
    applyFontSize(localStorage.getItem("reotoi-font-size") || root.dataset.fontSize);
  } catch (_) { applyTheme("light"); applyFontSize("medium"); }
  themeToggle?.addEventListener("click", () => applyTheme(root.dataset.theme === "dark" ? "light" : "dark"));
  fontButtons.forEach((button) => button.addEventListener("click", () => applyFontSize(button.dataset.fontSize)));
})();
