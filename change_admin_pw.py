import sqlite3
import os
from werkzeug.security import generate_password_hash
import getpass
from db import get_connection

def change_admin_password():
    print("--- Zmiana hasła Administratora ---")
    new_password = getpass.getpass("Wprowadź nowe hasło: ")
    confirm_password = getpass.getpass("Potwierdź nowe hasło: ")
    
    if new_password != confirm_password:
        print("Błąd: Hasła nie są identyczne.")
        return

    hashed_pw = generate_password_hash(new_password)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if admin exists
    cursor.execute('SELECT id FROM users WHERE username = "admin"')
    admin = cursor.fetchone()
    
    if admin:
        cursor.execute('UPDATE users SET password_hash = ? WHERE username = "admin"', (hashed_pw,))
        conn.commit()
        print("Sukces: Hasło administratora zostało zmienione.")
    else:
        # If admin doesn't exist for some reason, create it
        cursor.execute('INSERT INTO users (name, username, password_hash, role) VALUES (?, ?, ?, ?)',
                       ("Administrator", "admin", hashed_pw, 'admin'))
        conn.commit()
        print("Sukces: Konto administratora zostało utworzone z nowym hasłem.")
    
    conn.close()

if __name__ == "__main__":
    change_admin_password()
