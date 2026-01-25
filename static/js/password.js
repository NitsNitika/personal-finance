function checkStrength() {
    const pwd = document.getElementById("password").value;
    const meter = document.getElementById("strength");

    let strength = 0;
    if (pwd.length >= 8) strength++;
    if (pwd.match(/[A-Z]/)) strength++;
    if (pwd.match(/[a-z]/)) strength++;
    if (pwd.match(/[0-9]/)) strength++;
    if (pwd.match(/[@$!%*?&]/)) strength++;

    if (strength <= 2) {
        meter.innerText = "Weak Password";
        meter.style.color = "red";
    } else if (strength <= 4) {
        meter.innerText = "Medium Password";
        meter.style.color = "orange";
    } else {
        meter.innerText = "Strong Password";
        meter.style.color = "green";
    }
}
function startOtpTimer(seconds) {
    const timerElement = document.getElementById("timer");
    let remaining = seconds;

    const interval = setInterval(() => {
        const minutes = Math.floor(remaining / 60);
        const secs = remaining % 60;

        timerElement.textContent =
            String(minutes).padStart(2, "0") + ":" +
            String(secs).padStart(2, "0");

        if (remaining <= 0) {
            clearInterval(interval);
            timerElement.textContent = "Expired";
            timerElement.style.color = "red";
        }

        remaining--;
    }, 1000);
}
