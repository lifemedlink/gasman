document.addEventListener("DOMContentLoaded", loadDevices);

let currentUserManualMode = false;

/* ======================================================
   LOAD DEVICES
====================================================== */
async function loadDevices() {
  const r = await fetch("/user/devices/list", { credentials: "include" });
  if (!r.ok) return;

  const devices = await r.json();
  const list = document.getElementById("deviceList");
  list.innerHTML = "";

  if (!devices.length) {
    list.innerHTML = `<div class="text-muted p-3">No devices assigned</div>`;
    return;
  }

  currentUserManualMode = devices[0]?.manual_mode === true;

  devices.forEach(d => {

    const card = document.createElement("div");
    card.className = "device-card";

    const badgeClass =
      !d.online ? "badge-offline" :
      d.classification === "CRITICAL" ? "badge-critical" :
      d.classification === "LOW" ? "badge-low" :
      "badge-normal";

    card.innerHTML = `
      <div class="device-left">
        <div class="device-id">${d.device_id}</div>
        <div class="device-location">${d.device_location || "-"}</div>
      </div>
      <div class="device-right">
        <div class="gas">${Math.round(d.gas_percentage)}%</div>
        <span class="badge ${badgeClass}">
          ${d.online ? d.classification : "OFFLINE"}
        </span>
      </div>
    `;

    card.addEventListener("click", () => openDeviceModal(d));
    list.appendChild(card);
  });
}


/* ======================================================
   DEVICE MODAL
====================================================== */
window.openDeviceModal = function (d) {

  document.getElementById("m_id").innerText = d.device_id;
  document.getElementById("m_customer").innerText = d.customer_name || "-";
  document.getElementById("m_accepted_by").innerText = d.accepted_by || "--------------";
  document.getElementById("m_location").innerText = d.device_location || "-";
  document.getElementById("m_gas").innerText = `${Math.round(d.gas_percentage)}%`;
  document.getElementById("m_status").innerText = d.classification;

  const nav = document.getElementById("m_nav");
  nav.style.display = "none";

  if (d.coordinates) {
    const [lat, lng] = d.coordinates.split(",");
    nav.href = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;
  }

  let acceptBtn = document.getElementById("m_accept");

  if (!acceptBtn) {
    acceptBtn = document.createElement("button");
    acceptBtn.id = "m_accept";
    acceptBtn.className = "btn btn-success w-100 mb-2";
    nav.parentNode.insertBefore(acceptBtn, nav);
  }

  acceptBtn.style.display = "none";

  const isLowCritical =
    d.classification === "LOW" || d.classification === "CRITICAL";

  /* ======================================================
     AUTO MODE
  ====================================================== */
  if (!currentUserManualMode) {

    // Only show navigation if this is MY active task
    if (d.my_task_status) {
      nav.style.display = "block";
    }

  }

  /* ======================================================
     MANUAL MODE
  ====================================================== */
  else {

    // If I already accepted → show navigation
    if (d.my_task_status) {
      nav.style.display = "block";
    }

    // If LOW/CRITICAL and no active task → show Accept
    else if (!d.task_taken && isLowCritical) {

      acceptBtn.innerText = "Accept Task";
      acceptBtn.style.display = "block";

      acceptBtn.onclick = async function () {

        acceptBtn.disabled = true;
        acceptBtn.innerText = "Accepting...";

        const res = await fetch(`/user/devices/accept/${d.device_id}`, {
          method: "POST",
          credentials: "include"
        });

        const data = await res.json();

if (data.status === "accepted") {

    // Start the task (same as AUTO mode)
    await fetch("/user/task/start", {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            task_id: data.task_id
        })
    });

    closeModal();

    // Open the Drive page
    window.location.href = "/user";
}
 else {
          alert(data.error || "Unable to accept task");
          acceptBtn.disabled = false;
          acceptBtn.innerText = "Accept Task";
        }
      };
    }
  }

  document.getElementById("deviceModal").style.display = "flex";
};

window.closeModal = function () {
  document.getElementById("deviceModal").style.display = "none";
};
