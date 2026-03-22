/**
 * GLOBAL TASK ROUTER – FINAL INDUSTRIAL STABLE VERSION
 * ----------------------------------------------------
 * ✔ Manual + Auto unified lifecycle
 * ✔ Instant mode switching
 * ✔ No stale memory
 * ✔ Route clears correctly
 * ✔ Completion lock safe
 * ✔ No duplicate intervals
 * ✔ Pending + Active task route support
 */

window.TASK_MODE = "AUTO";

let routerInterval = null;
let routerInitialized = false;

window.lastActiveTaskId = null;

let lastShownCompletedId = null;
let completedLock = false;

const $ = id => document.getElementById(id);


/* =====================================================
   LOAD MODE FROM BACKEND
===================================================== */
async function loadTaskMode() {
  try {

    const r = await fetch("/user/settings",{credentials:"include"});
    if (!r.ok) return;

    const data = await r.json();

    window.TASK_MODE = data.task_enabled ? "AUTO" : "MANUAL";

  } catch(e) {
    console.error("Mode load failed",e);
  }
}


/* =====================================================
   SAVE MODE TO BACKEND
===================================================== */
async function saveTaskMode(enabled) {

  try {

    const r = await fetch("/user/settings/task-toggle",{
      method:"POST",
      credentials:"include",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({enabled})
    });

    if(!r.ok) return false;

    window.TASK_MODE = enabled ? "AUTO" : "MANUAL";
    return true;

  } catch(e){
    console.error("Mode save failed",e);
    return false;
  }

}


/* =====================================================
   TOGGLE UI + ENGINE SWITCH
===================================================== */
function initModeToggle(){

  const toggle = document.getElementById("modeToggle");
  const letter = document.getElementById("modeLetter");

  if(!toggle || !letter) return;

  function setVisual(mode){

    if(mode === "AUTO"){
      toggle.classList.remove("manual");
      toggle.classList.add("auto");
      letter.innerText = "A";
    } else {
      toggle.classList.remove("auto");
      toggle.classList.add("manual");
      letter.innerText = "M";
    }

  }

  setVisual(window.TASK_MODE);

  toggle.addEventListener("click", async ()=>{

    const newMode = window.TASK_MODE === "AUTO" ? "MANUAL" : "AUTO";
    const enabled = newMode === "AUTO";

    const success = await saveTaskMode(enabled);
    if(!success) return;

    if(routerInterval){
      clearInterval(routerInterval);
      routerInterval = null;
    }

    window.TASK_MODE = newMode;
    setVisual(newMode);

    if(window.clearRoute){
      clearRoute();
    }

    window.lastActiveTaskId = null;
    window.autoLastSuggested = null;
    completedLock = false;
    lastShownCompletedId = null;

    const userPos = window.USER_MAP?.getUserPos?.();

    if(userPos){

      if(newMode === "AUTO"){
        await window.autoEngineTick?.(userPos);
      }

      if(newMode === "MANUAL"){
        await window.manualEngineTick?.(userPos);
      }

    }

    startRouter();

  });

}


/* =====================================================
   ROUTER CORE LOOP
===================================================== */
async function runRouterTick(){

  if(!window.USER_MAP) return;

  const userPos = window.USER_MAP.getUserPos?.();
  if(!userPos) return;


  /* =====================================================
     1️⃣ ACTIVE TASK
  ===================================================== */

  const activeRes = await fetch(
    `/user/task/active?lat=${userPos.lat}&lng=${userPos.lng}`,
    {credentials:"include"}
  );

  if(activeRes.ok){

    const active = await activeRes.json();

    if(active?.task_id){

      window.lastActiveTaskId = active.task_id;

      completedLock = false;
      lastShownCompletedId = null;

      window.TaskUI?.showActive?.(active);

      /* DRAW ROUTE TO ACTIVE TASK */

      if(active.status !== "ON_SITE"){

        if(active.coordinates && window.drawRoute){
          drawRoute(userPos, active.coordinates);
        }

      } else {

        if(window.clearRoute) clearRoute();

      }

      return;

    }

  }


  window.lastActiveTaskId = null;


  /* =====================================================
     2️⃣ COMPLETED TASK CHECK
  ===================================================== */

  const completedRes = await fetch("/user/task/last-completed",{credentials:"include"});

  if(completedRes.ok){

    const completed = await completedRes.json();

    if(
      completed?.task_id &&
      completed.task_id !== lastShownCompletedId &&
      !completedLock
    ){

      lastShownCompletedId = completed.task_id;
      completedLock = true;

      window.TaskUI?.showCompleted?.();

      if(window.clearRoute){
        clearRoute();
      }

      setTimeout(()=>{
        window.TaskUI?.reset?.();
      },6000);

      return;

    }

  }


  /* =====================================================
     3️⃣ MODE ENGINE EXECUTION
  ===================================================== */

  if(window.TASK_MODE === "AUTO"){
    await window.autoEngineTick?.(userPos);
  }

  if(window.TASK_MODE === "MANUAL"){
    await window.manualEngineTick?.(userPos);
  }


  /* =====================================================
     4️⃣ DRAW ROUTE FOR PENDING TASK
  ===================================================== */

  if(!window.lastActiveTaskId){

    const pendingDevice = window.autoLastSuggested;

    if(pendingDevice){

      try{

        const res = await fetch("/user/devices/map",{credentials:"include"});
        if(!res.ok) return;

        const devices = await res.json();

        const dev = devices.find(d => d.device_id === pendingDevice);

        if(dev?.coordinates && window.drawRoute){
          drawRoute(userPos, dev.coordinates);
        }

      }catch(e){}

    }

  }

}


/* =====================================================
   START ROUTER LOOP
===================================================== */
function startRouter(){

  if(routerInterval){
    clearInterval(routerInterval);
  }

  runRouterTick();

  routerInterval = setInterval(runRouterTick,3000);

}


/* =====================================================
   FORCE REFRESH BUTTON
===================================================== */
window.forceTaskRefresh = async function(){

  completedLock = false;
  lastShownCompletedId = null;
  window.autoLastSuggested = null;

  runRouterTick();

};


/* =====================================================
   INIT
===================================================== */

document.addEventListener("DOMContentLoaded", async ()=>{

  if(routerInitialized) return;
  routerInitialized = true;

  await loadTaskMode();

  initModeToggle();

  const refreshBtn = document.getElementById("refreshBtn");

  if(refreshBtn){
    refreshBtn.addEventListener("click",()=>{
      window.forceTaskRefresh?.();
    });
  }

  startRouter();

});
