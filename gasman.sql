/* ==========================================================
   GASMAN – FINAL PRODUCTION DATABASE SETUP
   MySQL 8.x
   SAFE • STABLE • SCALE READY • NO CRASH
========================================================== */
DROP DATABASE IF EXISTS gasman;
CREATE DATABASE IF NOT EXISTS gasman;
USE gasman;

SET autocommit = 1;

-- Required for scheduled events
SET GLOBAL event_scheduler = ON;

/* ==========================================================
   1. LIVE DEVICE STATUS (SINGLE SOURCE OF TRUTH)
========================================================== */
CREATE TABLE IF NOT EXISTS gasman_device_status (
    device_id VARCHAR(45) PRIMARY KEY,

    gas_percentage       DECIMAL(6,2) NOT NULL,
    gas_leak_percent     DECIMAL(6,2),
    tank_pressure_bar    DECIMAL(6,2),
    line_pressure_bar    DECIMAL(6,4),

    classification       ENUM('NORMAL','LOW','CRITICAL') NOT NULL,
    gas_alarm_status     ENUM('Safe','Alert','Issue') NOT NULL,
    operation_status     ENUM('Safe','Alert','Issue') NOT NULL,
    system_status        ENUM('OK','Fault') NOT NULL,

    tank_level_flag      ENUM('Safe','Alert','Issue') NOT NULL,
    line_pressure_flag   ENUM('Safe','Alert','Issue') NOT NULL,
    gas_leak_flag        ENUM('Safe','Alert','Issue') NOT NULL,

    power_fault          TINYINT(1) DEFAULT 0,
    device_offline       TINYINT(1) DEFAULT 0,

    device_location VARCHAR(255),
    coordinates     VARCHAR(100),

    last_log_time   DATETIME,
    online          TINYINT(1) DEFAULT 1,
    online_since    DATETIME,
    offline_since   DATETIME,

    gas_stable_since DATETIME DEFAULT NULL,

    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
               ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_gds_updated (updated_at),
    INDEX idx_gds_class (classification),
    INDEX idx_gds_gasstable (gas_stable_since)

) ENGINE=InnoDB;


/* ==========================================================
   2A. USER ROLES (AUTHORIZATION LAYER)
   ----------------------------------------------------------
   - Decouples GASMAN roles from data_logger
   - Controls dashboard access (admin/subadmin/driver)
========================================================== */

CREATE TABLE IF NOT EXISTS gasman_user_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data_logger_user_id INT NOT NULL UNIQUE
      COMMENT 'Ref → data_logger.user_details.user_id',

    role ENUM('admin','subadmin','driver')
         NOT NULL DEFAULT 'driver',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_user_role (role)
) ENGINE=InnoDB
COMMENT='Role mapping for GASMAN authorization';

/* ==========================================================
   2B. USER SESSIONS (ONE ACTIVE LOGIN PER USER)
   ----------------------------------------------------------
   - Enforces ONE active session per user
   - Replaces old session on new login
========================================================== */

DROP TABLE IF EXISTS gasman_user_sessions;

CREATE TABLE gasman_user_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,

    data_logger_user_id INT NOT NULL
      COMMENT 'Ref → data_logger.user_details.user_id',

    session_id VARCHAR(128) NOT NULL
      COMMENT 'JWT session binding id',

    device_fingerprint VARCHAR(512) NOT NULL
      COMMENT 'Browser or mobile fingerprint',

    ip_address VARCHAR(45)
      COMMENT 'IPv4 / IPv6',

    user_agent TEXT
      COMMENT 'Client user agent',

    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
      COMMENT 'Updated on every request',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      COMMENT 'Login timestamp',

    expires_at DATETIME
      COMMENT 'Hard session expiration time',

    UNIQUE KEY uq_user (data_logger_user_id),
    INDEX idx_session (session_id),
    INDEX idx_session_last_seen (last_seen),
    INDEX idx_session_expires (expires_at)

) ENGINE=InnoDB
COMMENT='Single active login per user (strict enforcement)';


/* ==========================================================
   2C. REFRESH TOKENS (MOBILE SUPPORT)
   ----------------------------------------------------------
   - Only ONE active refresh token per user
   - Old token invalidated on new login
========================================================== */

