import sqlite3
import os

# For server deployment, store DB in the app directory or a configurable path
DB_FILE = os.environ.get('DATABASE_URL', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'leave_tracker.db'))

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create teams table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            owner_id INTEGER REFERENCES employees(id)
        )
    ''')
    
    # Create employees table (acts as users)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            leave_limit INTEGER DEFAULT 26,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT DEFAULT 'user',
            team_id INTEGER,
            invite_token TEXT UNIQUE,
            FOREIGN KEY (team_id) REFERENCES teams (id)
        )
    ''')
    
    # Create holidays table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS holidays (
            date TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
    ''')
    
    # Create leaves table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            manager_comment TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees (id)
        )
    ''')
    
    conn.commit()
    
    # Auto-migration for leaves table
    cursor.execute("PRAGMA table_info(leaves)")
    leave_cols = [info[1] for info in cursor.fetchall()]
    
    if 'status' not in leave_cols:
        cursor.execute("ALTER TABLE leaves ADD COLUMN status TEXT DEFAULT 'approved'")
        # For existing ones, we assume they were already approved
        cursor.execute("UPDATE leaves set status = 'approved' where status IS NULL")
    if 'manager_comment' not in leave_cols:
        cursor.execute("ALTER TABLE leaves ADD COLUMN manager_comment TEXT")
        
    conn.commit()
    
    # Auto-migration for teams table
    cursor.execute("PRAGMA table_info(teams)")
    teams_cols = [info[1] for info in cursor.fetchall()]
    if 'owner_id' not in teams_cols:
        cursor.execute("ALTER TABLE teams ADD COLUMN owner_id INTEGER REFERENCES employees(id)")
    
    # Auto-migration: check if new columns exist in employees
    cursor.execute("PRAGMA table_info(employees)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if 'leave_limit' not in columns:
        cursor.execute("ALTER TABLE employees ADD COLUMN leave_limit INTEGER DEFAULT 26")
    if 'username' not in columns:
        cursor.execute("ALTER TABLE employees ADD COLUMN username TEXT")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_employee_username ON employees(username)")
    if 'password_hash' not in columns:
        cursor.execute("ALTER TABLE employees ADD COLUMN password_hash TEXT")
    if 'role' not in columns:
        cursor.execute("ALTER TABLE employees ADD COLUMN role TEXT DEFAULT 'user'")
    if 'invite_token' not in columns:
        cursor.execute("ALTER TABLE employees ADD COLUMN invite_token TEXT")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_employee_invite ON employees(invite_token)")
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print(f"Database initialized at {DB_FILE}")
