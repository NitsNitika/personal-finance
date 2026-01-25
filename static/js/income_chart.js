document.addEventListener("DOMContentLoaded", () => {
  const canvas = document.getElementById("monthlyIncomeChart");
  if (!canvas) return;

  if (window.monthlyIncomeChart instanceof Chart) {
    window.monthlyIncomeChart.destroy();
  }

  if (!monthlyIncome || Object.keys(monthlyIncome).length === 0) return;

  const labels = [];
  const data = [];

  Object.keys(monthlyIncome)
    .sort()
    .forEach(key => {
      const [year, month] = key.split("-");
      const date = new Date(year, month - 1);
      labels.push(
        date.toLocaleString("en-IN", { month: "short", year: "numeric" })
      );
      data.push(monthlyIncome[key]);
    });

  window.monthlyIncomeChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Monthly Income (₹)",
        data,
        backgroundColor: "rgba(34,197,94,0.45)",
        hoverBackgroundColor: "rgba(34,197,94,0.7)",
        borderRadius: 10,
        barThickness: 60
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: v => "₹" + v.toLocaleString("en-IN")
          }
        }
      }
    }
  });
});
