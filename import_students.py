import csv
import mysql.connector
from werkzeug.security import generate_password_hash

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Delvin@2005",
    "database": "qr_attendence"
}

conn = mysql.connector.connect(**DATABASE_CONFIG)
cur = conn.cursor()

with open("students.csv", newline='', encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cur.execute("""
            INSERT IGNORE INTO users
            (username, password, role, name, roll_no, branch, semester)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            row["username"],
            generate_password_hash(row["password"]),
            row["role"],
            row.get("name", "N/A"),
            row.get("roll_no", "N/A"),
            row.get("branch", "N/A"),
            row.get("semester", "N/A")
        ))

conn.commit()
conn.close()

print("Student data imported successfully into MySQL with hashed passwords")
