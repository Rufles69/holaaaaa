// dark mode init
if (localStorage.getItem("dark-mode") === "true") {
    document.documentElement.classList.add("dark");
  }
  document.getElementById("toggle-dark")?.addEventListener("click", () => {
    document.documentElement.classList.toggle("dark");
    localStorage.setItem("dark-mode", document.documentElement.classList.contains("dark"));
  });
  
  // menu toggle button (floating)
  const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.getElementById("toggle-menu");
  if (toggleBtn) {
    let open = true;
    toggleBtn.addEventListener("click", () => {
      open = !open;
      if (open) {
        sidebar.classList.remove("-translate-x-64");
        toggleBtn.textContent = "✖";
      } else {
        sidebar.classList.add("-translate-x-64");
        toggleBtn.textContent = "☰";
      }
    });
  }
  