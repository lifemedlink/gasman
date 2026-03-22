const listEl = document.getElementById("activityList");
const dateInput = document.getElementById("activityDate");

/* Default = today */
dateInput.valueAsDate = new Date();
loadActivity();

dateInput.addEventListener("change", loadActivity);

/* ================= LOAD ACTIVITY LIST ================= */
async function loadActivity() {
  listEl.innerHTML = "Loading...";

  try {
    const r = await fetch(
      `/user/activity/list?date=${dateInput.value}`,
      { credentials: "include" }
    );

    if (!r.ok) throw new Error("API error");

    const data = await r.json();
    listEl.innerHTML = "";

    if (!data.length) {
      listEl.innerHTML = "<p>No activity</p>";
      return;
    }

    data.forEach(t => {
      const card = document.createElement("div");
      card.className = "task-card";
      card.onclick = () => openActivityModal(t.task_id);

      card.innerHTML = `
        <div class="task-header">
          <b>${t.device_id}</b>
          <span class="badge badge-completed">${t.status}</span>
        </div>
        <div class="task-meta">
          Tracking: ${t.tracking_id}<br>
          Completed: ${t.completed_at}
        </div>
      `;

      listEl.appendChild(card);
    });

  } catch (e) {
    console.error(e);
    listEl.innerHTML =
      "<p style='color:red'>Error loading activity</p>";
  }
}

/* ================= OPEN ACTIVITY MODAL ================= */
async function openActivityModal(taskId) {
  try {
    const r = await fetch(`/user/activity/${taskId}`, {
      credentials: "include"
    });

    if (!r.ok) throw new Error("Detail API error");

    const d = await r.json();

    // Header
    document.getElementById("m_device").innerText = d.device_id;
    document.getElementById("m_tracking").innerText =
      `Tracking: ${d.tracking_id}`;

    const badge = document.getElementById("m_status");
    badge.innerText = d.status;
    badge.className = "status-pill";

    // Timeline
    const tl = document.getElementById("m_timeline");
    tl.innerHTML = "";

    d.timeline.forEach(i => {
      const row = document.createElement("div");
      row.className = "timeline-item";
      row.innerHTML = `
        <div class="timeline-time">${i.time}</div>
        <div class="timeline-label">${i.label}</div>
      `;
      tl.appendChild(row);
    });

    // 🔥 THIS WAS MISSING
    document.getElementById("activityModal").style.display = "flex";

  } catch (e) {
    console.error(e);
    alert("Failed to load activity details");
  }
}

/* ================= CLOSE MODAL ================= */
function closeActivityModal() {
  document.getElementById("activityModal").style.display = "none";
}
