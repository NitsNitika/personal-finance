console.log("GOALS JS LOADED");

let deleteId = null;

/* ================= INIT ================= */
document.addEventListener("DOMContentLoaded", function () {

    const btn = document.getElementById("saveGoalBtn");

    if (btn) {
        btn.addEventListener("click", function () {
            createGoal();
        });
    }
});

/* ================= CREATE GOAL ================= */
function createGoal() {

    const title = document.getElementById("title").value.trim();
    const target = document.getElementById("target").value.trim();
    const priority = document.getElementById("priority").value;
    const date = document.getElementById("date").value;

    if (!title || !target) {
        openErrorModal("Please fill all fields");
        return;
    }

    fetch("/add_goal", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ title, target, priority, date })
    })
    .then(res => res.json())
    .then(data => {

        if (data.error) {
            openErrorModal(data.error);
            return;
        }

        // CLOSE MODAL
        closeModal();

        // SHOW SUCCESS
        document.getElementById("successText").innerText = "Goal created successfully!";
        document.getElementById("successModal").style.display = "flex";

        // CLEAR INPUTS
        document.getElementById("title").value = "";
        document.getElementById("target").value = "";
        document.getElementById("date").value = "";
    })
    .catch(() => {
        showToast("❌ Failed to create goal");
    });
}

/* ================= ADD MONEY ================= */
function addMoney(id) {

    const input = document.getElementById(`amount-${id}`);
    const amount = parseFloat(input.value);

    if (!amount || amount <= 0) {
        openErrorModal("Enter valid amount");
        return;
    }

    fetch(`/update_goal/${id}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ amount })
    })
    .then(res => res.json())
    .then(data => {

        if (data.error) {
            openErrorModal(data.error);
            return;
        }

        const savedEl = document.getElementById(`saved-${id}`);
        const targetEl = document.getElementById(`target-${id}`);

        let saved = parseFloat(savedEl.innerText);
        let target = parseFloat(targetEl.innerText);

        saved += amount;
        savedEl.innerText = saved;

        // ✅ UPDATE PROGRESS
        let percent = target > 0 ? (saved / target) * 100 : 0;
        percent = Math.min(percent, 100);

        const card = document.getElementById(`goal-${id}`);

        if (card) {
            card.querySelector(".progress").style.width = percent + "%";
            card.querySelector(".goal-header span").innerText = Math.round(percent) + "%";
        }

        // ✅ UPDATE TOTAL SAVINGS
        const totalEl = document.getElementById("totalSavings");
        let currentTotal = parseFloat(totalEl.innerText.replace(/[^\d.]/g, "")) || 0;
        currentTotal += amount;
        totalEl.innerText = "₹" + currentTotal.toFixed(1);

        // ✅ CLEAR INPUT
        input.value = "";
        input.defaultValue = "";
        input.placeholder = "₹ Add money";
        input.blur();

        // ✅ SHOW SUCCESS MODAL
        document.getElementById("successText").innerText = "Money added successfully!";
        document.getElementById("successModal").style.display = "flex";

        /* ================= 🎉 GOAL ACHIEVED ================= */
        if (saved >= target) {

            // disable input + button
            if (input) input.disabled = true;

            const addBtn = card.querySelector("button");
            if (addBtn) addBtn.disabled = true;

            // add message only once
            if (!card.querySelector(".goal-complete")) {
                card.insertAdjacentHTML("beforeend", `
                    <div class="goal-complete">
                        🎉 Goal Achieved!
                    </div>
                `);
            }
        }

    });
}

/* ================= DELETE ================= */
function deleteGoal(id) {
    deleteId = id;
    document.getElementById("deleteModal").style.display = "flex";
}

function confirmDelete() {
    fetch(`/delete_goal/${deleteId}`, { method: "POST" })
    .then(() => {

        const el = document.getElementById(`goal-${deleteId}`);
        if (el) el.remove();

        closeDeleteModal();
        showToast("❌ Goal deleted successfully");
    });
}

function closeDeleteModal() {
    document.getElementById("deleteModal").style.display = "none";
}

/* ================= MODALS ================= */
function openModal() {
    document.getElementById("goalModal").style.display = "flex";
}

function closeModal() {
    document.getElementById("goalModal").style.display = "none";
}

function closeSuccessModal() {
    document.getElementById("successModal").style.display = "none";
}

/* ================= ERROR MODAL ================= */
function openErrorModal(msg) {
    document.querySelector(".error-text").innerText = msg;
    document.getElementById("errorModal").style.display = "flex";
}

function closeErrorModal() {
    document.getElementById("errorModal").style.display = "none";
}

/* ================= TOAST ================= */
function showToast(msg) {
    const toast = document.getElementById("toast");

    if (!toast) return;

    toast.innerText = msg;
    toast.classList.add("show");

    setTimeout(() => {
        toast.classList.remove("show");
    }, 2500);
}

/* ================= NAV ================= */
function goDashboard() {
    window.location.href = "/profile";
}