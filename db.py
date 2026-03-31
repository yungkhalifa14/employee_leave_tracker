import sqlite3
import os

DB_FILE = os.environ.get('DATABASE_URL', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'leave_tracker.db'))

# Database Path from Environment Variable for portability
DB_PATH = os.environ.get('DATABASE_PATH', 'leave_tracker.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Users table — covers all roles: admin, manager, employee
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            leave_limit INTEGER DEFAULT 26,
            team_id INTEGER,
            email TEXT UNIQUE,
            reset_token TEXT,
            reset_token_expiry TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams (id)
        );
    ''')

    # Teams table — created by managers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            manager_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            join_token TEXT UNIQUE
        )
    ''')

    # Public holidays
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS holidays (
            date TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
    ''')

    # Leave requests — submitted by employees
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | declined
            manager_comment TEXT
        )
    ''')

    conn.commit()
    conn.close()
    migrate_db()

def migrate_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Add columns if they don't exist
    columns = [
        ('email', 'TEXT'),
        ('reset_token', 'TEXT'),
        ('reset_token_expiry', 'TIMESTAMP')
    ]
    for col_name, col_type in columns:
        try:
            cursor.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')
        except sqlite3.OperationalError:
            pass # Already exists
            
    # Add join_token to teams
    try:
        cursor.execute('ALTER TABLE teams ADD COLUMN join_token TEXT')
    except sqlite3.OperationalError:
        pass
    
    # Fill existing teams with tokens if they are null
    import secrets
    cursor.execute('SELECT id FROM teams WHERE join_token IS NULL')
    teams_without_tokens = cursor.fetchall()
    for (tid,) in teams_without_tokens:
        token = secrets.token_urlsafe(16)
        cursor.execute('UPDATE teams SET join_token = ? WHERE id = ?', (token, tid))
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print(f"Database initialised at {DB_FILE}")
