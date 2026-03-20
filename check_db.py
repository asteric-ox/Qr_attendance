<<<<<<< HEAD
import mysql.connector

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Delvin@2005",
    "database": "qr_attendence"
}

try:
    conn = mysql.connector.connect(**DATABASE_CONFIG)
    cur = conn.cursor()
    print("--- Branches ---")
    cur.execute('SELECT DISTINCT branch FROM subjects')
    print("Subjects:", cur.fetchall())
    cur.execute('SELECT DISTINCT branch FROM users')
    print("Users:", cur.fetchall())
    cur.execute('SELECT DISTINCT branch FROM timetable')
    print("Timetable:", cur.fetchall())
    print("\n--- Semesters ---")
    cur.execute('SELECT DISTINCT semester FROM subjects')
    print("Subjects:", cur.fetchall())
    cur.execute('SELECT DISTINCT semester FROM users')
    print("Users:", cur.fetchall())
    cur.execute('SELECT DISTINCT semester FROM timetable')
    print("Timetable:", cur.fetchall())
    conn.close()
except mysql.connector.Error as err:
    print("Error:", err)
=======
import mysql.connector

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Delvin@2005",
    "database": "qr_attendence"
}

try:
    conn = mysql.connector.connect(**DATABASE_CONFIG)
    cur = conn.cursor()
    print("--- Branches ---")
    cur.execute('SELECT DISTINCT branch FROM subjects')
    print("Subjects:", cur.fetchall())
    cur.execute('SELECT DISTINCT branch FROM users')
    print("Users:", cur.fetchall())
    cur.execute('SELECT DISTINCT branch FROM timetable')
    print("Timetable:", cur.fetchall())
    print("\n--- Semesters ---")
    cur.execute('SELECT DISTINCT semester FROM subjects')
    print("Subjects:", cur.fetchall())
    cur.execute('SELECT DISTINCT semester FROM users')
    print("Users:", cur.fetchall())
    cur.execute('SELECT DISTINCT semester FROM timetable')
    print("Timetable:", cur.fetchall())
    conn.close()
except mysql.connector.Error as err:
    print("Error:", err)
>>>>>>> cfc9b6af5e1d5697dd003ccf010269bd3f0df0de
