#!/bin/bash

APP_ROOT="/home/lmltcpa/gas"
BRANCH="main"

echo "🚀 Starting GASMAN deployment..."

cd $APP_ROOT || exit 1

echo "🔹 Pulling latest code..."
git fetch origin
git checkout $BRANCH
git pull origin $BRANCH

echo "🔹 Activating virtual environment..."
source venv/bin/activate

echo "🔹 Installing/Updating Python dependencies..."
pip install -r requirements.txt

echo "🔹 Restarting PM2 services (zero-downtime reload)..."
pm2 reload ecosystem.config.js --update-env

echo "🔹 Saving PM2 state..."
pm2 save

echo "✅ Deployment completed successfully!"
