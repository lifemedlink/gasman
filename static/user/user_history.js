document.addEventListener("DOMContentLoaded", () => {
  loadHistory();
  document.getElementById("historyStatus").onchange = loadHistory;
});

async function loadHistory() {
  const status = document.getElementById("filterStatus").value;
  const url = status
    ? `/api/user/history?status=${status}`
    : `/api/user/history`;

  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) return;

  const rows = await r.json();
  const body = document.getElementById("historyBody");
  body.innerHTML = "";

  if (!rows.length) {
    body.innerHTML =
      `<tr><td colspan="4" class="text-muted">No records</td></tr>`;
    return;
  }

  rows.forEach(t => {
    body.insertAdjacentHTML("beforeend", `
      <tr>
        <td>${t.device_id}</td>
        <td>${t.status}</td>
        <td>${t.accepted_at || "-"}</td>
        <td>${t.completed_at || "-"}</td>
      </tr>
    `);
  });
}


function exportHistoryCSV() {
  const rows = [...document.querySelectorAll("#historyTable tr")];
  let csv = "";

  rows.forEach(row => {
    const cols = [...row.querySelectorAll("td,th")];
    csv += cols.map(c => `"${c.innerText}"`).join(",") + "\n";
  });

  const blob = new Blob([csv], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "gasman_history.csv";
  a.click();
}