CREATE TABLE IF NOT EXISTS gasman_user_refresh_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,

    data_logger_user_id INT NOT NULL
      COMMENT 'Ref → data_logger.user_details.user_id',

    device_id VARCHAR(100)
      COMMENT 'Mobile device identifier',

    refresh_token_hash VARCHAR(255) NOT NULL
      COMMENT 'Store HASH only (never raw token)',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    is_active TINYINT(1) DEFAULT 1,

    UNIQUE KEY uq_refresh_user (data_logger_user_id),
    INDEX idx_refresh_user (data_logger_user_id)
) ENGINE=InnoDB
COMMENT='Refresh token store (one active device per user)';

/* ==========================================================
   SESSION CLEANUP EVENT (LONG-RUNNING SERVER SAFE)
   - Removes inactive sessions
   - Removes expired sessions
========================================================== */

DROP EVENT IF EXISTS ev_cleanup_user_sessions;

DELIMITER $$

CREATE EVENT ev_cleanup_user_sessions
ON SCHEDULE EVERY 10 MINUTE
ON COMPLETION PRESERVE
DO
BEGIN
    DELETE FROM gasman_user_sessions
    WHERE last_seen < (NOW() - INTERVAL 8 HOUR)
       OR (expires_at IS NOT NULL AND expires_at < NOW());
END$$

DELIMITER ;

/* ==========================================================
   3. TASKS (HARD-LOCKED, RACE SAFE)
========================================================== */
CREATE TABLE IF NOT EXISTS gasman_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,

    device_id VARCHAR(45) NOT NULL,
    priority ENUM('LOW','CRITICAL') DEFAULT 'LOW',

    user_name VARCHAR(100) NOT NULL,
    accepted_by VARCHAR(100),

initial_gas_level DECIMAL(6,2) DEFAULT 0
    COMMENT 'Gas level when driver starts filling',

final_gas_level DECIMAL(6,2) DEFAULT NULL
    COMMENT 'Gas level when tank filling completed',

    status ENUM(
      'PENDING',
      'ASSIGNED',
      'EN_ROUTE',
      'ON_SITE',
      'FILLING',
      'FILLED',
      'COMPLETED',
      'REJECTED',
      'CANCELLED'
    ) DEFAULT 'PENDING',

    tracking_id VARCHAR(40),

    accepted_at DATETIME,
    started_navigation_at DATETIME,
    assigned_at DATETIME,
    en_route_at DATETIME,
    on_site_at DATETIME,
    completed_at DATETIME,
    last_ping_at DATETIME,

    onsite_source ENUM('MANUAL','AUTO'),

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
               ON UPDATE CURRENT_TIMESTAMP,

    active_device_id VARCHAR(45)
      GENERATED ALWAYS AS (
        CASE
          WHEN status IN ('ASSIGNED','EN_ROUTE','ON_SITE','FILLING','FILLED')
          THEN device_id
          ELSE NULL
        END
      ) STORED,

    UNIQUE KEY uq_active_device (active_device_id),
    INDEX idx_gt_status (status),
    INDEX idx_gt_priority (priority),
    INDEX idx_gt_user_status (accepted_by, status),
    INDEX idx_gt_device (device_id),
    INDEX idx_gt_created (created_at)
) ENGINE=InnoDB;

/* ==========================================================
   4. TASK ACTIVITY (AUDIT LOG - FSM SAFE VERSION)
   ----------------------------------------------------------
   • Stores immutable task lifecycle events
   • Prevents duplicate status entries
   • Optimized for timeline queries
   • Optimized for tracking lookup
========================================================== */

