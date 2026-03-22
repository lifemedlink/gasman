/**
 * GASMAN – Admin History Controller (FINAL)
 * ----------------------------------------
 * ✔ Uses /get_history
 * ✔ Calendar filter
 * ✔ Session-safe
 */

(function () {

  const body = document.getElementById("adminHistoryRows");
  const btn = document.getElementById("historyFetchBtn");
  if (!body || !btn) return;

  async function loadHistory() {
    const start = document.getElementById("historyStart")?.value;
    const end = document.getElementById("historyEnd")?.value;

    body.innerHTML = `
      <tr>
        <td colspan="5" class="text-muted text-center">Loading…</td>
      </tr>
    `;

    let url = "/get_history?limit=1000";
    if (start) url += `&start_date=${start}`;
    if (end) url += `&end_date=${end}`;

    const rows = await GASMAN_UTILS.safeFetch(url);
    if (!Array.isArray(rows) || !rows.length) {
      body.innerHTML = `
        <tr>
          <td colspan="5" class="text-muted text-center">No history</td>
        </tr>
      `;
      return;
    }

    body.innerHTML = rows.map(r => `
      <tr>
        <td>${new Date(r.event_time).toLocaleString()}</td>
        <td><strong>${r.device_id}</strong></td>
        <td>${Math.round(r.gas_percentage)}%</td>
        <td>
          <span class="badge ${
            r.classification === "CRITICAL" ? "bg-danger" :
            r.classification === "LOW" ? "bg-warning text-dark" :
            "bg-success"
          }">
            ${r.classification}
          </span>
        </td>
        <td>${r.user_name || "-"}</td>
      </tr>
    `).join("");
  }

  btn.addEventListener("click", loadHistory);

})();
