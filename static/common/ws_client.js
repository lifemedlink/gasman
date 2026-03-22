/**
 * GASMAN – WebSocket Client (FINAL)
 * --------------------------------
 * ✔ Single WS connection
 * ✔ Auto reconnect
 * ✔ Topic-based subscriptions
 * ✔ Admin / User safe
 * ✔ Matches admin_map.js usage
 */

(function (window) {

  if (window.GASMAN_WS) return;

  const WS = {
    socket: null,
    connected: false,
    reconnectDelay: 2000,

    // topic → [handlers]
    topics: {},

    // legacy listeners (all messages)
    listeners: []
  };

  /* ============================================================
     CONTEXT
  ============================================================ */

  const ROLE = (window.GASMAN_ROLE || "").toLowerCase();
  const USER = window.GASMAN_USER || "";

  if (!ROLE) {
    console.warn("GASMAN WS: role missing");
    return;
  }

  /* ============================================================
     URL
  ============================================================ */

  function buildWsUrl() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    let url = `${proto}://${location.host}/ws/devices?role=${encodeURIComponent(ROLE)}`;

    if (ROLE === "user" && USER) {
      url += `&user=${encodeURIComponent(USER)}`;
    }
    return url;
  }

  /* ============================================================
     CONNECT
  ============================================================ */

  function connect() {
    try {
      WS.socket = new WebSocket(buildWsUrl());

      WS.socket.onopen = () => {
        WS.connected = true;
        console.info("✅ GASMAN WS connected");
      };

      WS.socket.onclose = () => {
        WS.connected = false;
        console.warn("⚠ GASMAN WS disconnected – retrying…");
        setTimeout(connect, WS.reconnectDelay);
      };

      WS.socket.onerror = () => {
        WS.socket?.close();
      };

      WS.socket.onmessage = ev => {
        try {
          const payload = JSON.parse(ev.data);
          dispatch(payload);
        } catch (e) {
          console.warn("WS invalid JSON", e);
        }
      };

    } catch (e) {
      console.error("WS connect failed", e);
      setTimeout(connect, WS.reconnectDelay);
    }
  }

  /* ============================================================
     DISPATCH
  ============================================================ */

  function dispatch(payload) {

    // 🔹 Topic-based
    if (payload?.topic && WS.topics[payload.topic]) {
      WS.topics[payload.topic].forEach(fn => {
        try { fn(payload); } catch (e) { console.error(e); }
      });
    }

    // 🔹 Global listeners
    WS.listeners.forEach(fn => {
      try { fn(payload); } catch (e) { console.error(e); }
    });
  }

  /* ============================================================
     PUBLIC API
  ============================================================ */

  /**
   * Subscribe to a topic
   * Example: GASMAN_WS.subscribe("device_updates", fn)
   */
  WS.subscribe = function (topic, handler) {
    if (!topic || typeof handler !== "function") return;
    WS.topics[topic] = WS.topics[topic] || [];
    WS.topics[topic].push(handler);
  };

  /**
   * Listen to ALL messages (legacy)
   */
  WS.on = function (handler) {
    if (typeof handler === "function") {
      WS.listeners.push(handler);
    }
  };

  /**
   * Send message to server
   */
  WS.send = function (obj) {
    if (WS.connected && WS.socket?.readyState === 1) {
      WS.socket.send(JSON.stringify(obj));
    }
  };

  /* ============================================================
     INIT
  ============================================================ */

  connect();
  window.GASMAN_WS = WS;

})(window);
