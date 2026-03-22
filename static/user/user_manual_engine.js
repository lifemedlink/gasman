/**
 * MANUAL ENGINE – FULL ROUTE + ETA + GPS VERSION
 */

window.manualEngineTick = async function(userPos){

  try {

    const r = await fetch("/user/task/active", {
      credentials: "include"
    });

    if (!r.ok) return;

    const active = await r.json();

    // --------------------------------------------------
    // NO ACTIVE TASK
    // --------------------------------------------------
    if (!active || !active.task_id) {

      window.lastActiveTaskId = null;

      if (window.clearRoute) window.clearRoute();

      if (window.TaskUI?.reset) {
        TaskUI.reset();
      }

      return;
    }

    // --------------------------------------------------
    // ACTIVE TASK EXISTS
    // --------------------------------------------------

    window.lastActiveTaskId = active.task_id;

    if (window.TaskUI?.showActive) {
      TaskUI.showActive(active);
    }

    // --------------------------------------------------
    // DRAW ROUTE + ETA (ONLY IF EN_ROUTE)
    // --------------------------------------------------

    if (
      userPos &&
      active.coordinates &&
      active.status === "EN_ROUTE"
    ) {
      if (window.drawRoute) {
        window.drawRoute(userPos, active.coordinates);
      }
    }

    // --------------------------------------------------
    // SEND GPS PING (AUTO ON_SITE TRIGGER)
    // --------------------------------------------------

    if (userPos && active.status === "EN_ROUTE") {

      await fetch("/user/task/gps-ping", {
        method: "POST",
        credentials: "include",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
          lat: userPos.lat,
          lng: userPos.lng
        })
      });

    }

  } catch (e) {
    console.error("Manual engine error:", e);
  }
};
