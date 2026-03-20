<<<<<<< HEAD
import os
import mysql.connector
import math
import csv
import json
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
)
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

app = Flask(__name__)
CORS(app)
app.url_map.strict_slashes = False
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 🔑 Secuirty Keys - PERSISTENT for Render
# We use a fixed key so that if Render restarts, tokens and QR codes still work.
app.config["JWT_SECRET_KEY"] = "attendance-system-v1-key-2024" 
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)
jwt = JWTManager(app)

# 🗝️ Encryption for QR codes - Fixed key for persistence
# We use a fixed key so that if Render restarts, existing QR codes can still be decrypted.
# This is a valid 32-byte URL-safe base64 Fernet key.
cipher_suite = Fernet(b'ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=')

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Delvin@2005",
    "database": "qr_attendence"
}

def get_db():
    conn = mysql.connector.connect(**DATABASE_CONFIG)
    return conn

@app.route("/api/health")
def health_check():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        conn.close()
        return jsonify({
            "status": "healthy",
            "db_users": user_count,
            "time": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def init_db():
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # 1. Users Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) UNIQUE,
        password TEXT,
        role VARCHAR(50),
        name VARCHAR(255),
        roll_no VARCHAR(100),
        branch VARCHAR(100),
        semester VARCHAR(50),
        device_id VARCHAR(255)
    )
    """)

    # 2. Sessions Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        faculty_id INT,
        branch VARCHAR(100),
        semester VARCHAR(50),
        subject VARCHAR(255),
        start_time TEXT,
        latitude DOUBLE,
        longitude DOUBLE,
        expires_at TEXT,
        radius INT DEFAULT 20
    )
    """)

    # 3. Attendance Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INT AUTO_INCREMENT PRIMARY KEY,
        session_id INT,
        student_id INT,
        status VARCHAR(50),
        marked_at TEXT
    )
    """)

    # 4. Subjects Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(100) UNIQUE,
        name VARCHAR(255),
        branch VARCHAR(100),
        semester VARCHAR(50)
    )
    """)

    # 5. Timetable Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS timetable (
        id INT AUTO_INCREMENT PRIMARY KEY,
        faculty_id INT,
        subject_id INT,
        day_of_week VARCHAR(20),
        start_time VARCHAR(20),
        end_time VARCHAR(20),
        branch VARCHAR(100),
        semester VARCHAR(50)
    )
    """)

    conn.commit()

    # 🚀 Auto-seed default users if database is empty
    cur.execute("SELECT COUNT(*) as count FROM users")
    if cur.fetchone()['count'] == 0:
        print("Seeding default users...")
        default_users = [
            ("admin1", generate_password_hash("admin123"), "admin", "Admin User")
        ]
        for username, password, role, name in default_users:
            cur.execute(
                "INSERT INTO users (username, password, role, name) VALUES (%s, %s, %s, %s)",
                (username, password, role, name)
            )
        conn.commit()

    # 📂 Import students from CSV if available
    try:
        csv_path = os.path.join(BASE_DIR, "students.csv")
        if os.path.exists(csv_path):
            with open(csv_path, newline='', encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cur.execute("SELECT 1 FROM users WHERE username=%s", (row["username"],))
                    if cur.fetchone():
                        continue
                        
                    semester = row.get("semester", "N/A")
                    branch = row.get("branch", "N/A")
                    name = row.get("name", "N/A")
                    roll_no = row.get("roll_no", "N/A")
                    
                    cur.execute("""
                        INSERT INTO users 
                        (username, password, role, name, roll_no, branch, semester)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        row["username"],
                        generate_password_hash(row["password"]),
                        row["role"],
                        name,
                        roll_no,
                        branch,
                        semester
                    ))
            conn.commit()
            print("Student CSV data imported successfully.")
    except Exception as e:
        print(f"Error importing students: {e}")

    # 🧑‍🏫 Import faculty from CSV if available
    try:
        csv_path = os.path.join(BASE_DIR, "faculty.csv")
        if os.path.exists(csv_path):
            with open(csv_path, newline='', encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cur.execute("SELECT 1 FROM users WHERE username=%s", (row["username"],))
                    if cur.fetchone():
                        continue

                    semester = row.get("semester", "N/A")
                    branch = row.get("branch", "N/A")
                    name = row.get("name", "N/A")
                    
                    cur.execute("""
                        INSERT INTO users 
                        (username, password, role, name, branch, semester)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        row["username"],
                        generate_password_hash(row["password"]),
                        "faculty",
                        name,
                        branch,
                        semester
                    ))
            conn.commit()
            print("Faculty CSV data imported successfully.")
    except Exception as e:
        print(f"Error importing faculty: {e}")

    conn.close()

init_db()

# 📍 Distance calculation (Haversine)
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c



# 🔐 Login API
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    device_id = data.get("device_id")

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT id, username, password, role, name, roll_no, branch, semester, device_id FROM users WHERE username=%s",
        (username,)
    )
    user = cur.fetchone()

    if user and check_password_hash(user["password"], password):
        # 📱 Device Binding Logic for Students
        user_role = user["role"]
        stored_device = user["device_id"]
        
        if user_role == "student":
            if not device_id:
                conn.close()
                return jsonify({"success": False, "message": "Device identification missing"}), 400
            
            if stored_device is None:
                # First time login on this device - Bind it
                cur.execute("UPDATE users SET device_id = %s WHERE id = %s", (device_id, user["id"]))
                conn.commit()
            elif stored_device != device_id:
                conn.close()
                return jsonify({
                    "success": False, 
                    "message": "Access Denied: This account is linked to another device. Contact Admin to reset."
                }), 403

        conn.close()
        access_token = create_access_token(
            identity=str(user["id"]), 
            additional_claims={"role": user["role"]}
        )
        user_data = {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "name": user["name"],
            "branch": user["branch"],
            "semester": user["semester"]
        }
        return jsonify({"success": True, "message": "Logged in successfully", "access_token": access_token, "user": user_data})
    else:
        conn.close()
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route("/api/whoami", methods=["GET"])
@jwt_required()
def whoami():
    current_user_id = get_jwt_identity()
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username, role, name, branch, semester FROM users WHERE id = %s", (current_user_id,))
    user = cur.fetchone()
    conn.close()
    if user:
        return jsonify({"success": True, "user": dict(user)})
    return jsonify({"success": False, "message": "User not found"}), 404


# 🧑‍🏫 Faculty: Create QR Session
@app.route("/api/sessions", methods=["POST"])
@jwt_required()
def create_session():
    claims = get_jwt()
    if claims.get("role") not in ["faculty", "admin"]:
        return jsonify({"success": False, "message": "Unauthorized. Faculty only."}), 403

    data = request.json
    faculty_id = get_jwt_identity()
    branch = data.get("branch")
    semester = data.get("semester")
    subject = data.get("subject")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    radius = data.get("radius", 20)

    if latitude is None or longitude is None:
        return jsonify({
            "success": False, 
            "message": "GPS coordinates are required. Please ensure your location is turned on and permitted."
        }), 400

    start_time = datetime.now().isoformat()
    expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        INSERT INTO sessions (faculty_id, branch, semester, subject, start_time, latitude, longitude, expires_at, radius)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (faculty_id, branch, semester, subject, start_time, latitude, longitude, expires_at, radius)
    )
    conn.commit()
    session_id = cur.lastrowid
    conn.close()

    return jsonify({"success": True, "session_id": session_id})

# 🧑‍🏫 Faculty: Get active session QR
@app.route("/api/sessions/<int:session_id>/qr", methods=["GET"])
@jwt_required()
def get_session_qr(session_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM sessions WHERE id=%s", (session_id,))
    session = cur.fetchone()
    conn.close()

    if not session:
        return jsonify({"success": False, "message": "Invalid session"}), 400

    if datetime.now() > datetime.fromisoformat(session["expires_at"]):
        return jsonify({"success": False, "message": "Session expired"}), 400

    payload_data = {
        "session_id": session_id,
        "timestamp": datetime.now().isoformat()
    }
    encrypted_payload = cipher_suite.encrypt(json.dumps(payload_data).encode()).decode()

    return jsonify({"success": True, "qr_payload": encrypted_payload})


# 🎓 Student: Mark Attendance (Geo + Present/Late)
@app.route("/api/attendance", methods=["POST"])
@jwt_required()
def mark_attendance():
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized. Student only."}), 403

    data = request.json
    qr_payload = data.get("qr_payload")
    student_id = get_jwt_identity()
    student_lat = data.get("latitude")
    student_lng = data.get("longitude")

    if student_lat is None or student_lng is None:
        return jsonify({
            "success": False, 
            "message": "GPS coordinates are required to mark attendance."
        }), 400

    if not qr_payload:
        return jsonify({"success": False, "message": "Missing qr_payload"}), 400

    # Decrypt the payload
    try:
        decrypted_bytes = cipher_suite.decrypt(qr_payload.encode())
        payload_data = json.loads(decrypted_bytes.decode())
    except InvalidToken:
        return jsonify({"success": False, "message": "Invalid or tampered QR Code"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": "Malformed QR payload"}), 400

    session_id = payload_data.get("session_id")
    qr_timestamp = datetime.fromisoformat(payload_data.get("timestamp"))

    # Rotating QR: Ensure the QR code was generated no more than 30 seconds ago!
    now = datetime.now()
    if (now - qr_timestamp).total_seconds() > 30:
        return jsonify({"success": False, "message": "QR Code expired. Scan the latest one on screen."}), 400

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM sessions WHERE id=%s", (session_id,))
    session = cur.fetchone()

    if not session:
        conn.close()
        return jsonify({"success": False, "message": "Invalid session"}), 400

    now = datetime.now()
    expires_at = datetime.fromisoformat(session["expires_at"])
    start_time = datetime.fromisoformat(session["start_time"])

    if now > expires_at:
        conn.close()
        return jsonify({"success": False, "message": "QR expired"}), 400

    # 📍 Geofence Check
    teacher_lat = session["latitude"]
    teacher_lng = session["longitude"]
    
    allowed_radius = session.get("radius") or 20

    if teacher_lat is not None and student_lat is not None:
        distance = haversine(teacher_lat, teacher_lng, student_lat, student_lng)
        
        # We use the radius specified by the faculty (default 20m)
        if distance > allowed_radius:
            conn.close()
            return jsonify({
                "success": False, 
                "message": f"Outside allowed area! Distance: {int(distance)}m. Max allowed: {allowed_radius}m."
            }), 403

    # Prevent duplicate
    cur.execute(
        "SELECT id FROM attendance WHERE session_id=%s AND student_id=%s",
        (session_id, student_id)
    )
    if cur.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Already marked"}), 400

    diff_minutes = (now - start_time).total_seconds() / 60
    status = "Present" if diff_minutes <= 10 else "Late"

    cur.execute(
        "INSERT INTO attendance (session_id, student_id, status, marked_at) VALUES (%s, %s, %s, %s)",
        (session_id, student_id, status, now.isoformat())
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "status": status})

# 📋 Faculty: Get Live Attendance List for a Session
@app.route("/api/sessions/<int:session_id>/live", methods=["GET"])
@jwt_required()
def get_live_attendance(session_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Get session info
    cur.execute("SELECT * FROM sessions WHERE id=%s", (session_id,))
    session = cur.fetchone()
    if not session:
        conn.close()
        return jsonify({"success": False, "message": "Session not found"}), 404

    # Get all attendance records with student details
    cur.execute("""
        SELECT a.student_id, a.status, a.marked_at,
               u.name, u.roll_no, u.branch, u.semester
        FROM attendance a
        JOIN users u ON a.student_id = u.id
        WHERE a.session_id = %s
        ORDER BY a.marked_at DESC
    """, (session_id,))
    rows = cur.fetchall()
    conn.close()

    attendance = [dict(r) for r in rows]
    return jsonify({
        "success": True,
        "attendance": attendance,
        "session": dict(session)
    })

# 📍 Faculty: Update Session Location (teacher moves around)
@app.route("/api/sessions/<int:session_id>/location", methods=["PUT"])
@jwt_required()
def update_session_location(session_id):
    data = request.json
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "UPDATE sessions SET latitude=%s, longitude=%s WHERE id=%s",
        (latitude, longitude, session_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# --- Faculty Home: Dashboard Info ---
@app.route("/api/faculty/dashboard", methods=["GET"])
@jwt_required()
def get_faculty_dashboard():
    faculty_id = get_jwt_identity()
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # Get active session
    cur.execute("SELECT id, subject, branch, semester FROM sessions WHERE faculty_id=%s AND expires_at > %s ORDER BY id DESC LIMIT 1", 
                (faculty_id, datetime.now().isoformat()))
    active_session = cur.fetchone()
    
    # Get recent attendance
    recent_attendance = []
    if active_session:
        cur.execute("""
            SELECT u.name, a.status, a.marked_at 
            FROM attendance a 
            JOIN users u ON a.student_id = u.id 
            WHERE a.session_id=%s 
            ORDER BY a.marked_at DESC LIMIT 10
        """, (active_session["id"],))
        rows = cur.fetchall()
        recent_attendance = [dict(r) for r in rows]

    conn.close()
    return jsonify({
        "success": True,
        "active_session": dict(active_session) if active_session else None,
        "recent_attendance": recent_attendance
    })

# --- Faculty: Current Timetable Period ---
@app.route("/api/faculty/current-period", methods=["GET"])
@jwt_required()
def get_current_period():
    faculty_id = get_jwt_identity()
    now = datetime.now()
    day = now.strftime('%A')
    time = now.strftime('%H:%M')
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT t.*, s.name as subject_name 
        FROM timetable t
        JOIN subjects s ON t.subject_id = s.id
        WHERE t.faculty_id = %s AND t.day_of_week = %s 
        AND %s BETWEEN t.start_time AND t.end_time
    """, (faculty_id, day, time))
    period = cur.fetchone()
    conn.close()
    
    return jsonify({"success": True, "period": dict(period) if period else None})

@app.route("/api/faculty/timetable", methods=["GET"])
@jwt_required()
def get_faculty_timetable():
    faculty_id = get_jwt_identity()
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT t.*, s.name as subject_name 
        FROM timetable t
        JOIN subjects s ON t.subject_id = s.id
        WHERE t.faculty_id = %s
        ORDER BY CASE day_of_week 
            WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 
            WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 
            WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 
        END, start_time
    """, (faculty_id,))
    rows = cur.fetchall()
    conn.close()
    return jsonify({"success": True, "timetable": [dict(r) for r in rows]})


# --- Student: Dashboard Stats ---
@app.route("/api/student/stats", methods=["GET"])
@jwt_required()
def get_student_stats():
    student_id = get_jwt_identity()
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # Overall attendance %
    cur.execute("SELECT COUNT(*) as count FROM attendance WHERE student_id=%s", (student_id,))
    present = cur.fetchone()['count']
    
    # Ideally compare with total sessions for their branch/sem
    cur.execute("SELECT branch, semester FROM users WHERE id=%s", (student_id,))
    user = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) as count FROM sessions WHERE branch=%s AND semester=%s", (user["branch"], user["semester"]))
    total_sessions = cur.fetchone()['count']
    
    percent = (present / total_sessions * 100) if total_sessions > 0 else 0
    
    # Last 5 history
    cur.execute("""
        SELECT s.subject, a.status, a.marked_at 
        FROM attendance a
        JOIN sessions s ON a.session_id = s.id
        WHERE a.student_id = %s
        ORDER BY a.marked_at DESC LIMIT 5
    """, (student_id,))
    history = [dict(r) for r in cur.fetchall()]
    
    conn.close()
    return jsonify({
        "success": True,
        "attendance_percent": round(percent, 1),
        "present_count": present,
        "total_sessions": total_sessions,
        "recent_history": history
    })

# --- Student: Daily Timetable ---
@app.route("/api/student/timetable", methods=["GET"])
@jwt_required()
def get_student_timetable():
    student_id = get_jwt_identity()
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    cur.execute("SELECT branch, semester FROM users WHERE id=%s", (student_id,))
    user = cur.fetchone()
    
    day = datetime.now().strftime('%A')
    
    cur.execute("""
        SELECT t.*, s.name as subject_name, u.name as faculty_name
        FROM timetable t
        JOIN subjects s ON t.subject_id = s.id
        JOIN users u ON t.faculty_id = u.id
        WHERE UPPER(t.branch) = UPPER(%s) AND UPPER(t.semester) = UPPER(%s) AND t.day_of_week = %s
        ORDER BY t.start_time
    """, (user["branch"], user["semester"], day))
    
    timetable = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"success": True, "timetable": timetable})

@app.route("/api/student/timetable-full", methods=["GET"])
@jwt_required()
def get_student_timetable_full():
    student_id = get_jwt_identity()
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    cur.execute("SELECT branch, semester FROM users WHERE id=%s", (student_id,))
    user = cur.fetchone()
    
    cur.execute("""
        SELECT t.*, s.name as subject_name, u.name as faculty_name
        FROM timetable t
        JOIN subjects s ON t.subject_id = s.id
        JOIN users u ON t.faculty_id = u.id
        WHERE UPPER(t.branch) = UPPER(%s) AND UPPER(t.semester) = UPPER(%s)
        ORDER BY CASE day_of_week 
            WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 
            WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 
            WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 
        END, t.start_time
    """, (user["branch"], user["semester"]))
    
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"success": True, "timetable": rows})

@app.route("/api/student/attendance-full", methods=["GET"])
@jwt_required()
def get_student_attendance_full():
    student_id = get_jwt_identity()
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    cur.execute("SELECT branch, semester FROM users WHERE id=%s", (student_id,))
    user = cur.fetchone()
    
    # Get all subjects for this sem
    cur.execute("SELECT name FROM subjects WHERE branch=%s AND semester=%s", (user["branch"], user["semester"]))
    subjects = cur.fetchall()
    
    totals = []
    daily = []
    
    for r in subjects:
        # Total sessions for this subject
        cur.execute("SELECT COUNT(*) as count FROM sessions WHERE subject=%s AND branch=%s AND semester=%s", (r['name'], user["branch"], user["semester"]))
        total = cur.fetchone()['count']
        
        # Present count
        cur.execute("""
            SELECT COUNT(*) as count FROM attendance a 
            JOIN sessions s ON a.session_id = s.id 
            WHERE a.student_id=%s AND s.subject=%s
        """, (student_id, r['name']))
        present = cur.fetchone()['count']
        
        percent = (present / total * 100) if total > 0 else 0
        
        totals.append({
            "subject": r['name'],
            "present": present,
            "total_classes": total,
            "percentage": percent
        })

    conn.close()

    return jsonify({
        "success": True,
        "daily_attendance": daily,
        "total_attendance": totals
    })


# 🧑‍💼 Admin: List Users (with Pagination)
@app.route("/api/admin/users", methods=["GET"])
@jwt_required()
def list_users():
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized. Admin only."}), 403

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    offset = (page - 1) * per_page

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # Get total count
    cur.execute("SELECT COUNT(*) as count FROM users")
    total_users = cur.fetchone()['count']
    total_pages = math.ceil(total_users / per_page)

    cur.execute(
        "SELECT id, username, role, name, roll_no, branch, semester FROM users LIMIT %s OFFSET %s",
        (per_page, offset)
    )
    rows = cur.fetchall()
    conn.close()

    users = [dict(r) for r in rows]

    return jsonify({
        "success": True,
        "users": users,
        "pagination": {
            "total_users": total_users,
            "total_pages": total_pages,
            "current_page": page,
            "per_page": per_page
        }
    })


# 🧑‍💼 Admin: Create User
@app.route("/api/admin/users", methods=["POST"])
@jwt_required()
def create_user():
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized. Admin only."}), 403

    data = request.json
    username = data.get("username")
    password = data.get("password")
    role = data.get("role")
    name = data.get("name")
    roll_no = data.get("roll_no")
    branch = data.get("branch")
    semester = data.get("semester")

    if not username or not password or not role:
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    hashed_password = generate_password_hash(password)

    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            INSERT INTO users (username, password, role, name, roll_no, branch, semester)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (username, hashed_password, role, name, roll_no, branch, semester)
        )
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        return jsonify({"success": True, "message": "User created", "user_id": user_id}), 201
    except mysql.connector.Error as err:
        if err.errno == 1062:
            return jsonify({"success": False, "message": "Username already exists"}), 400
        return jsonify({"success": False, "message": str(err)}), 500


# 🧑‍💼 Admin: Update User
@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
@jwt_required()
def update_user(user_id):
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized. Admin only."}), 403

    data = request.json
    
    # Fields that can be updated
    allowed_fields = ["username", "password", "role", "name", "roll_no", "branch", "semester"]
    updates = []
    params = []

    for field in allowed_fields:
        if field in data:
            if field == "password":
                updates.append(f"{field} = %s")
                params.append(generate_password_hash(data[field]))
            else:
                updates.append(f"{field} = %s")
                params.append(data[field])

    if not updates:
        return jsonify({"success": False, "message": "No update data provided"}), 400

    params.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, tuple(params))
    conn.commit()
    
    if cur.rowcount == 0:
        conn.close()
        return jsonify({"success": False, "message": "User not found"}), 404

    conn.close()
    return jsonify({"success": True, "message": "User updated"})


# 🧑‍💼 Admin: Change Password (Self or Other User)
@app.route("/api/admin/change-password", methods=["PUT"])
@jwt_required()
def admin_change_password():
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized. Admin only."}), 403

    data = request.json
    target_user_id = data.get("user_id") # Optional: ID of the user whose password is to be changed
    new_password = data.get("new_password")
    
    if not new_password:
        return jsonify({"success": False, "message": "New password required"}), 400

    # If no user_id is provided, change the current admin's password
    if not target_user_id:
        target_user_id = get_jwt_identity()
        current_password = data.get("current_password")
        if not current_password:
            return jsonify({"success": False, "message": "Current password required"}), 400
            
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT password FROM users WHERE id = %s", (target_user_id,))
        user_record = cur.fetchone()
        
        if not user_record or not check_password_hash(user_record["password"], current_password):
            conn.close()
            return jsonify({"success": False, "message": "Incorrect current password"}), 401
    else:
        conn = get_db()
        
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET password = %s WHERE id = %s",
        (generate_password_hash(new_password), target_user_id)
    )
    conn.commit()
    
    if cur.rowcount == 0:
        conn.close()
        return jsonify({"success": False, "message": "User not found"}), 404

    conn.close()
    return jsonify({"success": True, "message": "Password changed successfully"})


# 🧑‍💼 Admin: Delete User
@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized. Admin only."}), 403

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    
    if cur.rowcount == 0:
        conn.close()
        return jsonify({"success": False, "message": "User not found"}), 404

    conn.close()
    return jsonify({"success": True, "message": "User deleted"})


# 🧑‍💼 Admin: Reset User Device Binding
@app.route("/api/admin/users/<int:user_id>/reset-device", methods=["POST"])
@jwt_required()
def reset_device(user_id):
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized. Admin only."}), 403

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("UPDATE users SET device_id = NULL WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Device binding reset. Student can now login from a new device."})


# 🧑‍💼 Admin: List Subjects
@app.route("/api/admin/subjects", methods=["GET"])
@jwt_required()
def list_subjects():
    claims = get_jwt()
    if claims.get("role") not in ["admin", "faculty"]:
        return jsonify({"success": False, "message": "Unauthorized."}), 403

    branch = request.args.get("branch")
    semester = request.args.get("semester")

    query = "SELECT * FROM subjects"
    params = []
    
    if branch and semester:
        query += " WHERE branch = %s AND semester = %s"
        params = (branch, semester)
    elif branch:
        query += " WHERE branch = %s"
        params = (branch,)

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return jsonify({"success": True, "subjects": [dict(r) for r in rows]})


# 📊 Admin: View All Attendance Sessions
@app.route("/api/admin/attendance", methods=["GET"])
@jwt_required()
def admin_list_attendance():
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized. Admin only."}), 403

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    # Get all sessions with faculty name and attendance count
    cur.execute("""
        SELECT s.id, s.branch, s.semester, s.subject, s.start_time, s.expires_at,
               u.name as faculty_name,
               COUNT(a.id) as present_count
        FROM sessions s
        LEFT JOIN users u ON s.faculty_id = u.id
        LEFT JOIN attendance a ON a.session_id = s.id
        GROUP BY s.id
        ORDER BY s.start_time DESC
        LIMIT 100
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify({"success": True, "sessions": [dict(r) for r in rows]})


# 📊 Admin: View All Student Attendance Data
@app.route("/api/admin/all_student_attendance", methods=["GET"])
@jwt_required()
def admin_all_student_attendance():
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized. Admin only."}), 403

    branch = request.args.get("branch")
    semester = request.args.get("semester")

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # We want to return all students along with their present count and total session count for their branch/sem
    query = """
    SELECT u.id, u.name, u.roll_no, u.branch, u.semester,
           (SELECT COUNT(*) FROM attendance a WHERE a.student_id = u.id) as present_count,
           (SELECT COUNT(*) FROM sessions s WHERE s.branch = u.branch AND s.semester = u.semester) as total_sessions
    FROM users u
    WHERE u.role = 'student'
    """
    params = []

    if branch:
        query += " AND u.branch = %s"
        params.append(branch)
        
    if semester:
        query += " AND u.semester = %s"
        params.append(semester)

    query += " ORDER BY u.branch, u.semester, u.roll_no"
    
    cur.execute(query, tuple(params))
    students = cur.fetchall()
    conn.close()

    results = []
    for s in students:
        total = s['total_sessions']
        present = s['present_count']
        percentage = round((present / total * 100), 1) if total > 0 else 0
        s_dict = dict(s)
        s_dict['percentage'] = percentage
        results.append(s_dict)

    return jsonify({"success": True, "students": results})


# 📥 Admin: Export Attendance Report as CSV
@app.route("/api/admin/reports/export", methods=["POST"])
@jwt_required()
def export_report():
    import io
    import csv as csv_module
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized. Admin only."}), 403

    data = request.json or {}
    period = data.get("period", "weekly")  # weekly or monthly
    branch = data.get("branch", "")
    semester = data.get("semester", "")

    # Calculate date range
    now = datetime.now()
    if period == "weekly":
        cutoff = now - timedelta(days=7)
    else:
        cutoff = now - timedelta(days=30)

    conn = get_db()
    cur = conn.cursor()

    query = """
        SELECT 
            u_student.name as student_name,
            u_student.roll_no,
            u_student.branch,
            u_student.semester,
            s.subject,
            s.start_time as class_date,
            a.status,
            u_faculty.name as faculty_name
        FROM attendance a
        JOIN users u_student ON a.student_id = u_student.id
        JOIN sessions s ON a.session_id = s.id
        LEFT JOIN users u_faculty ON s.faculty_id = u_faculty.id
        WHERE s.start_time >= %s
    """
    params = [cutoff.isoformat()]

    if branch:
        query += " AND s.branch = %s"
        params.append(branch)
    if semester:
        query += " AND s.semester = %s"
        params.append(semester)

    query += " ORDER BY s.start_time DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    # Generate CSV
    output = io.StringIO()
    writer = csv_module.writer(output)
    writer.writerow(["Student Name", "Roll No", "Branch", "Semester", "Subject", "Class Date", "Status", "Faculty"])
    for row in rows:
        writer.writerow([
            row["student_name"], row["roll_no"], row["branch"],
            row["semester"], row["subject"],
            row["class_date"][:16] if row["class_date"] else "",
            row["status"], row["faculty_name"]
        ])

    csv_content = output.getvalue()
    output.close()

    from flask import Response
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_{period}_report.csv"}
    )


