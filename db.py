import sqlite3
import os

# Store DB in user's home folder to avoid permission issues when frozen
DB_FILE = os.path.join(os.path.expanduser('~'), 'leave_tracker.db')

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create employees table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            leave_limit INTEGER DEFAULT 26
        )
    ''')
    
    # Create holidays table
    # Using date string YYYY-MM-DD
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS holidays (
            date TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
    ''')
    
    # Create leaves table
    # storing dates as YYYY-MM-DD strings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees (id)
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized.")
