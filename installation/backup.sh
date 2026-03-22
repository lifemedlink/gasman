#!/bin/bash

DB_USER="root"
DB_PASS="root"
DATA_LOGGER_DB="data_logger"
GASMAN_DB="gasman"

BACKUP_DIR="/home/lmltcpa/backups"
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

mkdir -p $BACKUP_DIR

echo "📦 Starting database backup..."

mysqldump -u$DB_USER -p$DB_PASS $DATA_LOGGER_DB > $BACKUP_DIR/data_logger_$DATE.sql
mysqldump -u$DB_USER -p$DB_PASS $GASMAN_DB > $BACKUP_DIR/gasman_$DATE.sql

echo "🧹 Cleaning backups older than 7 days..."
find $BACKUP_DIR -type f -mtime +7 -delete

echo "✅ Backup completed successfully!"
