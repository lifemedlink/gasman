let ALL_DEVICES = [];

/* ======================================================
   LOAD DEVICES
====================================================== */
/*async function loadDevices() {
  const data = await GASMAN_UTILS.safeFetch("/devices/list");
  if (!Array.isArray(data)) return;
  ALL_DEVICES = data;
  renderTable();
}*/
async function loadDevices() {
  try {
    const res = await fetch("/devices/list", {
      credentials: "include"
    });

    if (!res.ok) {
      console.error("Failed to load devices:", res.status);
      return;
    }

    const data = await res.json();

    if (!Array.isArray(data)) {
      console.error("Invalid devices response");
      return;
    }

    ALL_DEVICES = data;
    renderTable();

  } catch (err) {
    console.error("Device load error:", err);
  }
}

/* ======================================================
   PRIORITY SORT (DB DRIVEN)
====================================================== */
function getPriorityRank(d) {
  if (d.system_status === "Fault") return 1;

  if (d.gas_leak_flag === "Issue") return 2;
  if (d.gas_leak_flag === "Alert") return 3;

  if (d.tank_level_flag === "Issue" || d.line_pressure_flag === "Issue") return 4;
  if (d.tank_level_flag === "Alert" || d.line_pressure_flag === "Alert") return 5;

  return 6;
}

/* ======================================================
   COMMENTS BUILDER (TEXT COLOR ONLY – NO BOX)
====================================================== */
function buildComments(d) {
  const parts = [];

  // ---- TANK LEVEL ----
  if (d.tank_level_flag === "Alert") {
    parts.push(`<span class="text-warning">Tank level</span>`);
  } else if (d.tank_level_flag === "Issue") {
    parts.push(`<span class="text-danger">Tank level</span>`);
  }

  // ---- LINE PRESSURE ----
  if (d.line_pressure_flag === "Alert") {
    parts.push(`<span class="text-warning">Line pressure</span>`);
  } else if (d.line_pressure_flag === "Issue") {
    parts.push(`<span class="text-danger">Line pressure</span>`);
  }

  // ---- GAS LEAK ----
  if (d.gas_leak_flag === "Alert") {
    parts.push(`<span class="text-warning">Gas leak</span>`);
  } else if (d.gas_leak_flag === "Issue") {
    parts.push(`<span class="text-danger">Gas leak</span>`);
  }

  // ---- SYSTEM ----
  if (d.system_status === "Fault") {
    if (d.device_offline) {
      parts.push(`<span class="text-danger">Device offline</span>`);
    }
    if (d.power_fault) {
      parts.push(`<span class="text-danger">Power fault</span>`);
    }
  }

  return parts.length ? parts.join(", ") : "-";
}

/* ======================================================
   RENDER TABLE
====================================================== */
function renderTable() {
  const body = document.getElementById("deviceTableBody");
  const search = document.getElementById("searchBox").value.toLowerCase();
  const filter = document.getElementById("filterStatus").value;

  let devices = [...ALL_DEVICES];

  // SEARCH
  if (search) {
    devices = devices.filter(d =>
      d.device_id.toLowerCase().includes(search)
    );
  }

  // FILTER
  if (filter !== "ALL") {
    if (filter === "PRIORITY") {
      devices.sort((a, b) => getPriorityRank(a) - getPriorityRank(b));
    } else if (filter === "FAULT") {
      devices = devices.filter(d => d.system_status === "Fault");
    } else if (filter === "GAS_ISSUE") {
      devices = devices.filter(d => d.gas_leak_flag === "Issue");
    } else if (filter === "GAS_ALERT") {
      devices = devices.filter(d => d.gas_leak_flag === "Alert");
    } else if (filter === "OP_ISSUE") {
      devices = devices.filter(d =>
        d.tank_level_flag === "Issue" || d.line_pressure_flag === "Issue"
      );
    } else if (filter === "OP_ALERT") {
      devices = devices.filter(d =>
        d.tank_level_flag === "Alert" || d.line_pressure_flag === "Alert"
      );
    } else if (filter === "SAFE") {
      devices = devices.filter(d =>
        d.system_status === "OK" &&
        d.gas_leak_flag === "Safe" &&
        d.tank_level_flag === "Safe" &&
        d.line_pressure_flag === "Safe"
      );
    }
  }

  body.innerHTML = "";

  if (!devices.length) {
    body.innerHTML = `
      <tr>
        <td colspan="12" class="text-center text-muted py-3">
          No devices found
        </td>
      </tr>`;
    return;
  }

  devices.forEach(d => {
    const systemColor = d.system_status === "Fault" ? "danger" : "success";

    let gasAlarmColor = "success";
    if (d.gas_leak_flag === "Alert") gasAlarmColor = "warning";
    if (d.gas_leak_flag === "Issue") gasAlarmColor = "danger";

    let opColor = "success";
    if (d.tank_level_flag === "Alert" || d.line_pressure_flag === "Alert") {
      opColor = "warning";
    }
    if (d.tank_level_flag === "Issue" || d.line_pressure_flag === "Issue") {
      opColor = "danger";
    }

    const lastUpdateColor = d.online ? "text-success" : "text-danger";
    const commentsHtml = buildComments(d);

    body.insertAdjacentHTML("beforeend", `
      <tr class="${d.online ? "" : "offline"}">
        <td>${d.customer_name}</td>
        <td>${d.location}</td>
        <td><b>${d.device_id}</b></td>

        <td><span class="badge bg-${systemColor} badge-status">${d.system_status}</span></td>
        <td><span class="badge bg-${gasAlarmColor} badge-status">${d.gas_alarm_status}</span></td>
        <td>${d.gas_leak_percent ?? 0}</td>
        <td><span class="badge bg-${opColor} badge-status">${d.operation_status}</span></td>

        <td>${d.tank_level_percent ?? "-"}</td>
        <td>${d.tank_pressure ?? "-"}</td>
        <td>${d.line_pressure ?? "-"}</td>

        <td class="${lastUpdateColor}">${d.last_update_text ?? "-"}</td>
        <td>${commentsHtml}</td>
      </tr>
    `);
  });
}

/* ======================================================
   EVENTS
====================================================== */
document.getElementById("searchBox").addEventListener("input", renderTable);
document.getElementById("filterStatus").addEventListener("change", renderTable);

/* ======================================================
   INIT
====================================================== */
loadDevices();
setInterval(loadDevices, 10000);
