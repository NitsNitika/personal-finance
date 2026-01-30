const ctx = document.getElementById("savingsChart").getContext("2d");

// 🔴 Destroy old chart if exists
if (window.savingsChartInstance) {
  window.savingsChartInstance.destroy();
}

// 🔢 Find max value dynamically
const maxValue = Math.max(
  ...chartData.income,
  ...chartData.expense,
  ...chartData.savings
);

// 🟢 Create new chart
window.savingsChartInstance = new Chart(ctx, {
  type: "bar",
  data: {
    labels: chartData.labels,
    datasets: [
      {
        label: "Income",
        data: chartData.income,
        backgroundColor: "#5b8def",
        borderRadius: 10,
        barThickness: 50,
      },
      {
        label: "Expenses",
        data: chartData.expense,
        backgroundColor: "#f26c6c",
        borderRadius: 10,
        barThickness: 50,
      },
      {
        label: "Savings",
        data: chartData.savings,
        backgroundColor: "#63c97a",
        borderRadius: 10,
        barThickness: 50,
      }
    ]
  },
  options: {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    y: {
      min: 10000,                 // 👈 start at 10,000
      max: Math.ceil(maxValue / 100000) * 100000, 
      ticks: {
        stepSize: 50000,          // 👈 fixed steps
        callback: value => "₹ " + value.toLocaleString()
      },
      grid: {
        color: "#eee"
      }
    },
    x: {
      grid: { display: false }
    }
  },
  plugins: {
    legend: { position: "top" }
  }
}
})