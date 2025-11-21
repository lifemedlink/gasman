#!/bin/bash

echo "========================================"
echo "   GASMAN AUTO SETUP + RUN SCRIPT"
echo "========================================"

# Move to project folder
cd "$(dirname "$0")"

# ----------------------------------------
# STEP 1 — Delete OLD venv (clean reset)
# ----------------------------------------
if [ -d "venv" ]; then
    echo "Deleting old virtual environment..."
    rm -rf venv
fi

# ----------------------------------------
# STEP 2 — Create NEW virtual environment
# ----------------------------------------
echo "Creating new virtual environment..."
python3 -m venv venv

# ----------------------------------------
# STEP 3 — Activate venv
# ----------------------------------------
echo "Activating virtual environment..."
source venv/bin/activate

# ----------------------------------------
# STEP 4 — Upgrade pip (recommended)
# ----------------------------------------
echo "Upgrading pip..."
pip install --upgrade pip

# ----------------------------------------
# STEP 5 — Install requirements
# ----------------------------------------
echo "Installing required packages..."
pip install flask mysql-connector-python
pip install -r requirements.txt --break-system-packages || pip install -r requirements.txt

# ----------------------------------------
# STEP 6 — Start Flask App
# ----------------------------------------
echo "----------------------------------------"
echo " Starting GASMAN Flask Server"
echo "----------------------------------------"
python3 app.py
