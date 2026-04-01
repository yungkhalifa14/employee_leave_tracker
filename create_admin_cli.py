import getpass
from tracker import LeaveTracker
from werkzeug.security import generate_password_hash
from db import init_db, migrate_db

def create_admin():
    print("--- Create Admin Account ---")
    
    # Ensure DB is ready
    init_db()
    migrate_db()
    
    name = input("Enter Full Name: ")
    username = input("Enter Username: ")
    email = input("Enter Email (optional, but recommended for recovery): ")
    password = getpass.getpass("Enter Password: ")
    confirm_password = getpass.getpass("Confirm Password: ")
    
    if password != confirm_password:
        print("Error: Passwords do not match.")
        return

    tracker = LeaveTracker()
    hashed_pw = generate_password_hash(password)
    
    # add_user(name, username, password_hash, role='employee', leave_limit=26, team_id=None, email=None)
    success = tracker.add_user(
        name=name,
        username=username,
        password_hash=hashed_pw,
        role='admin',
        email=email if email else None
    )
    
    if success:
        print(f"\nSuccess! Admin account '{username}' created.")
    else:
        print(f"\nError: Could not create account. Username '{username}' or email might already be taken.")

if __name__ == "__main__":
    create_admin()