# � Error Handlers (Return JSON instead of HTML)
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "message": "API endpoint not found"}), 404
    return send_from_directory('.', 'login.html')

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"🔥 Server Error: {e}")
    return jsonify({"success": False, "message": "Internal server error", "error": str(e)}), 500

# 🌐 Serve Static & HTML Files
@app.route("/")
def home():
    return send_from_directory(BASE_DIR, 'login.html')

@app.route("/<path:path>")
def serve_files(path):
    if path.startswith("api/"):
        return jsonify({"success": False, "message": "API path error"}), 404
        
    if path in [".env", "qr_attendance.db", "app.py", "students.csv", "faculty.csv"]:
        return "Access denied", 403

    try:
        full_path = os.path.join(BASE_DIR, path)
        if os.path.exists(full_path):
            return send_from_directory(BASE_DIR, path)
        if os.path.exists(full_path + ".html"):
            return send_from_directory(BASE_DIR, path + ".html")
        # For PWA support: return icons or manifest
        if "icon" in path or "manifest" in path:
             return send_from_directory(BASE_DIR, path)
        return send_from_directory(BASE_DIR, 'login.html')
    except Exception:
        return send_from_directory(BASE_DIR, 'login.html')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
=======
from __future__ import annotations

import collections.abc as cabc
import os
import sys
import typing as t
import weakref
from datetime import timedelta
from inspect import iscoroutinefunction
from itertools import chain
from types import TracebackType
from urllib.parse import quote as _url_quote

