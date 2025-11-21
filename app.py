from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
from datetime import datetime
import os
from google_api_key import GOOGLE_MAPS_API_KEY

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', '12345')

db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'root'),
    'database': os.getenv('DB_NAME', 'data_logger')
}

# -------------------------------
# LOGIN / LOGOUT
# -------------------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        user_name = request.form.get('user_name')
        password = request.form.get('password')

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM user_details WHERE user_name=%s AND password=%s", (user_name, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['loggedin'] = True
            session['user_name'] = user['user_name']
            return redirect(url_for('home'))
        else:
            msg = "Invalid credentials"

    return render_template("login.html", msg=msg)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------------------
# HOME
# -------------------------------
@app.route('/home')
def home():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    return render_template('home.html', user_name=session['user_name'], google_api_key=GOOGLE_MAPS_API_KEY)

# -------------------------------
# GET LOCATIONS (ALL LOW-GAS DEVICES for map & device-tab low list)
# -------------------------------
@app.route('/get_locations')
def get_locations():
    """
    Returns only LOW-GAS devices assigned to the logged-in user.
    gas_percentage = raw_gas * 20
    threshold_percent = (ang3_lower_limit / 1000) * 20
    ALWAYS returns low-gas devices (used by map + low-gas table).
    """
    if 'loggedin' not in session:
        return jsonify([])

    user_name = session['user_name']
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT user_id FROM user_details WHERE user_name=%s", (user_name,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify([])

    cursor.execute("SELECT device_id FROM user_device_list WHERE user_id=%s", (user['user_id'],))
    rows = cursor.fetchall()
    device_ids = [r['device_id'] for r in rows]
    if not device_ids:
        conn.close()
        return jsonify([])

    placeholders = ",".join(["%s"] * len(device_ids))

    query = f"""
        SELECT
            udl.device_id,
            d.gas_level AS gas_level_raw,
            COALESCE(d.coordinates, dl.coordinates) AS coordinates,
            d.log_time AS current_log_time,
            dl.customer_name,
            COALESCE(d.device_location, dl.address) AS device_location,
            a.ang3_lower_limit
        FROM user_device_list udl
        LEFT JOIN device_log_current d ON udl.device_id=d.device_id
        LEFT JOIN devicelist dl ON udl.device_id=dl.device_id
        LEFT JOIN analog a ON udl.device_id=a.device_id
        WHERE udl.device_id IN ({placeholders})
        ORDER BY d.log_time DESC
    """

    cursor.execute(query, tuple(device_ids))
    fetched = cursor.fetchall()
    conn.close()

    out = []
    now = datetime.now()
    seen = set()

    for r in fetched:
        device_id = r.get("device_id")
        if device_id in seen:
            continue
        seen.add(device_id)

        coords_raw = (r.get("coordinates") or "").strip()
        lat = lng = None
        if coords_raw:
            try:
                parts = coords_raw.replace(";", ",").split(",")
                if len(parts) >= 2:
                    lat = float(parts[0].strip())
                    lng = float(parts[1].strip())
            except:
                lat = lng = None

        raw_gas = None
        try:
            if r.get("gas_level_raw") is not None and r.get("gas_level_raw") != "":
                raw_gas = float(r.get("gas_level_raw"))
        except:
            raw_gas = None

        gas_percentage = None
        if raw_gas is not None:
            try:
                gas_percentage = raw_gas * 20.0
            except:
                gas_percentage = None

        ang3_lower_limit = None
        if r.get("ang3_lower_limit") not in (None, ""):
            try:
                ang3_lower_limit = float(r.get("ang3_lower_limit"))
            except:
                ang3_lower_limit = None

        threshold_percent = None
        if ang3_lower_limit is not None:
            try:
                threshold_percent = (ang3_lower_limit / 1000.0) * 20.0
            except:
                threshold_percent = None

        # decide Low Gas
        is_low_gas = False
        try:
            if threshold_percent is not None and gas_percentage is not None:
                is_low_gas = gas_percentage < threshold_percent
            else:
                if gas_percentage is not None and gas_percentage < 10.0:
                    is_low_gas = True
        except:
            is_low_gas = False

        if not is_low_gas:
            continue

        clt = r.get("current_log_time")
        clt_iso = clt.isoformat() if isinstance(clt, datetime) else None

        out.append({
            "device_id": device_id,
            "coordinates": f"{lat},{lng}" if lat is not None and lng is not None else "",
            "gas_level_raw": raw_gas,
            "gas_percentage": int(round(gas_percentage)) if gas_percentage is not None else None,
            "threshold_percent": int(round(threshold_percent)) if threshold_percent is not None else None,
            "device_location": r.get("device_location"),
            "customer_name": r.get("customer_name"),
            "current_log_time": clt_iso,
        })

    return jsonify(out)


