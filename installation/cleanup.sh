#!/bin/bash

APP_ROOT="/home/lmltcpa/gas"
BACKUP_DIR="/home/lmltcpa/backups"
DAYS_OLD=7

echo "====================================="
echo "🧹 GASMAN SYSTEM CLEANUP STARTING..."
echo "====================================="

# =========================================================
# 1️⃣ Clean APT Cache
# =========================================================
echo "🔹 Cleaning apt cache..."
sudo apt autoremove -y
sudo apt autoclean -y
sudo apt clean

# =========================================================
# 2️⃣ Clear System Journal Logs (Keep 7 Days)
# =========================================================
echo "🔹 Cleaning system logs..."
sudo journalctl --vacuum-time=7d

# =========================================================
# 3️⃣ Clear PM2 Logs
# =========================================================
echo "🔹 Cleaning PM2 logs..."
pm2 flush

# =========================================================
# 4️⃣ Remove Old Application Logs
# =========================================================
echo "🔹 Removing old application logs..."
find $APP_ROOT/logs -type f -mtime +$DAYS_OLD -delete

# =========================================================
# 5️⃣ Remove Old Backups
# =========================================================
echo "🔹 Removing old database backups..."
find $BACKUP_DIR -type f -mtime +$DAYS_OLD -delete

# =========================================================
# 6️⃣ Remove Python Cache Files
# =========================================================
echo "🔹 Removing Python cache files..."
find $APP_ROOT -type d -name "__pycache__" -exec rm -r {} +
find $APP_ROOT -type f -name "*.pyc" -delete

# =========================================================
# 7️⃣ Clear Temporary Files
# =========================================================
echo "🔹 Cleaning /tmp directory..."
sudo find /tmp -type f -mtime +3 -delete

# =========================================================
# 8️⃣ Clear System Memory Cache (Safe)
# =========================================================
echo "🔹 Clearing memory cache..."
sudo sync
echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null

# =========================================================
# 9️⃣ Show Disk Usage After Cleanup
# =========================================================
echo ""
echo "📊 Disk usage after cleanup:"
df -h /

echo ""
echo "====================================="
echo "✅ CLEANUP COMPLETED SUCCESSFULLY"
echo "====================================="
