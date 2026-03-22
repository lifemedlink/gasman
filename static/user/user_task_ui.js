window.TaskUI = (function(){

  const $ = id => document.getElementById(id);

  function show(el){ if(el) el.style.display = "block"; }
  function hide(el){ if(el) el.style.display = "none"; }
  function set(el,val){ if(el) el.innerText = val ?? "-"; }

  /* =====================================================
     CARD ANIMATION
  ===================================================== */

function showCard(){
  const c = $("taskCard");
  if(!c) return;

  /* only expand when card first appears */
  if(c.style.display !== "block"){
    c.classList.remove("minimized");
  }

  c.style.display = "block";

  requestAnimationFrame(()=>{
    c.classList.add("show");
  });
}

  function hideCardSmooth(){
    const c = $("taskCard");
    if(!c) return;

    c.classList.remove("show");
    c.classList.add("slide-down");

    setTimeout(()=>{
      c.classList.remove("slide-down");
      c.style.display = "none";
    },300);
  }

  /* =====================================================
     PROGRESS TRACKER
  ===================================================== */

  function updateProgress(status){

    const steps = document.querySelectorAll(".step");
    const fill = $("progressFill");

    steps.forEach((s,index)=>{
      s.classList.remove("active","current","completed");
      s.innerHTML = s.getAttribute("data-step") || (index+1);
    });

    let percent = 0;
    let currentIndex = 0;

    if(status === "ASSIGNED"){ currentIndex = 0; percent = 0; }
    if(status === "EN_ROUTE"){ currentIndex = 1; percent = 33; }
    if(status === "ON_SITE"){ currentIndex = 2; percent = 66; }
    if(status === "FILLING"){ currentIndex = 2; percent = 66; }
    if(status === "FILLED"){ currentIndex = 3; percent = 100; }

    if(status === "COMPLETED"){
      percent = 100;
      steps.forEach(s=>{
        s.classList.add("completed");
        s.innerHTML = "";
      });
      if(fill) fill.style.width = percent + "%";
      return;
    }

    steps.forEach((step,index)=>{
      if(index < currentIndex){
        step.classList.add("completed");
        step.innerHTML = "";
      }
      if(index === currentIndex){
        step.classList.add("active","current");
      }
    });

    if(fill) fill.style.width = percent + "%";
  }

  /* =====================================================
     GAS PROGRESS (MATCH PIN COLORS)
  ===================================================== */

  function updateGasProgress(percent, classification){

    const fill = $("gasProgressFill");
    const text = $("gasPercentText");

    const clean = Math.max(0, Math.min(100, percent));

    if(fill){

      fill.style.width = clean + "%";

      if(classification === "CRITICAL"){
        fill.style.background = "#ff0000";
      }
      else if(classification === "LOW"){
        fill.style.background = "#ffbf00";
      }
      else{
        fill.style.background = "#28a745";
      }
    }

    if(text){
      text.innerText = clean + "%";
    }
  }

  /* =====================================================
     RESET
  ===================================================== */

  function reset(){
    if(window.lastActiveTaskId) return;
    hideCardSmooth();
    setTimeout(()=>{
      hide($("taskPending"));
      hide($("taskActive"));
    },300);
  }

  /* =====================================================
     SHOW NEW TASK
  ===================================================== */

  function showNew(device){

    showCard();
    show($("taskPending"));
    hide($("taskActive"));

    set($("t_device"), device.device_id);
    set($("t_customer"), device.customer_name);
    set($("t_location"), device.device_location);

    const badge = $("t_priority");
    const gasPercent = Math.round(device.gas_percentage || 0);
    const classification = device.classification;

    if(badge){
      if(classification === "CRITICAL"){
        badge.className = "task-badge badge-critical";
        badge.innerText = `CRITICAL (${gasPercent}%)`;
      } else {
        badge.className = "task-badge badge-low";
        badge.innerText = `LOW (${gasPercent}%)`;
      }
    }

    updateProgress("ASSIGNED");
  }

  /* =====================================================
     SHOW ACTIVE TASK
  ===================================================== */

  function showActive(task){

    showCard();
    hide($("taskPending"));
    show($("taskActive"));

    set($("a_title"), task.device_id || "-");
    set($("a_subtitle"), task.customer_name || "-");
    set($("a_location"), task.device_location || "-");
    set($("a_tracking"), task.tracking_id || "-");

    const statusMap = {
      "ASSIGNED": "ACCEPTED",
      "EN_ROUTE": "ON THE WAY",
      "ON_SITE": "LOCATION REACHED",
      "FILLING": "GAS FILLING",
      "FILLED": "GAS FILLED",
      "COMPLETED": "TASK COMPLETED"
    };

    const displayStatus = statusMap[task.status] || task.status;

    set($("a_status"), displayStatus);

    const statusBadge = $("a_status_badge");
    if(statusBadge){
      statusBadge.innerText = displayStatus;
    }

    const etaRow = $("a_eta")?.closest(".task-row");
    const gasRow = $("gasProgressRow");

    if(task.status === "ASSIGNED" || task.status === "EN_ROUTE"){
      if(etaRow) show(etaRow);
      if(gasRow) hide(gasRow);
    }
    else if(task.status === "ON_SITE" ||
            task.status === "FILLING" ||
            task.status === "FILLED"){

      if(etaRow) hide(etaRow);

      if(gasRow){
        show(gasRow);
        updateGasProgress(
          task.gas_percentage ?? 0,
          task.classification ?? "NORMAL"
        );
      }
    }
    else{
      if(etaRow) hide(etaRow);
      if(gasRow) hide(gasRow);
    }

    updateProgress(task.status);

    const navBtn = $("btnNavigate");
    const cancelBtn = $("btnCancel");

    /* ===== NAV BUTTON ===== */

if(navBtn){

  if(task.status === "ASSIGNED" || task.status === "EN_ROUTE"){

    navBtn.innerText = "Navigate";
    navBtn.className = "btn btn-primary";
    show(navBtn);

    navBtn.onclick = ()=>{
       window.NAV_MODE = "MAPS";
      if(window.startNavigation) window.startNavigation(task);
    };

    /* ===============================
       AUTO ROUTE START (NEW)
    =============================== */
    if(task.status === "EN_ROUTE"){
      if(window.startNavigation){
        window.startNavigation(task);
      }
    }

  }

      else if(task.status === "FILLING" || task.status === "FILLED"){

        navBtn.innerText = "Task Completed";
        navBtn.className = "btn btn-success";
        show(navBtn);

        navBtn.onclick = async ()=>{

          const gasValue = task.gas_percentage ?? 0;

          const confirmBox = confirm(
            `Are you sure Gas Filled ${gasValue}% ?`
          );

          if(!confirmBox) return;

          navBtn.disabled = true;

          await fetch("/user/task/complete",{
            method:"POST",
            credentials:"include",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({ task_id: task.task_id })
          });

          set($("a_status"), "TASK COMPLETED");

          if(statusBadge){
            statusBadge.className = "task-badge badge-active";
            statusBadge.innerText = "TASK COMPLETED";
          }

          updateProgress("COMPLETED");

          navBtn.innerText = "Completed ✓";

          setTimeout(()=>{
            window.lastActiveTaskId = null;
            hideCardSmooth();
            window.forceTaskRefresh?.();
          },2000);
        };
      }

      else{
        hide(navBtn);
      }
    }

    /* ===== CANCEL BUTTON ===== */

    if(cancelBtn){

      if(task.status === "ASSIGNED" ||
         task.status === "EN_ROUTE" ||
         task.status === "ON_SITE"){

        show(cancelBtn);

        cancelBtn.onclick = async ()=>{

          await fetch("/user/task/cancel",{
            method:"POST",
            credentials:"include",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({ task_id: task.task_id })
          });

          if(window.clearRoute) window.clearRoute();

          window.lastActiveTaskId = null;
          reset();
        };
      }
      else{
        hide(cancelBtn);
      }
    }
  }

document.addEventListener("DOMContentLoaded",()=>{
const toggleBtn = document.getElementById("taskToggle");
const taskCard = document.getElementById("taskCard");

if(toggleBtn && taskCard){

  toggleBtn.onclick = ()=>{

    if(taskCard.classList.contains("minimized")){
      taskCard.classList.remove("minimized");
      toggleBtn.innerText = "▼";
    }else{
      taskCard.classList.add("minimized");
      toggleBtn.innerText = "▲";
    }

  };

}
  /* ================= CARD DRAG SYSTEM ================= */

  const card = document.getElementById("taskCard");
  const dragHandle = document.querySelector(".task-drag");

  let startY = 0;
  let currentY = 0;
  let dragging = false;

  if(card && dragHandle){

    dragHandle.addEventListener("touchstart", e=>{
      dragging = true;
      startY = e.touches[0].clientY;
      card.classList.add("dragging");
    });

    dragHandle.addEventListener("touchmove", e=>{
      if(!dragging) return;

      currentY = e.touches[0].clientY;
      const diff = currentY - startY;

      if(diff > 0){
        card.style.transform = `translateY(${diff}px)`;
      }
    });

    dragHandle.addEventListener("touchend", ()=>{

      dragging = false;
      card.classList.remove("dragging");
      card.style.transform = "";

      const diff = currentY - startY;

      if(diff > 80){
        card.classList.add("minimized");
      }else{
        card.classList.remove("minimized");
      }

    });

  }

});
  return {
    reset,
    showNew,
    showActive
  };

})();
