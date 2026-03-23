// Dropdown → input sync
function toggleCustomGoal(){
  const select = document.getElementById("goalSelect");
  const input = document.getElementById("goalName");

  if(select.value === "Other"){
    input.value = "";
    input.focus();
  } else if(select.value){
    input.value = select.value;
  }
}

// Animate progress bars
document.querySelectorAll(".progress-bar").forEach(bar=>{
  const w = bar.getAttribute("data-width");
  setTimeout(()=> bar.style.width = w + "%", 200);
});

// Snooze helpers
function isSnoozed(goalId){
  const until = localStorage.getItem("snooze_"+goalId);
  return until && new Date(until) > new Date();
}

function snooze(goalId){
  const until = new Date();
  until.setHours(until.getHours()+24);
  localStorage.setItem("snooze_"+goalId, until.toISOString());
}

// Toast display
function showToast(alert){
  if(isSnoozed(alert.goal_id)) return;

  const c = document.getElementById("toast-container");
  const t = document.createElement("div");
  t.className = "toast " + alert.priority;

  t.innerHTML = `
    <div>${alert.msg}</div>
    <div class="actions">
      <button onclick="snooze(${alert.goal_id}); this.closest('.toast').remove();">
        Snooze 24h
      </button>
      <button onclick="this.closest('.toast').remove();">
        Dismiss
      </button>
    </div>
  `;

  c.appendChild(t);
  setTimeout(()=>t.remove(),8000);
}

// Show alerts sequentially
deadlineAlerts.forEach((a,i)=>{
  setTimeout(()=> showToast(a), i*700);
});

