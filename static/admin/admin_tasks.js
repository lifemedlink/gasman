(async function () {

  const body = document.getElementById("taskRows");
  if (!body) return;

  async function loadTasks() {
    const rows = await fetch("/admin/tasks/live").then(r => r.json());
    body.innerHTML = "";

    if (!rows.length) {
      body.innerHTML =
        "<tr><td colspan='7' class='text-muted'>No active tasks</td></tr>";
      return;
    }

    rows.forEach(t => {
      const badge =
        t.status === "PENDING" ? "secondary" :
        t.status === "ACCEPTED" ? "warning text-dark" :
        t.status === "IN_PROGRESS" ? "primary" :
        "success";

      body.insertAdjacentHTML("beforeend", `
        <tr>
          <td><b>${t.device_id}</b></td>
          <td>${t.user_name}</td>
          <td><span class="badge bg-${badge}">${t.status}</span></td>
          <td>${t.gas_percentage ?? "-"}%</td>
          <td>${t.tracking_id || "-"}</td>
          <td>${t.started_navigation_at || t.accepted_at || t.created_at}</td>
          <td>
            <button class="btn btn-sm btn-outline-primary"
              onclick="viewTask(${t.id})">
              View
            </button>
          </td>
        </tr>
      `);
    });
  }

  window.viewTask = async function (taskId) {
    const rows = await fetch(`/admin/tasks/${taskId}`).then(r => r.json());
    let log = rows.map(r =>
      `${r.created_at} – ${r.action}`
    ).join("\n");

    alert("Task Timeline:\n\n" + log);
  };

  loadTasks();
  setInterval(loadTasks, 10000); // 🔁 LIVE refresh

})();
