from db import get_connection

def migrate():
    print("Migrating database...")
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(employees)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'leave_limit' not in columns:
            print("Adding 'leave_limit' column to 'employees' table...")
            cursor.execute("ALTER TABLE employees ADD COLUMN leave_limit INTEGER DEFAULT 26")
            conn.commit()
            print("Migration successful.")
        else:
            print("'leave_limit' column already exists.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
