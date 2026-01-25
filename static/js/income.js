const ctx = document.getElementById('incomeChart');

new Chart(ctx, {
    type: 'line',
    data: {
        labels: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug'],
        datasets: [{
            label: 'Monthly Income',
            data: [2000, 3000, 2800, 4200, 5000, 4800, 4100, 5500],
            borderColor: '#4a6cf7',
            backgroundColor: 'rgba(74,108,247,0.2)',
            tension: 0.4,
            fill: true
        }]
    }
});