import click
from werkzeug.datastructures import Headers
from werkzeug.datastructures import ImmutableDict
from werkzeug.exceptions import BadRequestKeyError
from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import InternalServerError
from werkzeug.routing import BuildError
from werkzeug.routing import MapAdapter
from werkzeug.routing import RequestRedirect
from werkzeug.routing import RoutingException
from werkzeug.routing import Rule
from werkzeug.serving import is_running_from_reloader
from werkzeug.wrappers import Response as BaseResponse
from werkzeug.wsgi import get_host

from . import cli
from . import typing as ft
from .ctx import AppContext
from .ctx import RequestContext
from .globals import _cv_app
from .globals import _cv_request
from .globals import current_app
from .globals import g
from .globals import request
from .globals import request_ctx
from .globals import session
from .helpers import get_debug_flag
from .helpers import get_flashed_messages
from .helpers import get_load_dotenv
from .helpers import send_from_directory
from .sansio.app import App
from .sansio.scaffold import _sentinel
from .sessions import SecureCookieSessionInterface
from .sessions import SessionInterface
from .signals import appcontext_tearing_down
from .signals import got_request_exception
from .signals import request_finished
from .signals import request_started
from .signals import request_tearing_down
from .templating import Environment
from .wrappers import Request
from .wrappers import Response

