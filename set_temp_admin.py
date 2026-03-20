<<<<<<< HEAD
import mysql.connector
from werkzeug.security import generate_password_hash

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Delvin@2005",
    "database": "qr_attendence"
}

def create_admin_user():
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        cur = conn.cursor(dictionary=True)
        
        # Check if user already exists
        cur.execute("SELECT id FROM users WHERE username = 'admin'")
        user = cur.fetchone()
        
        hashed_pw = generate_password_hash("123456")
        
        if user:
            print("Updating existing 'admin' user password...")
            cur.execute("UPDATE users SET password = %s, role = 'admin' WHERE username = 'admin'", (hashed_pw,))
        else:
            print("Creating new 'admin' user...")
            cur.execute("""
                INSERT INTO users (username, password, role, name) 
                VALUES (%s, %s, %s, %s)
            """, ("admin", hashed_pw, "admin", "System Administrator"))
            
        conn.commit()
        conn.close()
        print("SUCCESS: Admin credentials set. Username: 'admin', Password: '123456'")
        
    except mysql.connector.Error as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    create_admin_user()
=======
import mysql.connector
from werkzeug.security import generate_password_hash

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Delvin@2005",
    "database": "qr_attendence"
}

def create_admin_user():
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        cur = conn.cursor(dictionary=True)
        
        # Check if user already exists
        cur.execute("SELECT id FROM users WHERE username = 'admin'")
        user = cur.fetchone()
        
        hashed_pw = generate_password_hash("123456")
        
        if user:
            print("Updating existing 'admin' user password...")
            cur.execute("UPDATE users SET password = %s, role = 'admin' WHERE username = 'admin'", (hashed_pw,))
        else:
            print("Creating new 'admin' user...")
            cur.execute("""
                INSERT INTO users (username, password, role, name) 
                VALUES (%s, %s, %s, %s)
            """, ("admin", hashed_pw, "admin", "System Administrator"))
            
        conn.commit()
        conn.close()
        print("SUCCESS: Admin credentials set. Username: 'admin', Password: '123456'")
        
    except mysql.connector.Error as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    create_admin_user()
>>>>>>> cfc9b6af5e1d5697dd003ccf010269bd3f0df0de
