document.addEventListener("DOMContentLoaded", () => {
  const categoryFilter = document.getElementById("categoryFilter");
  const fromDate = document.getElementById("fromDate");
  const toDate = document.getElementById("toDate");

  const rows = document.querySelectorAll("tbody tr");

  function filterExpenses() {
    const category = categoryFilter.value;
    const from = fromDate.value;
    const to = toDate.value;

    rows.forEach(row => {
      const rowDate = row.children[0].innerText.split("-").reverse().join("-");
      const rowCategory = row.children[1].innerText;

      let show = true;

      if (category && rowCategory !== category) show = false;
      if (from && rowDate < from) show = false;
      if (to && rowDate > to) show = false;

      row.style.display = show ? "" : "none";
    });
  }

  categoryFilter.addEventListener("change", filterExpenses);
  fromDate.addEventListener("change", filterExpenses);
  toDate.addEventListener("change", filterExpenses);
});
