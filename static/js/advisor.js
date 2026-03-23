// ================== GLOBAL ==================
let riskProfile = window.riskProfile || "LOW";
let strategies = window.strategies || {};


// ================== SMART ADVISOR TABS ==================
function showTab(type, el = null) {

    // active TAB UI
    document.querySelectorAll(".time-btn").forEach(b => b.classList.remove("active"));
    if (el) el.classList.add("active");

    const container = document.getElementById("strategy-container");
    const banner = document.getElementById("recommended-banner");

    container.innerHTML = "";

    if (!strategies[type]) {
        container.innerHTML = "<p>No strategies available</p>";
        return;
    }


    // ================== RISK DETECT ==================
    const risk = riskProfile.includes("HIGH") ? "high"
                : riskProfile.includes("MEDIUM") ? "medium"
                : "low";
    

                // 🔥 APPLY RISK COLOR TO TIME CARD
    const timeCard = document.querySelector(".time-card");

    timeCard.classList.remove("low", "medium", "high");
    timeCard.classList.add(risk);


    // ================== BANNER ==================
    let recommendedText = "";

    if (risk === "high") {
        recommendedText = "🚀 Recommended for YOU: High growth investments (Long Term)";
    } else if (risk === "medium") {
        recommendedText = "⚖ Recommended for YOU: Balanced investments (Medium Term)";
    } else {
        recommendedText = "🛡 Recommended for YOU: Safe investments (Short Term)";
    }

    banner.innerHTML = `<div class="banner-box">${recommendedText}</div>`;

    // ================== CARDS ==================
    strategies[type].forEach((item, index) => {

        let badge = "";
        let highlightClass = "";

        if (
            (risk === "high" && type === "long" && index === 0) ||
            (risk === "medium" && type === "medium" && index === 0) ||
            (risk === "low" && type === "short" && index === 0)
        ) {
            badge = `<span class="badge best">⭐ Best</span>`;
            highlightClass = "best-card";
        }
        else if (index === 1) {
            badge = `<span class="badge recommended">✔ Recommended</span>`;
        }
        else {
            badge = `<span class="badge safe">Safe</span>`;
        }

        // ================== ICONS ==================
        let icon = "bi-graph-up";

        if (item.key.includes("gold")) icon = "bi-currency-dollar";
        if (item.key.includes("ppf")) icon = "bi-piggy-bank";
        if (item.key.includes("bills")) icon = "bi-bank";
        if (item.key.includes("bond")) icon = "bi-building";
        if (item.key.includes("liquid")) icon = "bi-droplet";
        if (item.key.includes("equity")) icon = "bi-bar-chart";

        // ================== CARD ==================
        const card = document.createElement("a");
        card.href = `/investment/${type}/${item.key}`;
        card.className = `advisor-card ${highlightClass}`;

        card.innerHTML = `
            <div class="card-header">
                <i class="bi ${icon}"></i>
                <h5>${item.title}</h5>
                ${badge}
            </div>
            <p class="subtitle">Click for detailed analysis →</p>
        `;

        container.appendChild(card);
    });
}


// ================== INVESTMENT PAGE TABS ==================
function showInvestmentTab(id, el) {

    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tabs button").forEach(b => b.classList.remove("active"));

    document.getElementById(id).classList.add("active");
    el.classList.add("active");
}


// ================== COMPARE ==================
function addToCompare(title, returns, risk) {

    let items = JSON.parse(localStorage.getItem("compare")) || [];

    if (items.find(i => i.title === title)) {
        alert("Already added!");
        return;
    }

    if (items.length >= 2) {
        alert("Only 2 investments allowed");
        return;
    }

    items.push({ title, returns, risk });
    localStorage.setItem("compare", JSON.stringify(items));

    if (items.length === 2) {
        window.location.href = "/compare";
    } else {
        alert("Added! Select one more investment.");
    }
}


// ================== CLEAR COMPARE ==================
function clearCompare() {
    localStorage.removeItem("compare");
    location.reload();
}


// ================== AUTO LOAD ==================
document.addEventListener("DOMContentLoaded", () => {
    showTab("short");
});