if t.TYPE_CHECKING:  # pragma: no cover
    from _typeshed.wsgi import StartResponse
    from _typeshed.wsgi import WSGIEnvironment

    from .testing import FlaskClient
    from .testing import FlaskCliRunner
    from .typing import HeadersValue

T_shell_context_processor = t.TypeVar(
    "T_shell_context_processor", bound=ft.ShellContextProcessorCallable
)
T_teardown = t.TypeVar("T_teardown", bound=ft.TeardownCallable)
T_template_filter = t.TypeVar("T_template_filter", bound=ft.TemplateFilterCallable)
T_template_global = t.TypeVar("T_template_global", bound=ft.TemplateGlobalCallable)
T_template_test = t.TypeVar("T_template_test", bound=ft.TemplateTestCallable)


def _make_timedelta(value: timedelta | int | None) -> timedelta | None:
    if value is None or isinstance(value, timedelta):
        return value

    return timedelta(seconds=value)


class Flask(App):
    """The flask object implements a WSGI application and acts as the central
    object.  It is passed the name of the module or package of the
    application.  Once it is created it will act as a central registry for
    the view functions, the URL rules, template configuration and much more.

    The name of the package is used to resolve resources from inside the
    package or the folder the module is contained in depending on if the
    package parameter resolves to an actual python package (a folder with
    an :file:`__init__.py` file inside) or a standard module (just a ``.py`` file).

    For more information about resource loading, see :func:`open_resource`.

    Usually you create a :class:`Flask` instance in your main module or
    in the :file:`__init__.py` file of your package like this::

        from flask import Flask
        app = Flask(__name__)

    .. admonition:: About the First Parameter

        The idea of the first parameter is to give Flask an idea of what
        belongs to your application.  This name is used to find resources
        on the filesystem, can be used by extensions to improve debugging
        information and a lot more.

        So it's important what you provide there.  If you are using a single
        module, `__name__` is always the correct value.  If you however are
        using a package, it's usually recommended to hardcode the name of
        your package there.

        For example if your application is defined in :file:`yourapplication/app.py`
        you should create it with one of the two versions below::

            app = Flask('yourapplication')
            app = Flask(__name__.split('.')[0])

        Why is that?  The application will work even with `__name__`, thanks
        to how resources are looked up.  However it will make debugging more
        painful.  Certain extensions can make assumptions based on the
        import name of your application.  For example the Flask-SQLAlchemy
        extension will look for the code in your application that triggered
        an SQL query in debug mode.  If the import name is not properly set
        up, that debugging information is lost.  (For example it would only
        pick up SQL queries in `yourapplication.app` and not
        `yourapplication.views.frontend`)

    .. versionadded:: 0.7
       The `static_url_path`, `static_folder`, and `template_folder`
       parameters were added.

    .. versionadded:: 0.8
       The `instance_path` and `instance_relative_config` parameters were
       added.

    .. versionadded:: 0.11
       The `root_path` parameter was added.

    .. versionadded:: 1.0
       The ``host_matching`` and ``static_host`` parameters were added.

    .. versionadded:: 1.0
       The ``subdomain_matching`` parameter was added. Subdomain
       matching needs to be enabled manually now. Setting
       :data:`SERVER_NAME` does not implicitly enable it.

    :param import_name: the name of the application package
    :param static_url_path: can be used to specify a different path for the
                            static files on the web.  Defaults to the name
                            of the `static_folder` folder.
    :param static_folder: The folder with static files that is served at
        ``static_url_path``. Relative to the application ``root_path``
        or an absolute path. Defaults to ``'static'``.
    :param static_host: the host to use when adding the static route.
        Defaults to None. Required when using ``host_matching=True``
        with a ``static_folder`` configured.
    :param host_matching: set ``url_map.host_matching`` attribute.
        Defaults to False.
    :param subdomain_matching: consider the subdomain relative to
        :data:`SERVER_NAME` when matching routes. Defaults to False.
    :param template_folder: the folder that contains the templates that should
                            be used by the application.  Defaults to
                            ``'templates'`` folder in the root path of the
                            application.
    :param instance_path: An alternative instance path for the application.
                          By default the folder ``'instance'`` next to the
                          package or module is assumed to be the instance
                          path.
    :param instance_relative_config: if set to ``True`` relative filenames
                                     for loading the config are assumed to
                                     be relative to the instance path instead
                                     of the application root.
    :param root_path: The path to the root of the application files.
        This should only be set manually when it can't be detected
        automatically, such as for namespace packages.
    """

    default_config = ImmutableDict(
        {
            "DEBUG": None,
            "TESTING": False,
            "PROPAGATE_EXCEPTIONS": None,
            "SECRET_KEY": None,
            "SECRET_KEY_FALLBACKS": None,
            "PERMANENT_SESSION_LIFETIME": timedelta(days=31),
            "USE_X_SENDFILE": False,
            "TRUSTED_HOSTS": None,
            "SERVER_NAME": None,
            "APPLICATION_ROOT": "/",
            "SESSION_COOKIE_NAME": "session",
            "SESSION_COOKIE_DOMAIN": None,
            "SESSION_COOKIE_PATH": None,
            "SESSION_COOKIE_HTTPONLY": True,
            "SESSION_COOKIE_SECURE": False,
            "SESSION_COOKIE_PARTITIONED": False,
            "SESSION_COOKIE_SAMESITE": None,
            "SESSION_REFRESH_EACH_REQUEST": True,
            "MAX_CONTENT_LENGTH": None,
            "MAX_FORM_MEMORY_SIZE": 500_000,
            "MAX_FORM_PARTS": 1_000,
            "SEND_FILE_MAX_AGE_DEFAULT": None,
            "TRAP_BAD_REQUEST_ERRORS": None,
            "TRAP_HTTP_EXCEPTIONS": False,
            "EXPLAIN_TEMPLATE_LOADING": False,
            "PREFERRED_URL_SCHEME": "http",
            "TEMPLATES_AUTO_RELOAD": None,
            "MAX_COOKIE_SIZE": 4093,
            "PROVIDE_AUTOMATIC_OPTIONS": True,
        }
    )

    #: The class that is used for request objects.  See :class:`~flask.Request`
    #: for more information.
    request_class: type[Request] = Request

    #: The class that is used for response objects.  See
    #: :class:`~flask.Response` for more information.
    response_class: type[Response] = Response

    #: the session interface to use.  By default an instance of
    #: :class:`~flask.sessions.SecureCookieSessionInterface` is used here.
    #:
    #: .. versionadded:: 0.8
    session_interface: SessionInterface = SecureCookieSessionInterface()

    def __init__(
        self,
        import_name: str,
        static_url_path: str | None = None,
        static_folder: str | os.PathLike[str] | None = "static",
        static_host: str | None = None,
        host_matching: bool = False,
        subdomain_matching: bool = False,
        template_folder: str | os.PathLike[str] | None = "templates",
        instance_path: str | None = None,
        instance_relative_config: bool = False,
        root_path: str | None = None,
    ):
        super().__init__(
            import_name=import_name,
            static_url_path=static_url_path,
            static_folder=static_folder,
            static_host=static_host,
            host_matching=host_matching,
            subdomain_matching=subdomain_matching,
            template_folder=template_folder,
            instance_path=instance_path,
            instance_relative_config=instance_relative_config,
            root_path=root_path,
        )

        #: The Click command group for registering CLI commands for this
        #: object. The commands are available from the ``flask`` command
        #: once the application has been discovered and blueprints have
        #: been registered.
        self.cli = cli.AppGroup()

        # Set the name of the Click group in case someone wants to add
        # the app's commands to another CLI tool.
        self.cli.name = self.name

        # Add a static route using the provided static_url_path, static_host,
        # and static_folder if there is a configured static_folder.
        # Note we do this without checking if static_folder exists.
        # For one, it might be created while the server is running (e.g. during
        # development). Also, Google App Engine stores static files somewhere
        if self.has_static_folder:
            assert bool(static_host) == host_matching, (
                "Invalid static_host/host_matching combination"
            )
            # Use a weakref to avoid creating a reference cycle between the app
            # and the view function (see #3761).
            self_ref = weakref.ref(self)
            self.add_url_rule(
                f"{self.static_url_path}/<path:filename>",
                endpoint="static",
                host=static_host,
                view_func=lambda **kw: self_ref().send_static_file(**kw),  # type: ignore # noqa: B950
            )

    def get_send_file_max_age(self, filename: str | None) -> int | None:
        """Used by :func:`send_file` to determine the ``max_age`` cache
        value for a given file path if it wasn't passed.

        By default, this returns :data:`SEND_FILE_MAX_AGE_DEFAULT` from
        the configuration of :data:`~flask.current_app`. This defaults
        to ``None``, which tells the browser to use conditional requests
        instead of a timed cache, which is usually preferable.

        Note this is a duplicate of the same method in the Flask
        class.

        .. versionchanged:: 2.0
            The default configuration is ``None`` instead of 12 hours.

        .. versionadded:: 0.9
        """
        value = current_app.config["SEND_FILE_MAX_AGE_DEFAULT"]

        if value is None:
            return None

        if isinstance(value, timedelta):
            return int(value.total_seconds())

        return value  # type: ignore[no-any-return]

    def send_static_file(self, filename: str) -> Response:
        """The view function used to serve files from
        :attr:`static_folder`. A route is automatically registered for
        this view at :attr:`static_url_path` if :attr:`static_folder` is
        set.

        Note this is a duplicate of the same method in the Flask
        class.

        .. versionadded:: 0.5

        """
        if not self.has_static_folder:
            raise RuntimeError("'static_folder' must be set to serve static_files.")

        # send_file only knows to call get_send_file_max_age on the app,
        # call it here so it works for blueprints too.
        max_age = self.get_send_file_max_age(filename)
        return send_from_directory(
            t.cast(str, self.static_folder), filename, max_age=max_age
        )

    def open_resource(
        self, resource: str, mode: str = "rb", encoding: str | None = None
    ) -> t.IO[t.AnyStr]:
        """Open a resource file relative to :attr:`root_path` for reading.

        For example, if the file ``schema.sql`` is next to the file
        ``app.py`` where the ``Flask`` app is defined, it can be opened
        with:

        .. code-block:: python

            with app.open_resource("schema.sql") as f:
                conn.executescript(f.read())

        :param resource: Path to the resource relative to :attr:`root_path`.
        :param mode: Open the file in this mode. Only reading is supported,
            valid values are ``"r"`` (or ``"rt"``) and ``"rb"``.
        :param encoding: Open the file with this encoding when opening in text
            mode. This is ignored when opening in binary mode.

        .. versionchanged:: 3.1
            Added the ``encoding`` parameter.
        """
        if mode not in {"r", "rt", "rb"}:
            raise ValueError("Resources can only be opened for reading.")

        path = os.path.join(self.root_path, resource)

        if mode == "rb":
            return open(path, mode)  # pyright: ignore

        return open(path, mode, encoding=encoding)

    def open_instance_resource(
        self, resource: str, mode: str = "rb", encoding: str | None = "utf-8"
    ) -> t.IO[t.AnyStr]:
        """Open a resource file relative to the application's instance folder
        :attr:`instance_path`. Unlike :meth:`open_resource`, files in the
        instance folder can be opened for writing.

        :param resource: Path to the resource relative to :attr:`instance_path`.
        :param mode: Open the file in this mode.
        :param encoding: Open the file with this encoding when opening in text
            mode. This is ignored when opening in binary mode.

        .. versionchanged:: 3.1
            Added the ``encoding`` parameter.
        """
        path = os.path.join(self.instance_path, resource)

        if "b" in mode:
            return open(path, mode)

        return open(path, mode, encoding=encoding)

    def create_jinja_environment(self) -> Environment:
        """Create the Jinja environment based on :attr:`jinja_options`
        and the various Jinja-related methods of the app. Changing
        :attr:`jinja_options` after this will have no effect. Also adds
        Flask-related globals and filters to the environment.

        .. versionchanged:: 0.11
           ``Environment.auto_reload`` set in accordance with
           ``TEMPLATES_AUTO_RELOAD`` configuration option.

        .. versionadded:: 0.5
        """
        options = dict(self.jinja_options)

        if "autoescape" not in options:
            options["autoescape"] = self.select_jinja_autoescape

        if "auto_reload" not in options:
            auto_reload = self.config["TEMPLATES_AUTO_RELOAD"]

            if auto_reload is None:
                auto_reload = self.debug

            options["auto_reload"] = auto_reload

        rv = self.jinja_environment(self, **options)
        rv.globals.update(
            url_for=self.url_for,
            get_flashed_messages=get_flashed_messages,
            config=self.config,
            # request, session and g are normally added with the
            # context processor for efficiency reasons but for imported
            # templates we also want the proxies in there.
            request=request,
            session=session,
            g=g,
        )
        rv.policies["json.dumps_function"] = self.json.dumps
        return rv

    def create_url_adapter(self, request: Request | None) -> MapAdapter | None:
        """Creates a URL adapter for the given request. The URL adapter
        is created at a point where the request context is not yet set
        up so the request is passed explicitly.

        .. versionchanged:: 3.1
            If :data:`SERVER_NAME` is set, it does not restrict requests to
            only that domain, for both ``subdomain_matching`` and
            ``host_matching``.

        .. versionchanged:: 1.0
            :data:`SERVER_NAME` no longer implicitly enables subdomain
            matching. Use :attr:`subdomain_matching` instead.

        .. versionchanged:: 0.9
           This can be called outside a request when the URL adapter is created
           for an application context.

        .. versionadded:: 0.6
        """
        if request is not None:
            if (trusted_hosts := self.config["TRUSTED_HOSTS"]) is not None:
                request.trusted_hosts = trusted_hosts

            # Check trusted_hosts here until bind_to_environ does.
            request.host = get_host(request.environ, request.trusted_hosts)  # pyright: ignore
            subdomain = None
            server_name = self.config["SERVER_NAME"]

            if self.url_map.host_matching:
                # Don't pass SERVER_NAME, otherwise it's used and the actual
                # host is ignored, which breaks host matching.
                server_name = None
            elif not self.subdomain_matching:
                # Werkzeug doesn't implement subdomain matching yet. Until then,
                # disable it by forcing the current subdomain to the default, or
                # the empty string.
                subdomain = self.url_map.default_subdomain or ""

            return self.url_map.bind_to_environ(
                request.environ, server_name=server_name, subdomain=subdomain
            )

        # Need at least SERVER_NAME to match/build outside a request.
        if self.config["SERVER_NAME"] is not None:
            return self.url_map.bind(
                self.config["SERVER_NAME"],
                script_name=self.config["APPLICATION_ROOT"],
                url_scheme=self.config["PREFERRED_URL_SCHEME"],
            )

        return None

    def raise_routing_exception(self, request: Request) -> t.NoReturn:
        """Intercept routing exceptions and possibly do something else.

        In debug mode, intercept a routing redirect and replace it with
        an error if the body will be discarded.

        With modern Werkzeug this shouldn't occur, since it now uses a
        308 status which tells the browser to resend the method and
        body.

        .. versionchanged:: 2.1
            Don't intercept 307 and 308 redirects.

        :meta private:
        :internal:
        """
        if (
            not self.debug
            or not isinstance(request.routing_exception, RequestRedirect)
            or request.routing_exception.code in {307, 308}
            or request.method in {"GET", "HEAD", "OPTIONS"}
        ):
            raise request.routing_exception  # type: ignore[misc]

        from .debughelpers import FormDataRoutingRedirect

        raise FormDataRoutingRedirect(request)

    def update_template_context(self, context: dict[str, t.Any]) -> None:
        """Update the template context with some commonly used variables.
        This injects request, session, config and g into the template
        context as well as everything template context processors want
        to inject.  Note that the as of Flask 0.6, the original values
        in the context will not be overridden if a context processor
        decides to return a value with the same key.

        :param context: the context as a dictionary that is updated in place
                        to add extra variables.
        """
        names: t.Iterable[str | None] = (None,)

        # A template may be rendered outside a request context.
        if request:
            names = chain(names, reversed(request.blueprints))

        # The values passed to render_template take precedence. Keep a
        # copy to re-apply after all context functions.
        orig_ctx = context.copy()

        for name in names:
            if name in self.template_context_processors:
                for func in self.template_context_processors[name]:
                    context.update(self.ensure_sync(func)())

        context.update(orig_ctx)

    def make_shell_context(self) -> dict[str, t.Any]:
        """Returns the shell context for an interactive shell for this
        application.  This runs all the registered shell context
        processors.

        .. versionadded:: 0.11
        """
        rv = {"app": self, "g": g}
        for processor in self.shell_context_processors:
            rv.update(processor())
        return rv

    def run(
        self,
        host: str | None = None,
        port: int | None = None,
        debug: bool | None = None,
        load_dotenv: bool = True,
        **options: t.Any,
    ) -> None:
        """Runs the application on a local development server.

        Do not use ``run()`` in a production setting. It is not intended to
        meet security and performance requirements for a production server.
        Instead, see :doc:`/deploying/index` for WSGI server recommendations.

        If the :attr:`debug` flag is set the server will automatically reload
        for code changes and show a debugger in case an exception happened.

        If you want to run the application in debug mode, but disable the
        code execution on the interactive debugger, you can pass
        ``use_evalex=False`` as parameter.  This will keep the debugger's
        traceback screen active, but disable code execution.

        It is not recommended to use this function for development with
        automatic reloading as this is badly supported.  Instead you should
        be using the :command:`flask` command line script's ``run`` support.

        .. admonition:: Keep in Mind

           Flask will suppress any server error with a generic error page
           unless it is in debug mode.  As such to enable just the
           interactive debugger without the code reloading, you have to
           invoke :meth:`run` with ``debug=True`` and ``use_reloader=False``.
           Setting ``use_debugger`` to ``True`` without being in debug mode
           won't catch any exceptions because there won't be any to
           catch.

        :param host: the hostname to listen on. Set this to ``'0.0.0.0'`` to
            have the server available externally as well. Defaults to
            ``'127.0.0.1'`` or the host in the ``SERVER_NAME`` config variable
            if present.
        :param port: the port of the webserver. Defaults to ``5000`` or the
            port defined in the ``SERVER_NAME`` config variable if present.
        :param debug: if given, enable or disable debug mode. See
            :attr:`debug`.
        :param load_dotenv: Load the nearest :file:`.env` and :file:`.flaskenv`
            files to set environment variables. Will also change the working
            directory to the directory containing the first file found.
        :param options: the options to be forwarded to the underlying Werkzeug
            server. See :func:`werkzeug.serving.run_simple` for more
            information.

        .. versionchanged:: 1.0
            If installed, python-dotenv will be used to load environment
            variables from :file:`.env` and :file:`.flaskenv` files.

            The :envvar:`FLASK_DEBUG` environment variable will override :attr:`debug`.

            Threaded mode is enabled by default.

        .. versionchanged:: 0.10
            The default port is now picked from the ``SERVER_NAME``
            variable.
        """
        # Ignore this call so that it doesn't start another server if
        # the 'flask run' command is used.
        if os.environ.get("FLASK_RUN_FROM_CLI") == "true":
            if not is_running_from_reloader():
                click.secho(
                    " * Ignoring a call to 'app.run()' that would block"
                    " the current 'flask' CLI command.\n"
                    "   Only call 'app.run()' in an 'if __name__ =="
                    ' "__main__"\' guard.',
                    fg="red",
                )

            return

        if get_load_dotenv(load_dotenv):
            cli.load_dotenv()

            # if set, env var overrides existing value
            if "FLASK_DEBUG" in os.environ:
                self.debug = get_debug_flag()

        # debug passed to method overrides all other sources
        if debug is not None:
            self.debug = bool(debug)

        server_name = self.config.get("SERVER_NAME")
        sn_host = sn_port = None

        if server_name:
            sn_host, _, sn_port = server_name.partition(":")

        if not host:
            if sn_host:
                host = sn_host
            else:
                host = "127.0.0.1"

        if port or port == 0:
            port = int(port)
        elif sn_port:
            port = int(sn_port)
        else:
            port = 5000

        options.setdefault("use_reloader", self.debug)
        options.setdefault("use_debugger", self.debug)
        options.setdefault("threaded", True)

        cli.show_server_banner(self.debug, self.name)

        from werkzeug.serving import run_simple

        try:
            run_simple(t.cast(str, host), port, self, **options)
        finally:
            # reset the first request information if the development server
            # reset normally.  This makes it possible to restart the server
            # without reloader and that stuff from an interactive shell.
            self._got_first_request = False

    def test_client(self, use_cookies: bool = True, **kwargs: t.Any) -> FlaskClient:
        """Creates a test client for this application.  For information
        about unit testing head over to :doc:`/testing`.

        Note that if you are testing for assertions or exceptions in your
        application code, you must set ``app.testing = True`` in order for the
        exceptions to propagate to the test client.  Otherwise, the exception
        will be handled by the application (not visible to the test client) and
        the only indication of an AssertionError or other exception will be a
        500 status code response to the test client.  See the :attr:`testing`
        attribute.  For example::

            app.testing = True
            client = app.test_client()

        The test client can be used in a ``with`` block to defer the closing down
        of the context until the end of the ``with`` block.  This is useful if
        you want to access the context locals for testing::

            with app.test_client() as c:
                rv = c.get('/?vodka=42')
                assert request.args['vodka'] == '42'

        Additionally, you may pass optional keyword arguments that will then
        be passed to the application's :attr:`test_client_class` constructor.
        For example::

            from flask.testing import FlaskClient

            class CustomClient(FlaskClient):
                def __init__(self, *args, **kwargs):
                    self._authentication = kwargs.pop("authentication")
                    super(CustomClient,self).__init__( *args, **kwargs)

            app.test_client_class = CustomClient
            client = app.test_client(authentication='Basic ....')

        See :class:`~flask.testing.FlaskClient` for more information.

        .. versionchanged:: 0.4
           added support for ``with`` block usage for the client.

        .. versionadded:: 0.7
           The `use_cookies` parameter was added as well as the ability
           to override the client to be used by setting the
           :attr:`test_client_class` attribute.

        .. versionchanged:: 0.11
           Added `**kwargs` to support passing additional keyword arguments to
           the constructor of :attr:`test_client_class`.
        """
        cls = self.test_client_class
        if cls is None:
            from .testing import FlaskClient as cls
        return cls(  # type: ignore
            self, self.response_class, use_cookies=use_cookies, **kwargs
        )

    def test_cli_runner(self, **kwargs: t.Any) -> FlaskCliRunner:
        """Create a CLI runner for testing CLI commands.
        See :ref:`testing-cli`.

        Returns an instance of :attr:`test_cli_runner_class`, by default
        :class:`~flask.testing.FlaskCliRunner`. The Flask app object is
        passed as the first argument.

        .. versionadded:: 1.0
        """
        cls = self.test_cli_runner_class

        if cls is None:
            from .testing import FlaskCliRunner as cls

        return cls(self, **kwargs)  # type: ignore

    def handle_http_exception(
        self, e: HTTPException
    ) -> HTTPException | ft.ResponseReturnValue:
        """Handles an HTTP exception.  By default this will invoke the
        registered error handlers and fall back to returning the
        exception as response.

        .. versionchanged:: 1.0.3
            ``RoutingException``, used internally for actions such as
             slash redirects during routing, is not passed to error
             handlers.

        .. versionchanged:: 1.0
            Exceptions are looked up by code *and* by MRO, so
            ``HTTPException`` subclasses can be handled with a catch-all
            handler for the base ``HTTPException``.

        .. versionadded:: 0.3
        """
        # Proxy exceptions don't have error codes.  We want to always return
        # those unchanged as errors
        if e.code is None:
            return e

        # RoutingExceptions are used internally to trigger routing
        # actions, such as slash redirects raising RequestRedirect. They
        # are not raised or handled in user code.
        if isinstance(e, RoutingException):
            return e

        handler = self._find_error_handler(e, request.blueprints)
        if handler is None:
            return e
        return self.ensure_sync(handler)(e)  # type: ignore[no-any-return]

    def handle_user_exception(
        self, e: Exception
    ) -> HTTPException | ft.ResponseReturnValue:
        """This method is called whenever an exception occurs that
        should be handled. A special case is :class:`~werkzeug
        .exceptions.HTTPException` which is forwarded to the
        :meth:`handle_http_exception` method. This function will either
        return a response value or reraise the exception with the same
        traceback.

        .. versionchanged:: 1.0
            Key errors raised from request data like ``form`` show the
            bad key in debug mode rather than a generic bad request
            message.

        .. versionadded:: 0.7
        """
        if isinstance(e, BadRequestKeyError) and (
            self.debug or self.config["TRAP_BAD_REQUEST_ERRORS"]
        ):
            e.show_exception = True

        if isinstance(e, HTTPException) and not self.trap_http_exception(e):
            return self.handle_http_exception(e)

        handler = self._find_error_handler(e, request.blueprints)

        if handler is None:
            raise

        return self.ensure_sync(handler)(e)  # type: ignore[no-any-return]

    def handle_exception(self, e: Exception) -> Response:
        """Handle an exception that did not have an error handler
        associated with it, or that was raised from an error handler.
        This always causes a 500 ``InternalServerError``.

        Always sends the :data:`got_request_exception` signal.

        If :data:`PROPAGATE_EXCEPTIONS` is ``True``, such as in debug
        mode, the error will be re-raised so that the debugger can
        display it. Otherwise, the original exception is logged, and
        an :exc:`~werkzeug.exceptions.InternalServerError` is returned.

        If an error handler is registered for ``InternalServerError`` or
        ``500``, it will be used. For consistency, the handler will
        always receive the ``InternalServerError``. The original
        unhandled exception is available as ``e.original_exception``.

        .. versionchanged:: 1.1.0
            Always passes the ``InternalServerError`` instance to the
            handler, setting ``original_exception`` to the unhandled
            error.

        .. versionchanged:: 1.1.0
            ``after_request`` functions and other finalization is done
            even for the default 500 response when there is no handler.

        .. versionadded:: 0.3
        """
        exc_info = sys.exc_info()
        got_request_exception.send(self, _async_wrapper=self.ensure_sync, exception=e)
        propagate = self.config["PROPAGATE_EXCEPTIONS"]

        if propagate is None:
            propagate = self.testing or self.debug

        if propagate:
            # Re-raise if called with an active exception, otherwise
            # raise the passed in exception.
            if exc_info[1] is e:
                raise

            raise e

        self.log_exception(exc_info)
        server_error: InternalServerError | ft.ResponseReturnValue
        server_error = InternalServerError(original_exception=e)
        handler = self._find_error_handler(server_error, request.blueprints)

        if handler is not None:
            server_error = self.ensure_sync(handler)(server_error)

        return self.finalize_request(server_error, from_error_handler=True)

    def log_exception(
        self,
        exc_info: (tuple[type, BaseException, TracebackType] | tuple[None, None, None]),
    ) -> None:
        """Logs an exception.  This is called by :meth:`handle_exception`
        if debugging is disabled and right before the handler is called.
        The default implementation logs the exception as error on the
        :attr:`logger`.

        .. versionadded:: 0.8
        """
        self.logger.error(
            f"Exception on {request.path} [{request.method}]", exc_info=exc_info
        )

    def dispatch_request(self) -> ft.ResponseReturnValue:
        """Does the request dispatching.  Matches the URL and returns the
        return value of the view or error handler.  This does not have to
        be a response object.  In order to convert the return value to a
        proper response object, call :func:`make_response`.

        .. versionchanged:: 0.7
           This no longer does the exception handling, this code was
           moved to the new :meth:`full_dispatch_request`.
        """
        req = request_ctx.request
        if req.routing_exception is not None:
            self.raise_routing_exception(req)
        rule: Rule = req.url_rule  # type: ignore[assignment]
        # if we provide automatic options for this URL and the
        # request came with the OPTIONS method, reply automatically
        if (
            getattr(rule, "provide_automatic_options", False)
            and req.method == "OPTIONS"
        ):
            return self.make_default_options_response()
        # otherwise dispatch to the handler for that endpoint
        view_args: dict[str, t.Any] = req.view_args  # type: ignore[assignment]
        return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]

    def full_dispatch_request(self) -> Response:
        """Dispatches the request and on top of that performs request
        pre and postprocessing as well as HTTP exception catching and
        error handling.

        .. versionadded:: 0.7
        """
        self._got_first_request = True

        try:
            request_started.send(self, _async_wrapper=self.ensure_sync)
            rv = self.preprocess_request()
            if rv is None:
                rv = self.dispatch_request()
        except Exception as e:
            rv = self.handle_user_exception(e)
        return self.finalize_request(rv)

    def finalize_request(
        self,
        rv: ft.ResponseReturnValue | HTTPException,
        from_error_handler: bool = False,
    ) -> Response:
        """Given the return value from a view function this finalizes
        the request by converting it into a response and invoking the
        postprocessing functions.  This is invoked for both normal
        request dispatching as well as error handlers.

        Because this means that it might be called as a result of a
        failure a special safe mode is available which can be enabled
        with the `from_error_handler` flag.  If enabled, failures in
        response processing will be logged and otherwise ignored.

        :internal:
        """
        response = self.make_response(rv)
        try:
            response = self.process_response(response)
            request_finished.send(
                self, _async_wrapper=self.ensure_sync, response=response
            )
        except Exception:
            if not from_error_handler:
                raise
            self.logger.exception(
                "Request finalizing failed with an error while handling an error"
            )
        return response

    def make_default_options_response(self) -> Response:
        """This method is called to create the default ``OPTIONS`` response.
        This can be changed through subclassing to change the default
        behavior of ``OPTIONS`` responses.

        .. versionadded:: 0.7
        """
        adapter = request_ctx.url_adapter
        methods = adapter.allowed_methods()  # type: ignore[union-attr]
        rv = self.response_class()
        rv.allow.update(methods)
        return rv

    def ensure_sync(self, func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        """Ensure that the function is synchronous for WSGI workers.
        Plain ``def`` functions are returned as-is. ``async def``
        functions are wrapped to run and wait for the response.

        Override this method to change how the app runs async views.

        .. versionadded:: 2.0
        """
        if iscoroutinefunction(func):
            return self.async_to_sync(func)

        return func

    def async_to_sync(
        self, func: t.Callable[..., t.Coroutine[t.Any, t.Any, t.Any]]
    ) -> t.Callable[..., t.Any]:
        """Return a sync function that will run the coroutine function.

        .. code-block:: python

            result = app.async_to_sync(func)(*args, **kwargs)

        Override this method to change how the app converts async code
        to be synchronously callable.

        .. versionadded:: 2.0
        """
        try:
            from asgiref.sync import async_to_sync as asgiref_async_to_sync
        except ImportError:
            raise RuntimeError(
                "Install Flask with the 'async' extra in order to use async views."
            ) from None

        return asgiref_async_to_sync(func)

    def url_for(
        self,
        /,
        endpoint: str,
        *,
        _anchor: str | None = None,
        _method: str | None = None,
        _scheme: str | None = None,
        _external: bool | None = None,
        **values: t.Any,
    ) -> str:
        """Generate a URL to the given endpoint with the given values.

        This is called by :func:`flask.url_for`, and can be called
        directly as well.

        An *endpoint* is the name of a URL rule, usually added with
        :meth:`@app.route() <route>`, and usually the same name as the
        view function. A route defined in a :class:`~flask.Blueprint`
        will prepend the blueprint's name separated by a ``.`` to the
        endpoint.

        In some cases, such as email messages, you want URLs to include
        the scheme and domain, like ``https://example.com/hello``. When
        not in an active request, URLs will be external by default, but
        this requires setting :data:`SERVER_NAME` so Flask knows what
        domain to use. :data:`APPLICATION_ROOT` and
        :data:`PREFERRED_URL_SCHEME` should also be configured as
        needed. This config is only used when not in an active request.

        Functions can be decorated with :meth:`url_defaults` to modify
        keyword arguments before the URL is built.

        If building fails for some reason, such as an unknown endpoint
        or incorrect values, the app's :meth:`handle_url_build_error`
        method is called. If that returns a string, that is returned,
        otherwise a :exc:`~werkzeug.routing.BuildError` is raised.

        :param endpoint: The endpoint name associated with the URL to
            generate. If this starts with a ``.``, the current blueprint
            name (if any) will be used.
        :param _anchor: If given, append this as ``#anchor`` to the URL.
        :param _method: If given, generate the URL associated with this
            method for the endpoint.
        :param _scheme: If given, the URL will have this scheme if it
            is external.
        :param _external: If given, prefer the URL to be internal
            (False) or require it to be external (True). External URLs
            include the scheme and domain. When not in an active
            request, URLs are external by default.
        :param values: Values to use for the variable parts of the URL
            rule. Unknown keys are appended as query string arguments,
            like ``?a=b&c=d``.

        .. versionadded:: 2.2
            Moved from ``flask.url_for``, which calls this method.
        """
        req_ctx = _cv_request.get(None)

        if req_ctx is not None:
            url_adapter = req_ctx.url_adapter
            blueprint_name = req_ctx.request.blueprint

            # If the endpoint starts with "." and the request matches a
            # blueprint, the endpoint is relative to the blueprint.
            if endpoint[:1] == ".":
                if blueprint_name is not None:
                    endpoint = f"{blueprint_name}{endpoint}"
                else:
                    endpoint = endpoint[1:]

            # When in a request, generate a URL without scheme and
            # domain by default, unless a scheme is given.
            if _external is None:
                _external = _scheme is not None
        else:
            app_ctx = _cv_app.get(None)

            # If called by helpers.url_for, an app context is active,
            # use its url_adapter. Otherwise, app.url_for was called
            # directly, build an adapter.
            if app_ctx is not None:
                url_adapter = app_ctx.url_adapter
            else:
                url_adapter = self.create_url_adapter(None)

            if url_adapter is None:
                raise RuntimeError(
                    "Unable to build URLs outside an active request"
                    " without 'SERVER_NAME' configured. Also configure"
                    " 'APPLICATION_ROOT' and 'PREFERRED_URL_SCHEME' as"
                    " needed."
                )

            # When outside a request, generate a URL with scheme and
            # domain by default.
            if _external is None:
                _external = True

        # It is an error to set _scheme when _external=False, in order
        # to avoid accidental insecure URLs.
        if _scheme is not None and not _external:
            raise ValueError("When specifying '_scheme', '_external' must be True.")

        self.inject_url_defaults(endpoint, values)

        try:
            rv = url_adapter.build(  # type: ignore[union-attr]
                endpoint,
                values,
                method=_method,
                url_scheme=_scheme,
                force_external=_external,
            )
        except BuildError as error:
            values.update(
                _anchor=_anchor, _method=_method, _scheme=_scheme, _external=_external
            )
            return self.handle_url_build_error(error, endpoint, values)

        if _anchor is not None:
            _anchor = _url_quote(_anchor, safe="%!#$&'()*+,/:;=?@")
            rv = f"{rv}#{_anchor}"

        return rv

    def make_response(self, rv: ft.ResponseReturnValue) -> Response:
        """Convert the return value from a view function to an instance of
        :attr:`response_class`.

        :param rv: the return value from the view function. The view function
            must return a response. Returning ``None``, or the view ending
            without returning, is not allowed. The following types are allowed
            for ``view_rv``:

            ``str``
                A response object is created with the string encoded to UTF-8
                as the body.

            ``bytes``
                A response object is created with the bytes as the body.

            ``dict``
                A dictionary that will be jsonify'd before being returned.

            ``list``
                A list that will be jsonify'd before being returned.

            ``generator`` or ``iterator``
                A generator that returns ``str`` or ``bytes`` to be
                streamed as the response.

            ``tuple``
                Either ``(body, status, headers)``, ``(body, status)``, or
                ``(body, headers)``, where ``body`` is any of the other types
                allowed here, ``status`` is a string or an integer, and
                ``headers`` is a dictionary or a list of ``(key, value)``
                tuples. If ``body`` is a :attr:`response_class` instance,
                ``status`` overwrites the exiting value and ``headers`` are
                extended.

            :attr:`response_class`
                The object is returned unchanged.

            other :class:`~werkzeug.wrappers.Response` class
                The object is coerced to :attr:`response_class`.

            :func:`callable`
                The function is called as a WSGI application. The result is
                used to create a response object.

        .. versionchanged:: 2.2
            A generator will be converted to a streaming response.
            A list will be converted to a JSON response.

        .. versionchanged:: 1.1
            A dict will be converted to a JSON response.

        .. versionchanged:: 0.9
           Previously a tuple was interpreted as the arguments for the
           response object.
        """

        status: int | None = None
        headers: HeadersValue | None = None

        # unpack tuple returns
        if isinstance(rv, tuple):
            len_rv = len(rv)

            # a 3-tuple is unpacked directly
            if len_rv == 3:
                rv, status, headers = rv  # type: ignore[misc]
            # decide if a 2-tuple has status or headers
            elif len_rv == 2:
                if isinstance(rv[1], (Headers, dict, tuple, list)):
                    rv, headers = rv  # pyright: ignore
                else:
                    rv, status = rv  # type: ignore[assignment,misc]
            # other sized tuples are not allowed
            else:
                raise TypeError(
                    "The view function did not return a valid response tuple."
                    " The tuple must have the form (body, status, headers),"
                    " (body, status), or (body, headers)."
                )

        # the body must not be None
        if rv is None:
            raise TypeError(
                f"The view function for {request.endpoint!r} did not"
                " return a valid response. The function either returned"
                " None or ended without a return statement."
            )

        # make sure the body is an instance of the response class
        if not isinstance(rv, self.response_class):
            if isinstance(rv, (str, bytes, bytearray)) or isinstance(rv, cabc.Iterator):
                # let the response class set the status and headers instead of
                # waiting to do it manually, so that the class can handle any
                # special logic
                rv = self.response_class(
                    rv,  # pyright: ignore
                    status=status,
                    headers=headers,  # type: ignore[arg-type]
                )
                status = headers = None
            elif isinstance(rv, (dict, list)):
                rv = self.json.response(rv)
            elif isinstance(rv, BaseResponse) or callable(rv):
                # evaluate a WSGI callable, or coerce a different response
                # class to the correct type
                try:
                    rv = self.response_class.force_type(
                        rv,  # type: ignore[arg-type]
                        request.environ,
                    )
                except TypeError as e:
                    raise TypeError(
                        f"{e}\nThe view function did not return a valid"
                        " response. The return type must be a string,"
                        " dict, list, tuple with headers or status,"
                        " Response instance, or WSGI callable, but it"
                        f" was a {type(rv).__name__}."
                    ).with_traceback(sys.exc_info()[2]) from None
            else:
                raise TypeError(
                    "The view function did not return a valid"
                    " response. The return type must be a string,"
                    " dict, list, tuple with headers or status,"
                    " Response instance, or WSGI callable, but it was a"
                    f" {type(rv).__name__}."
                )

        rv = t.cast(Response, rv)
        # prefer the status if it was provided
        if status is not None:
            if isinstance(status, (str, bytes, bytearray)):
                rv.status = status
            else:
                rv.status_code = status

        # extend existing headers with provided headers
        if headers:
            rv.headers.update(headers)

        return rv

    def preprocess_request(self) -> ft.ResponseReturnValue | None:
        """Called before the request is dispatched. Calls
        :attr:`url_value_preprocessors` registered with the app and the
        current blueprint (if any). Then calls :attr:`before_request_funcs`
        registered with the app and the blueprint.

        If any :meth:`before_request` handler returns a non-None value, the
        value is handled as if it was the return value from the view, and
        further request handling is stopped.
        """
        names = (None, *reversed(request.blueprints))

        for name in names:
            if name in self.url_value_preprocessors:
                for url_func in self.url_value_preprocessors[name]:
                    url_func(request.endpoint, request.view_args)

        for name in names:
            if name in self.before_request_funcs:
                for before_func in self.before_request_funcs[name]:
                    rv = self.ensure_sync(before_func)()

                    if rv is not None:
                        return rv  # type: ignore[no-any-return]

        return None

    def process_response(self, response: Response) -> Response:
        """Can be overridden in order to modify the response object
        before it's sent to the WSGI server.  By default this will
        call all the :meth:`after_request` decorated functions.

        .. versionchanged:: 0.5
           As of Flask 0.5 the functions registered for after request
           execution are called in reverse order of registration.

        :param response: a :attr:`response_class` object.
        :return: a new response object or the same, has to be an
                 instance of :attr:`response_class`.
        """
        ctx = request_ctx._get_current_object()  # type: ignore[attr-defined]

        for func in ctx._after_request_functions:
            response = self.ensure_sync(func)(response)

        for name in chain(request.blueprints, (None,)):
            if name in self.after_request_funcs:
                for func in reversed(self.after_request_funcs[name]):
                    response = self.ensure_sync(func)(response)

        if not self.session_interface.is_null_session(ctx.session):
            self.session_interface.save_session(self, ctx.session, response)

        return response

    def do_teardown_request(
        self,
        exc: BaseException | None = _sentinel,  # type: ignore[assignment]
    ) -> None:
        """Called after the request is dispatched and the response is
        returned, right before the request context is popped.

        This calls all functions decorated with
        :meth:`teardown_request`, and :meth:`Blueprint.teardown_request`
        if a blueprint handled the request. Finally, the
        :data:`request_tearing_down` signal is sent.

        This is called by
        :meth:`RequestContext.pop() <flask.ctx.RequestContext.pop>`,
        which may be delayed during testing to maintain access to
        resources.

        :param exc: An unhandled exception raised while dispatching the
            request. Detected from the current exception information if
            not passed. Passed to each teardown function.

        .. versionchanged:: 0.9
            Added the ``exc`` argument.
        """
        if exc is _sentinel:
            exc = sys.exc_info()[1]

        for name in chain(request.blueprints, (None,)):
            if name in self.teardown_request_funcs:
                for func in reversed(self.teardown_request_funcs[name]):
                    self.ensure_sync(func)(exc)

        request_tearing_down.send(self, _async_wrapper=self.ensure_sync, exc=exc)

    def do_teardown_appcontext(
        self,
        exc: BaseException | None = _sentinel,  # type: ignore[assignment]
    ) -> None:
        """Called right before the application context is popped.

        When handling a request, the application context is popped
        after the request context. See :meth:`do_teardown_request`.

        This calls all functions decorated with
        :meth:`teardown_appcontext`. Then the
        :data:`appcontext_tearing_down` signal is sent.

        This is called by
        :meth:`AppContext.pop() <flask.ctx.AppContext.pop>`.

        .. versionadded:: 0.9
        """
        if exc is _sentinel:
            exc = sys.exc_info()[1]

        for func in reversed(self.teardown_appcontext_funcs):
            self.ensure_sync(func)(exc)

        appcontext_tearing_down.send(self, _async_wrapper=self.ensure_sync, exc=exc)

    def app_context(self) -> AppContext:
        """Create an :class:`~flask.ctx.AppContext`. Use as a ``with``
        block to push the context, which will make :data:`current_app`
        point at this application.

        An application context is automatically pushed by
        :meth:`RequestContext.push() <flask.ctx.RequestContext.push>`
        when handling a request, and when running a CLI command. Use
        this to manually create a context outside of these situations.

        ::

            with app.app_context():
                init_db()

        See :doc:`/appcontext`.

        .. versionadded:: 0.9
        """
        return AppContext(self)

    def request_context(self, environ: WSGIEnvironment) -> RequestContext:
        """Create a :class:`~flask.ctx.RequestContext` representing a
        WSGI environment. Use a ``with`` block to push the context,
        which will make :data:`request` point at this request.

        See :doc:`/reqcontext`.

        Typically you should not call this from your own code. A request
        context is automatically pushed by the :meth:`wsgi_app` when
        handling a request. Use :meth:`test_request_context` to create
        an environment and context instead of this method.

        :param environ: a WSGI environment
        """
        return RequestContext(self, environ)

    def test_request_context(self, *args: t.Any, **kwargs: t.Any) -> RequestContext:
        """Create a :class:`~flask.ctx.RequestContext` for a WSGI
        environment created from the given values. This is mostly useful
        during testing, where you may want to run a function that uses
        request data without dispatching a full request.

        See :doc:`/reqcontext`.

        Use a ``with`` block to push the context, which will make
        :data:`request` point at the request for the created
        environment. ::

            with app.test_request_context(...):
                generate_report()

        When using the shell, it may be easier to push and pop the
        context manually to avoid indentation. ::

            ctx = app.test_request_context(...)
            ctx.push()
            ...
            ctx.pop()

        Takes the same arguments as Werkzeug's
        :class:`~werkzeug.test.EnvironBuilder`, with some defaults from
        the application. See the linked Werkzeug docs for most of the
        available arguments. Flask-specific behavior is listed here.

        :param path: URL path being requested.
        :param base_url: Base URL where the app is being served, which
            ``path`` is relative to. If not given, built from
            :data:`PREFERRED_URL_SCHEME`, ``subdomain``,
            :data:`SERVER_NAME`, and :data:`APPLICATION_ROOT`.
        :param subdomain: Subdomain name to append to
            :data:`SERVER_NAME`.
        :param url_scheme: Scheme to use instead of
            :data:`PREFERRED_URL_SCHEME`.
        :param data: The request body, either as a string or a dict of
            form keys and values.
        :param json: If given, this is serialized as JSON and passed as
            ``data``. Also defaults ``content_type`` to
            ``application/json``.
        :param args: other positional arguments passed to
            :class:`~werkzeug.test.EnvironBuilder`.
        :param kwargs: other keyword arguments passed to
            :class:`~werkzeug.test.EnvironBuilder`.
        """
        from .testing import EnvironBuilder

        builder = EnvironBuilder(self, *args, **kwargs)

        try:
            return self.request_context(builder.get_environ())
        finally:
            builder.close()

    def wsgi_app(
        self, environ: WSGIEnvironment, start_response: StartResponse
    ) -> cabc.Iterable[bytes]:
        """The actual WSGI application. This is not implemented in
        :meth:`__call__` so that middlewares can be applied without
        losing a reference to the app object. Instead of doing this::

            app = MyMiddleware(app)

        It's a better idea to do this instead::

            app.wsgi_app = MyMiddleware(app.wsgi_app)

        Then you still have the original application object around and
        can continue to call methods on it.

        .. versionchanged:: 0.7
            Teardown events for the request and app contexts are called
            even if an unhandled error occurs. Other events may not be
            called depending on when an error occurs during dispatch.
            See :ref:`callbacks-and-errors`.

        :param environ: A WSGI environment.
        :param start_response: A callable accepting a status code,
            a list of headers, and an optional exception context to
            start the response.
        """
        ctx = self.request_context(environ)
        error: BaseException | None = None
        try:
            try:
                ctx.push()
                response = self.full_dispatch_request()
            except Exception as e:
                error = e
                response = self.handle_exception(e)
            except:  # noqa: B001
                error = sys.exc_info()[1]
                raise
            return response(environ, start_response)
        finally:
            if "werkzeug.debug.preserve_context" in environ:
                environ["werkzeug.debug.preserve_context"](_cv_app.get())
                environ["werkzeug.debug.preserve_context"](_cv_request.get())

            if error is not None and self.should_ignore_error(error):
                error = None

            ctx.pop(error)

    def __call__(
        self, environ: WSGIEnvironment, start_response: StartResponse
    ) -> cabc.Iterable[bytes]:
        """The WSGI server calls the Flask application object as the
        WSGI application. This calls :meth:`wsgi_app`, which can be
        wrapped to apply middleware.
        """
        return self.wsgi_app(environ, start_response)
>>>>>>> cfc9b6af5e1d5697dd003ccf010269bd3f0df0de
