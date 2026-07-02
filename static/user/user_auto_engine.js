/**
 * AUTO ENGINE – FINAL INDUSTRIAL VERSION (DUAL NAVIGATION)
 * -------------------------------------------------
 * ✔ Active task priority
 * ✔ Pending suggestion
 * ✔ Completion detection
 * ✔ Route lifecycle safe
 * ✔ Manual → Auto switching safe
 * ✔ No stale memory
 * ✔ Auto start navigation after accept
 * ✔ Internal navigation + Google Maps support
 * ✔ Navigate button opens Google Maps
 */

window.autoLastSuggested = null;

/* Navigation preference
   INTERNAL = stay inside GASMAN
   MAPS = open Google Maps app
*/
window.NAV_MODE = "INTERNAL";


/* =====================================================
   AUTO ENGINE LOOP
===================================================== */

window.autoEngineTick = async function (userPos) {

  try {

    /* =====================================================
       1️⃣ CHECK ACTIVE TASK
    ===================================================== */

    const activeRes = await fetch(
      `/user/task/active?lat=${userPos.lat}&lng=${userPos.lng}`,
      { credentials: "include" }
    );

    if (!activeRes.ok) return;

    const active = await activeRes.json();

    if (active?.task_id) {

      window.lastActiveTaskId = active.task_id;

      window.TaskUI?.showActive?.(active);

      /* =====================================================
         ROUTE CONTROL / ARRIVAL DETECTION
      ===================================================== */

      const mapRes = await fetch("/user/devices/map", {
        credentials: "include"
      });

      if (mapRes.ok) {

        const devices = await mapRes.json();
        const dev = devices.find(d => d.device_id === active.device_id);

        /* ================= ARRIVED ================= */

        if (active.status === "ON_SITE") {

          window.routeLocked = true;

          if (window.clearRoute) clearRoute();

          window.currentRouteInfo = null;

          /* Return to GASMAN if Google Maps was open */
          if (document.hidden) {
            window.location.href = "/user";
          }

        } else {

          window.routeLocked = false;

          /* Draw route internally if navigation mode */
          if (
            window.NAV_MODE === "INTERNAL" &&
            dev?.coordinates &&
            window.drawRoute
          ) {
            drawRoute(userPos, dev.coordinates);
          }

        }

      }


      return;

    }

    window.lastActiveTaskId = null;


    /* =====================================================
       2️⃣ CHECK RECENT COMPLETION
    ===================================================== */

    const completedRes = await fetch("/user/task/last-completed", {
      credentials: "include"
    });

    if (completedRes.ok) {

      const completed = await completedRes.json();

      if (completed?.task_id) {

        window.autoLastSuggested = null;

        window.TaskUI?.showCompleted?.();

        if (window.clearRoute) {
          clearRoute();
        }

        setTimeout(() => {
          window.TaskUI?.reset?.();
        }, 6000);

        return;

      }

    }


    /* =====================================================
       3️⃣ CHECK PENDING TASK
    ===================================================== */

    const pendingRes = await fetch(
      `/user/task/pending?lat=${userPos.lat}&lng=${userPos.lng}`,
      { credentials: "include" }
    );

    if (!pendingRes.ok) return;

    const pending = await pendingRes.json();

    if (!pending?.task_id || pending.task_taken === true) {

      window.autoLastSuggested = null;
      window.TaskUI?.reset?.();
      return;

    }

    if (pending.device_id === window.autoLastSuggested) {
      return;
    }

    window.autoLastSuggested = pending.device_id;


    /* =====================================================
       4️⃣ SHOW NEW TASK
    ===================================================== */

    window.TaskUI?.showNew?.(pending);


    /* =====================================================
       5️⃣ ACCEPT / REJECT BUTTONS
    ===================================================== */

    const acceptBtn = document.getElementById("btnAccept");
    const rejectBtn = document.getElementById("btnReject");

    if (acceptBtn) {
      acceptBtn.onclick = () => acceptTask(pending.task_id);
    }

    if (rejectBtn) {
      rejectBtn.onclick = () => rejectTask(pending.device_id);
    }

  } catch (e) {

    console.error("Auto engine error:", e);

  }

};



/* =====================================================
   ACCEPT TASK
===================================================== */

async function acceptTask(taskId) {

  try {

    const r = await fetch("/user/task/accept", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId })
    });

    if (!r.ok) {

      const err = await r.text();
      console.error("Accept failed:", err);
      return;

    }

    const task = await r.json();

    window.autoLastSuggested = null;

    /* Accept → use INTERNAL navigation */

    window.NAV_MODE = "INTERNAL";

    if (task?.task_id) {

  /* stay in internal navigation */
  /*window.NAV_MODE = "INTERNAL";*/

      startNavigation({
        task_id: task.task_id,
        device_id: task.device_id,
        status: task.status
      });

    }

  } catch (e) {

    console.error("Accept error:", e);

  }

}



/* =====================================================
   REJECT TASK
===================================================== */

async function rejectTask(deviceId) {

  try {

    await fetch("/user/task/reject", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId })
    });

    window.autoLastSuggested = null;
    window.TaskUI?.reset?.();

  } catch (e) {

    console.error("Reject error:", e);

  }

}



/* =====================================================
   CANCEL TASK
===================================================== */

async function cancelTask(taskId) {

  await fetch("/user/task/cancel", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId })
  });

  window.autoLastSuggested = null;
  window.TaskUI?.reset?.();

}



/* =====================================================
   START NAVIGATION
===================================================== */

async function startNavigation(task) {

  try {

if (task.status === "ASSIGNED") {

    const startRes = await fetch("/user/task/start", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: task.task_id })
    });

    if (startRes.ok) {
        task.status = "EN_ROUTE";
    } else {
        console.warn("Start skipped (already started)");
    }

}
  } catch (e) {

    console.error("Start error:", e);

  }


  /* =====================================================
     GET DEVICE LOCATION
  ===================================================== */

  const r = await fetch("/user/devices/map", {
    credentials: "include"
  });

  if (!r.ok) return;

  const devices = await r.json();
  const dev = devices.find(d => d.device_id === task.device_id);

  if (!dev?.coordinates) return;

//  const [lat, lng] = dev.coordinates.split(",").map(v => v.trim());
const [lat, lng] = dev.coordinates.split(",").map(v => v.trim());

window.currentDestinationCoords = {
  lat,
  lng
};

  /* =====================================================
     INTERNAL NAVIGATION
  ===================================================== */

  if (window.NAV_MODE === "INTERNAL") {

    const userPos = window.USER_MAP?.getUserPos?.();

    if (userPos && window.drawRoute) {
      drawRoute(userPos, `${lat},${lng}`);
    }

    return;

  }


/* =====================================================
   SMART NAVIGATION (PHONE → APP, DESKTOP → TAB)
===================================================== */

return;
}