CREATE TABLE IF NOT EXISTS gasman_task_activity (
    id INT AUTO_INCREMENT PRIMARY KEY,

    task_id INT,
    device_id VARCHAR(45),
    user_name VARCHAR(100),

    action VARCHAR(64)
        COMMENT 'Driver/system action',

    status_after VARCHAR(32)
        COMMENT 'FSM state after action',

    tracking_id VARCHAR(40)
        COMMENT 'Public tracking reference',

    note TEXT
        COMMENT 'Optional explanation',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

/* PERFORMANCE INDEXES */

INDEX idx_gta_task (task_id),
INDEX idx_gta_device (device_id),

INDEX idx_gta_tracking (tracking_id),
INDEX idx_gta_tracking_time (tracking_id, created_at),

INDEX idx_gta_status (status_after),

INDEX idx_gta_created (created_at),

    /* ======================================================
       FSM SAFETY
       Prevent duplicate state logs per task
    ====================================================== */

    UNIQUE KEY uq_task_state (
        task_id,
        status_after
    ),

    /* ======================================================
       FOREIGN KEY
    ====================================================== */

    CONSTRAINT fk_gta_task
      FOREIGN KEY (task_id)
      REFERENCES gasman_tasks(id)
      ON DELETE CASCADE

) ENGINE=InnoDB
COMMENT='Task lifecycle audit log (FSM event store)';

/* ==========================================================
   5. USER LOCATION HISTORY
========================================================== */
CREATE TABLE IF NOT EXISTS gasman_user_location_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_name VARCHAR(100) NOT NULL,
    lat DECIMAL(10,7) NOT NULL,
    lng DECIMAL(10,7) NOT NULL,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_ulh_user_time (user_name, recorded_at)
) ENGINE=InnoDB;

/* ==========================================================
   6. USER TASK SETTINGS
========================================================== */
CREATE TABLE IF NOT EXISTS gasman_user_settings (
    user_name VARCHAR(100) PRIMARY KEY,
    task_enabled TINYINT(1) DEFAULT 1,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
               ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

/* Safe index creation */
SET @idx_exists = (
    SELECT COUNT(1)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'gasman_user_settings'
      AND index_name = 'idx_gus_task_enabled'
);

SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_gus_task_enabled ON gasman_user_settings (task_enabled)',
    'SELECT ''Index already exists''');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;



/* ==========================================================
   7. GAS PARAMETERS
========================================================== */
CREATE TABLE IF NOT EXISTS gasman_gas_parameters (
    id INT AUTO_INCREMENT PRIMARY KEY,
    molecular_weight_M DECIMAL(8,4) NOT NULL,
    specific_gravity_S DECIMAL(8,4) NOT NULL,
    operating_pressure_LP DECIMAL(8,4) NOT NULL,
    temperature_T DECIMAL(8,4) NOT NULL,
    gas_constant_G DECIMAL(12,6),
    updated_by VARCHAR(100),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active TINYINT(1) DEFAULT 1
) ENGINE=InnoDB;

