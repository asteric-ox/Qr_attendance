<<<<<<< HEAD
import csv
import mysql.connector
from werkzeug.security import generate_password_hash

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Delvin@2005",
    "database": "qr_attendence"
}

def reimport_all():
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        cur = conn.cursor()

        # Clear current users to avoid any confusion with old passwords
        # Except the admin1 which we use for management
        cur.execute("DELETE FROM users WHERE username != 'admin1'")
        
        # 🧑‍🏫 Import Faculty
        try:
            with open("faculty.csv", newline='', encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cur.execute("""
                        INSERT INTO users (username, password, role, name, branch)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        row["username"].strip(),
                        generate_password_hash(row["password"].strip()),
                        "faculty",
                        row["name"].strip(),
                        row["branch"].strip()
                    ))
        except Exception as e:
            print(f"Faculty error: {e}")

        # 🎓 Import Students
        try:
            with open("students.csv", newline='', encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cur.execute("""
                        INSERT INTO users (username, password, role, name, roll_no, branch, semester)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        row["username"].strip(),
                        generate_password_hash(row["password"].strip()),
                        "student",
                        row["name"].strip(),
                        row["roll_no"].strip(),
                        row["branch"].strip(),
                        row["semester"].strip()
                    ))
        except Exception as e:
            print(f"Student error: {e}")

        conn.commit()
        conn.close()
        print("SUCCESS: All Faculty and Student passwords have been reset and updated from CSV files in MySQL.")
    except mysql.connector.Error as err:
        print(f"Database error: {err}")

if __name__ == "__main__":
    reimport_all()
=======
import csv
import mysql.connector
from werkzeug.security import generate_password_hash

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Delvin@2005",
    "database": "qr_attendence"
}

def reimport_all():
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        cur = conn.cursor()

        # Clear current users to avoid any confusion with old passwords
        # Except the admin1 which we use for management
        cur.execute("DELETE FROM users WHERE username != 'admin1'")
        
        # 🧑‍🏫 Import Faculty
        try:
            with open("faculty.csv", newline='', encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cur.execute("""
                        INSERT INTO users (username, password, role, name, branch)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        row["username"].strip(),
                        generate_password_hash(row["password"].strip()),
                        "faculty",
                        row["name"].strip(),
                        row["branch"].strip()
                    ))
        except Exception as e:
            print(f"Faculty error: {e}")

        # 🎓 Import Students
        try:
            with open("students.csv", newline='', encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cur.execute("""
                        INSERT INTO users (username, password, role, name, roll_no, branch, semester)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        row["username"].strip(),
                        generate_password_hash(row["password"].strip()),
                        "student",
                        row["name"].strip(),
                        row["roll_no"].strip(),
                        row["branch"].strip(),
                        row["semester"].strip()
                    ))
        except Exception as e:
            print(f"Student error: {e}")

        conn.commit()
        conn.close()
        print("SUCCESS: All Faculty and Student passwords have been reset and updated from CSV files in MySQL.")
    except mysql.connector.Error as err:
        print(f"Database error: {err}")

if __name__ == "__main__":
    reimport_all()
>>>>>>> cfc9b6af5e1d5697dd003ccf010269bd3f0df0de
