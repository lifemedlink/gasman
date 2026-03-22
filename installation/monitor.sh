#!/bin/bash

echo "=============================="
echo "📊 GASMAN SERVER STATUS"
echo "=============================="

echo ""
echo "🔹 CPU & Memory"
top -bn1 | grep "Cpu(s)"
free -h

echo ""
echo "🔹 Disk Usage"
df -h /

echo ""
echo "🔹 PM2 Process Status"
pm2 list

echo ""
echo "🔹 MySQL Status"
sudo systemctl is-active mysql

echo ""
echo "🔹 Redis Status"
sudo systemctl is-active redis-server

echo ""
echo "🔹 Active MySQL Connections"
mysql -uroot -proot -e "SHOW STATUS LIKE 'Threads_connected';"

echo ""
echo "=============================="
echo "✅ Monitoring check completed"
echo "=============================="
