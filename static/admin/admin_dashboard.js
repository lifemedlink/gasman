/* =========================================================
   GASMAN – DASHBOARD (KPI FILTER ENABLED – FULL VERSION)
========================================================= */

(function () {

  function el(id){ return document.getElementById(id); }
  function setText(id,val){ if(el(id)) el(id).innerText = val; }

  async function api(url){
    try{
      const res = await fetch(url,{credentials:"include"});
      if(!res.ok) return null;
      return await res.json();
    }catch{ return null; }
  }

  /* ================= KPI LOAD ================= */

  async function loadKPIs() {

    const data = await api("/devices");
    if (!data) return;

    setText("kpiAllDevices", data.total_devices);
    setText("kpiTasks", data.active_tasks);
    setText("kpiCritical", data.critical);
    setText("kpiLow", data.low);
    setText("kpiNormal", data.normal);
    setText("kpiOffline", data.offline);
  }

  /* ================= KPI FILTER CLICK ================= */

  function initKpiFilters(){

    const cards = document.querySelectorAll(".kpi-card");

    cards.forEach(card => {

      card.addEventListener("click", function(){

        const filter = this.dataset.filter;

        // Remove active from all
        cards.forEach(c => c.classList.remove("active"));

        // Activate clicked
        this.classList.add("active");

        // Update URL
        const url = new URL(window.location);
        if(filter === "ALL"){
          url.searchParams.delete("filter");
        } else {
          url.searchParams.set("filter", filter);
        }

        window.history.replaceState({}, "", url);
        window.deviceFilter = filter === "ALL" ? null : filter;
        // Reload map
        if(window.loadAdminMap){
          window.loadAdminMap();
        }
      });

    });

  }

  /* ================= PREDICTIVE ================= */

  async function loadPredictive(){
    const box = el("predictiveList");
    if(!box) return;

    const data = await api("/admin/predictive");

    if(!data || !data.length){
      box.innerHTML =
        `<div class="text-muted small">No upcoming CRITICAL alerts</div>`;
      return;
    }

    box.innerHTML = data.map(p => `
      <div class="border-bottom py-2 small">
        <strong>${p.device_id}</strong><br>
        Gas: ${p.current_pct}%<br>
        ⏳ Critical in <strong>${p.minutes_to_critical} min</strong>
      </div>
    `).join("");
  }

  /* ================= LIVE TASK TABLE ================= */

  async function loadLiveTasks() {

    const tbody = document.getElementById("liveTaskTable");
    if (!tbody) return;

    const data = await api("/admin/tasks/live");

    if (!data || !data.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" class="text-center text-muted p-3">
            No active driver tasks
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = data.map(t => `
      <tr>
        <td>${t.driver}</td>
        <td>${t.device_id}</td>
        <td>
          <span class="badge bg-primary">
            ${t.status}
          </span>
        </td>
        <td>${t.gas_percentage ?? 0}%</td>
      </tr>
    `).join("");
  }

  /* ================= INIT ================= */

  loadKPIs();
  loadPredictive();
  loadLiveTasks();
  initKpiFilters();

  setInterval(loadKPIs,30000);
  setInterval(loadPredictive,60000);
  setInterval(loadLiveTasks,15000);

})();
