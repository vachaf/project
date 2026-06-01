/* theme-toggle.js
   Pure JS theme switcher. No external CDN dependency. */
(function () {
  var KEY = "sic-theme";

  function getSavedTheme() {
    try {
      return window.localStorage.getItem(KEY);
    } catch (_) {
      return null;
    }
  }

  function saveTheme(value) {
    try {
      window.localStorage.setItem(KEY, value);
    } catch (_) {
      // Ignore storage failures. Theme toggle should remain non-fatal.
    }
  }

  function isDarkTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark";
  }

  function applyTheme(value) {
    if (value === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }

  function syncIcon() {
    var btns = document.querySelectorAll(".theme-toggle");
    var isDark = isDarkTheme();
    for (var i = 0; i < btns.length; i++) {
      btns[i].textContent = isDark ? "☀" : "☾";
      btns[i].title = isDark ? "라이트 모드로 전환" : "다크 모드로 전환";
      btns[i].setAttribute("aria-label", btns[i].title);
    }
  }

  applyTheme(getSavedTheme());

  window.toggleTheme = function () {
    var next = isDarkTheme() ? "light" : "dark";
    applyTheme(next);
    saveTheme(next);
    syncIcon();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", syncIcon, { once: true });
  } else {
    syncIcon();
  }
})();
