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
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username, role FROM users")
    users = cur.fetchall()
    print("Users in DB:")
    for user in users:
        print(user)
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
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username, role FROM users")
    users = cur.fetchall()
    print("Users in DB:")
    for user in users:
        print(user)
    conn.close()
except mysql.connector.Error as err:
    print("Error:", err)
>>>>>>> cfc9b6af5e1d5697dd003ccf010269bd3f0df0de
