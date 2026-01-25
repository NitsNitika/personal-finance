document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ delete_income.js loaded");

  const rows = document.querySelectorAll(".income-row");
  const toggleBtn = document.getElementById("toggleView");

  if (!toggleBtn || rows.length === 0) return;

  const LIMIT = 5;
  let expanded = false;

  function updateView() {
    rows.forEach((row, index) => {
      row.style.display =
        expanded || index < LIMIT ? "table-row" : "none";
    });

    toggleBtn.textContent = expanded ? "View Less" : "View More";
  }

  toggleBtn.addEventListener("click", (e) => {
    e.preventDefault();
    expanded = !expanded;
    updateView();
  });

  if (rows.length <= LIMIT) {
    toggleBtn.style.display = "none";
  }

  updateView();
});