# -------------------------------
# Combined device info (low + normal) for Device Information tab
# -------------------------------
@app.route('/device_info_combined')
def device_info_combined():
    """
    Returns assigned devices split into:
      - low_gas: gas% < threshold
      - normal_gas: gas% >= threshold (or No Data treated as normal)
    """
    if "loggedin" not in session:
        return jsonify({"low_gas": [], "normal_gas": []})

    user_name = session["user_name"]
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT user_id FROM user_details WHERE user_name=%s", (user_name,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({"low_gas": [], "normal_gas": []})

    cursor.execute("SELECT device_id FROM user_device_list WHERE user_id=%s", (user["user_id"],))
    assigned = cursor.fetchall()
    device_ids = [d["device_id"] for d in assigned]
    if not device_ids:
        conn.close()
        return jsonify({"low_gas": [], "normal_gas": []})

    placeholders = ",".join(["%s"] * len(device_ids))

    cursor.execute(f"""
        SELECT
            udl.device_id,
            d.gas_level AS gas_level_raw,
            COALESCE(d.coordinates, dl.coordinates) AS coordinates,
            d.log_time AS current_log_time,
            dl.customer_name,
            COALESCE(d.device_location, dl.address) AS device_location,
            a.ang3_lower_limit
        FROM user_device_list udl
        LEFT JOIN device_log_current d ON udl.device_id = d.device_id
        LEFT JOIN devicelist dl ON udl.device_id = dl.device_id
        LEFT JOIN analog a ON udl.device_id = a.device_id
        WHERE udl.device_id IN ({placeholders})
        ORDER BY d.log_time DESC
    """, tuple(device_ids))

    rows = cursor.fetchall()
    conn.close()

    seen = set()
    low = []
    normal = []

    for r in rows:
        device_id = r.get("device_id")
        if device_id in seen:
            continue
        seen.add(device_id)

        raw = r.get("gas_level_raw")
        gas_percent = None
        try:
            if raw not in (None, ""):
                gas_percent = float(raw) * 20.0
        except:
            gas_percent = None

        ang = r.get("ang3_lower_limit")
        try:
            threshold = (float(ang) / 1000.0) * 20.0 if ang not in (None, "") else 10.0
        except:
            threshold = 10.0

        gas_int = int(round(gas_percent)) if gas_percent is not None else None
        threshold_int = int(round(threshold))

        device_obj = {
            "device_id": device_id,
            "gas_percentage": gas_int,
            "threshold_percent": threshold_int,
            "customer_name": r.get("customer_name"),
            "device_location": r.get("device_location"),
            "coordinates": r.get("coordinates") or "",
            "last_log_time": str(r.get("current_log_time")) if r.get("current_log_time") else None
        }

        if gas_percent is None:
            device_obj["device_status"] = "No Data"
            normal.append(device_obj)
        else:
            if gas_percent < threshold:
                device_obj["device_status"] = f"Low Gas Level ({gas_int}%)"
                low.append(device_obj)
            else:
                device_obj["device_status"] = f"OK ({gas_int}%)"
                normal.append(device_obj)

    return jsonify({"low_gas": low, "normal_gas": normal})


if __name__ == "__main__":
    port = int(os.getenv('PORT', 9999))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
