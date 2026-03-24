let deleteId = null;

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
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ title, target, priority, date })
    })
    .then(res => res.json())
    .then(data => {

        if (data.error) {
            openErrorModal(data.error);
        } else {
            closeModal();
            showToast("✅ Goal created successfully");
            setTimeout(() => location.reload(), 800);
        }
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
        } else {
            input.value = "";
            showToast("💰 Money added successfully");
            setTimeout(() => location.reload(), 700);
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
        closeDeleteModal();
        showToast("❌ Goal deleted successfully");
        setTimeout(() => location.reload(), 700);
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
    toast.innerText = msg;
    toast.classList.add("show");

    setTimeout(() => toast.classList.remove("show"), 2000);
}