/* ==========================================================
   8. CONSUMPTION TABLES
========================================================== */
CREATE TABLE IF NOT EXISTS gasman_consumption_daily (
    device_id VARCHAR(45),
    reading_date DATE,
    gas_volume DECIMAL(10,2),
    PRIMARY KEY (device_id, reading_date)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS gasman_consumption_monthly (
    device_id VARCHAR(45),
    ym CHAR(6),
    gas_volume DECIMAL(12,2),
    PRIMARY KEY (device_id, ym)
) ENGINE=InnoDB;

/* ==========================================================
   9. TRACKING COUNTERS (DAILY SEQUENCE)
========================================================== */
CREATE TABLE IF NOT EXISTS tracking_counters (
    dt CHAR(8) PRIMARY KEY,
    seq INT NOT NULL
) ENGINE=InnoDB;

/* ==========================================================
   10. AUTO CALC PROCEDURES
========================================================== */

DROP PROCEDURE IF EXISTS sp_calc_gas_daily;

DELIMITER $$

CREATE PROCEDURE sp_calc_gas_daily(IN p_date DATE)
BEGIN
  INSERT INTO gasman_consumption_daily
  SELECT
    device_id,
    p_date,
    ((MAX(meter1)-MIN(meter1))/100) *
    (SELECT gas_constant_G FROM gasman_gas_parameters
     WHERE is_active=1 LIMIT 1)
  FROM data_logger.gasman_meter_history
  WHERE reading_date = p_date
  GROUP BY device_id
  ON DUPLICATE KEY UPDATE gas_volume = VALUES(gas_volume);
END$$

DELIMITER ;

/* ==========================================================
   11. LIVE DEVICE STATUS REFRESH
========================================================== */

SET GLOBAL event_scheduler = ON;
DROP EVENT IF EXISTS ev_refresh_gasman_device_status;
DELIMITER $$

CREATE EVENT ev_refresh_gasman_device_status
ON SCHEDULE EVERY 5 SECOND
DO
BEGIN
  INSERT INTO gasman_device_status (
    device_id,
    gas_percentage,
    gas_leak_percent,
    tank_pressure_bar,
    line_pressure_bar,

    classification,
    gas_alarm_status,
    operation_status,
    system_status,

    tank_level_flag,
    line_pressure_flag,
    gas_leak_flag,

    power_fault,
    device_offline,

    device_location,
    coordinates,
    last_log_time,

    online,
    online_since,
    offline_since,

    gas_stable_since,
    updated_at
  )
  SELECT
    d.device_id,

    /* ================= RAW VALUES ================= */
    ROUND((d.gas_level / 5) * 100, 0) AS gas_percentage,

    CASE
      WHEN d.gas_detector <= 4 THEN 0
      WHEN d.gas_detector >= 20 THEN 100
      ELSE ROUND(((d.gas_detector - 4) / 16) * 100, 0)
    END AS gas_leak_percent,

    ROUND((d.tank_pressure / 5) * 20, 2),
    ROUND((d.line_pressure / 5) * 2, 4),

    /* ================= CLASSIFICATION ================= */
    CASE
      WHEN (d.gas_level * 1000) < a.ang3_lower_limit THEN 'CRITICAL'
      WHEN (d.gas_level * 1000) < (a.ang3_lower_limit * 2) THEN 'LOW'
      ELSE 'NORMAL'
    END AS classification,

    /* ================= GAS ALARM ================= */
    CASE
      WHEN d.gas_detector >= (a.ang2_lower_limit / 1000) THEN 'Issue'
      WHEN ((d.gas_detector - 4) / 16) * 100 >= 15 THEN 'Alert'
      ELSE 'Safe'
    END AS gas_alarm_status,

    /* ================= OPERATION ================= */
    CASE
      WHEN (d.line_pressure * 1000) < a.ang5_lower_limit
        OR (d.gas_level * 1000) < a.ang3_lower_limit THEN 'Issue'
      WHEN (d.line_pressure * 1000) < (a.ang5_lower_limit * 2)
        OR (d.gas_level * 1000) < (a.ang3_lower_limit * 2) THEN 'Alert'
      ELSE 'Safe'
    END AS operation_status,

    /* ================= SYSTEM ================= */
    CASE
      WHEN d.log_time IS NULL
        OR TIMESTAMPDIFF(SECOND, d.log_time, NOW()) > (sc.http_post_interval * 4)
        OR (d.power_level * 1000) < a.ang6_lower_limit THEN 'Fault'
      ELSE 'OK'
    END AS system_status,

    /* ================= CAUSE FLAGS (UI COMMENTS) ================= */
    CASE
      WHEN (d.gas_level * 1000) < a.ang3_lower_limit THEN 'Issue'
      WHEN (d.gas_level * 1000) < (a.ang3_lower_limit * 2) THEN 'Alert'
      ELSE 'Safe'
    END AS tank_level_flag,

    CASE
      WHEN (d.line_pressure * 1000) < a.ang5_lower_limit THEN 'Issue'
      WHEN (d.line_pressure * 1000) < (a.ang5_lower_limit * 2) THEN 'Alert'
      ELSE 'Safe'
    END AS line_pressure_flag,

    CASE
      WHEN d.gas_detector >= (a.ang2_lower_limit / 1000) THEN 'Issue'
      WHEN ((d.gas_detector - 4) / 16) * 100 >= 15 THEN 'Alert'
      ELSE 'Safe'
    END AS gas_leak_flag,

    /* ================= POWER / OFFLINE ================= */
    IF((d.power_level * 1000) < a.ang6_lower_limit, 1, 0),

    IF(
      d.log_time IS NULL
      OR TIMESTAMPDIFF(SECOND, d.log_time, NOW()) > (sc.http_post_interval * 4),
      1, 0
    ),

    /* ================= META ================= */
    d.device_location,
    d.coordinates,
    d.log_time,

    IF(TIMESTAMPDIFF(SECOND, d.log_time, NOW()) <= (sc.http_post_interval * 4), 1, 0),
    IF(TIMESTAMPDIFF(SECOND, d.log_time, NOW()) <= (sc.http_post_interval * 4), NOW(), NULL),
    IF(TIMESTAMPDIFF(SECOND, d.log_time, NOW()) >  (sc.http_post_interval * 4), NOW(), NULL),

    /* ================= GAS STABILITY ================= */
    CASE
      WHEN
        ROUND((d.gas_level / 5) * 100, 0) >= 85
        AND (d.gas_level * 1000) >= (a.ang3_lower_limit * 2)
      THEN NOW()
      ELSE NULL
    END AS gas_stable_since,

    NOW()

  FROM data_logger.device_log_current d
  JOIN data_logger.analog a        ON a.device_id = d.device_id
  JOIN data_logger.slave_config sc ON sc.device_id = d.device_id
 ON DUPLICATE KEY UPDATE
    gas_percentage      = VALUES(gas_percentage),
    gas_leak_percent    = VALUES(gas_leak_percent),
    tank_pressure_bar   = VALUES(tank_pressure_bar),
    line_pressure_bar   = VALUES(line_pressure_bar),

    classification      = VALUES(classification),
    gas_alarm_status    = VALUES(gas_alarm_status),
    operation_status    = VALUES(operation_status),
    system_status       = VALUES(system_status),

    tank_level_flag     = VALUES(tank_level_flag),
    line_pressure_flag  = VALUES(line_pressure_flag),
    gas_leak_flag       = VALUES(gas_leak_flag),

    power_fault         = VALUES(power_fault),
    device_offline      = VALUES(device_offline),

    device_location     = VALUES(device_location),
    coordinates         = VALUES(coordinates),
    last_log_time       = VALUES(last_log_time),

    online              = VALUES(online),
    online_since        = IF(VALUES(online)=1 AND online=0, NOW(), online_since),
    offline_since       = IF(VALUES(online)=0 AND online=1, NOW(), offline_since),

    gas_stable_since =
      CASE
        WHEN VALUES(gas_percentage) >= 85
         AND VALUES(classification) = 'NORMAL'
        THEN IF(gas_stable_since IS NULL, NOW(), gas_stable_since)
        ELSE NULL
      END,

    updated_at = NOW();
END$$
DELIMITER ;
/* ==========================================================
   12. AUTO TASK CREATION (AUTO USERS ONLY)
   - Only for users with task_enabled = 1
   - Manual users (task_enabled = 0) get NO system tasks
========================================================== */

DROP EVENT IF EXISTS ev_create_gasman_tasks;
DELIMITER $$

CREATE EVENT ev_create_gasman_tasks
ON SCHEDULE EVERY 10 SECOND
DO
BEGIN

  /* =======================================================
     STEP 1: CREATE AUTO TASKS ONLY FOR AUTO USERS
  ======================================================= */

  INSERT INTO gasman_tasks (
      device_id,
      priority,
      user_name,
      status,
      created_at
  )
  SELECT
      g.device_id,
      g.classification,
      'SYSTEM',
      'PENDING',
      NOW()
  FROM gasman_device_status g

  /* Join device → user → user_settings */
  JOIN data_logger.user_device_list ud
        ON ud.device_id = g.device_id

  JOIN data_logger.user_details u
        ON u.user_id = ud.user_id

  JOIN gasman_user_settings us
        ON us.user_name = u.user_name

  WHERE
      g.classification IN ('LOW','CRITICAL')
      AND g.online = 1

      /* AUTO USERS ONLY */
      AND us.task_enabled = 1

      /* No active task */
      AND NOT EXISTS (
          SELECT 1
          FROM gasman_tasks t
          WHERE t.device_id = g.device_id
            AND t.status IN ('PENDING','ASSIGNED','EN_ROUTE','ON_SITE')
      )

      /* Cooldown after reject (1 min) */
      AND NOT EXISTS (
          SELECT 1
          FROM gasman_tasks t2
          WHERE t2.device_id = g.device_id
            AND t2.status = 'REJECTED'
            AND t2.updated_at >= NOW() - INTERVAL 1 MINUTE
      );



END$$

DELIMITER ;


/* ==========================================================
   13. TASK TIMEOUT WATCHDOG
========================================================== */

DROP EVENT IF EXISTS ev_cancel_stuck_tasks;

DELIMITER $$

CREATE EVENT ev_cancel_stuck_tasks
ON SCHEDULE EVERY 5 MINUTE
DO
BEGIN

  UPDATE gasman_tasks
  SET status='CANCELLED', updated_at=NOW()
  WHERE status IN ('ASSIGNED','EN_ROUTE','ON_SITE')
    AND last_ping_at < NOW() - INTERVAL 720 MINUTE;

  INSERT IGNORE INTO gasman_task_activity
    (task_id, device_id, user_name, action, status_after, tracking_id, note)
  SELECT
    t.id,
    t.device_id,
    t.accepted_by,
    'CANCELLED',
    'CANCELLED',
    t.tracking_id,
    'Auto-cancel due to inactivity'
  FROM gasman_tasks t
  WHERE t.status='CANCELLED'
    AND t.updated_at >= NOW() - INTERVAL 5 MINUTE;

END$$

DELIMITER ;
/* ==========================================================
   14. AUTO COMPLETE TASK (FSM SAFE VERSION)
========================================================== */

DROP EVENT IF EXISTS ev_complete_gasman_tasks;

DELIMITER $$

CREATE EVENT ev_complete_gasman_tasks
ON SCHEDULE EVERY 5 SECOND
DO
BEGIN

  UPDATE gasman_tasks t
  JOIN gasman_device_status g
    ON g.device_id = t.device_id
  SET
    t.status = 'COMPLETED',
    t.completed_at = NOW(),
    t.updated_at = NOW()
  WHERE
    t.status = 'FILLED'
    AND g.gas_stable_since IS NOT NULL
    AND g.classification = 'NORMAL'
    AND TIMESTAMPDIFF(SECOND, g.gas_stable_since, NOW()) >= 10;

  INSERT IGNORE INTO gasman_task_activity
      (task_id, device_id, user_name, action, status_after, tracking_id, note)
  SELECT
      t.id,
      t.device_id,
      t.accepted_by,
      'AUTO_COMPLETED',
      'COMPLETED',
      t.tracking_id,
      'Auto completed after gas stable ≥10s'
  FROM gasman_tasks t
  WHERE
      t.status = 'COMPLETED'
      AND t.completed_at >= NOW() - INTERVAL 10 SECOND;

END$$

DELIMITER ;

/* ==========================================================
   15. AUTO PROMOTE EN_ROUTE → ON_SITE (REMOTE FILL)
========================================================== */
DROP EVENT IF EXISTS ev_autopromote_enroute_to_onsite;

DELIMITER $$

CREATE EVENT ev_autopromote_enroute_to_onsite
ON SCHEDULE EVERY 10 SECOND
DO
BEGIN

  UPDATE gasman_tasks t
  JOIN gasman_device_status g
    ON g.device_id = t.device_id
  SET
    t.status        = 'ON_SITE',
    t.on_site_at    = NOW(),
    t.onsite_source = 'AUTO',
    t.updated_at    = NOW()
  WHERE
    t.status = 'EN_ROUTE'
    AND t.on_site_at IS NULL
    AND g.gas_stable_since IS NOT NULL
    AND TIMESTAMPDIFF(SECOND, g.gas_stable_since, NOW()) >= 10;

  INSERT IGNORE INTO gasman_task_activity
    (task_id, device_id, user_name, action, status_after, tracking_id, note)
  SELECT
    t.id,
    t.device_id,
    t.accepted_by,
    'AUTO_ON_SITE',
    'ON_SITE',
    t.tracking_id,
    'Auto-promoted to ON_SITE'
  FROM gasman_tasks t
  WHERE
    t.status = 'ON_SITE'
    AND t.onsite_source = 'AUTO';

END$$

DELIMITER ;
