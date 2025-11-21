-- Switch to the correct database
USE data_logger;

-- Create `log_time_tracker` table if not exists
CREATE TABLE IF NOT EXISTS log_time_tracker (
    device_id VARCHAR(50) PRIMARY KEY,
    last_log_time DATETIME NOT NULL,
    device_status ENUM('online', 'offline') DEFAULT 'offline'
);