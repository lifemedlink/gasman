// ecosystem.config.js
// GASMAN – Fully Universal PM2 Production Config

const APP_ROOT = "/home/lmltcpa/gasman";

const commonEnv = {
  PYTHONPATH: APP_ROOT,
  PYTHONUNBUFFERED: "1",
  ENV: "prod",
  DEBUG: "false",

  DB_HOST: "127.0.0.1",
  DB_PORT: "3306",
  DB_USER: "root",
  DB_PASSWORD: "root",
  DATA_LOGGER_DB: "data_logger",
  GASMAN_DB: "gasman",

  REDIS_URL: "redis://127.0.0.1:6379/0",

  JWT_SECRET: process.env.JWT_SECRET,

  GOOGLE_MAPS_API_KEY: process.env.GOOGLE_MAPS_API_KEY
};

module.exports = {
  apps: [

    {
      name: "gasman-api",
      cwd: APP_ROOT,

      script: `${APP_ROOT}/venv/bin/gunicorn`,
args:
  "app:app " +
  "--worker-class uvicorn.workers.UvicornWorker " +
  "--workers 2 " +
  "--bind 0.0.0.0:9998 " +
  "--timeout 120 " +
  "--graceful-timeout 30 " +
  "--max-requests 1000 " +
  "--max-requests-jitter 100 " +
  "--forwarded-allow-ips=*",

      interpreter: "none",

      watch: false,
      kill_timeout: 5000,
      restart_delay: 2000,
      max_restarts: 10,

      out_file: `${APP_ROOT}/logs/api-out.log`,
      error_file: `${APP_ROOT}/logs/api-error.log`,
      merge_logs: true,

      env: commonEnv
    },

    {
      name: "gasman-device-sync",
      cwd: APP_ROOT,

      script: `${APP_ROOT}/services/device_sync.py`,
      interpreter: `${APP_ROOT}/venv/bin/python3`,

      watch: false,
      kill_timeout: 5000,
      restart_delay: 2000,

      out_file: `${APP_ROOT}/logs/device-sync-out.log`,
      error_file: `${APP_ROOT}/logs/device-sync-error.log`,
      merge_logs: true,

      env: commonEnv
    },

    {
      name: "gasman-proof-engine",
      cwd: APP_ROOT,

      script: `${APP_ROOT}/run_proof_engine_loop.py`,
      interpreter: `${APP_ROOT}/venv/bin/python3`,

      watch: false,
      kill_timeout: 5000,
      restart_delay: 2000,

      out_file: `${APP_ROOT}/logs/proof-out.log`,
      error_file: `${APP_ROOT}/logs/proof-error.log`,
      merge_logs: true,

      env: commonEnv
    },

    {
      name: "gasman-ws-listener",
      cwd: APP_ROOT,

      script: `${APP_ROOT}/services/ws_listener.py`,
      interpreter: `${APP_ROOT}/venv/bin/python3`,

      watch: false,
      kill_timeout: 5000,
      restart_delay: 2000,

      out_file: `${APP_ROOT}/logs/ws-listener-out.log`,
      error_file: `${APP_ROOT}/logs/ws-listener-error.log`,
      merge_logs: true,

      env: commonEnv
    }

  ]
};
