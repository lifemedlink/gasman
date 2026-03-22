#!/bin/bash

set -e

CONF="/etc/mysql/mysql.conf.d/mysqld.cnf"
BACKUP="/etc/mysql/mysql.conf.d/mysqld.cnf.bak.$(date +%F_%T)"

echo "🔹 Backing up MySQL config..."
sudo cp $CONF $BACKUP
echo "Backup created at: $BACKUP"

echo "🔹 Updating max_connections to 300..."

if grep -q "^max_connections" $CONF; then
    sudo sed -i 's/^max_connections.*/max_connections = 300/' $CONF
else
    echo -e "\nmax_connections = 300" | sudo tee -a $CONF > /dev/null
fi

echo "🔹 Restarting MySQL..."
sudo systemctl restart mysql

echo "✅ MySQL tuning complete."
echo "👉 Please verify manually using:"
echo "   sudo mysql -uroot -p -e \"SHOW VARIABLES LIKE 'max_connections';\""
