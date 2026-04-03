import os
from tracker import LeaveTracker
from werkzeug.security import generate_password_hash
from db import init_db, migrate_db

def create_specific_manager():
    """ Utility script to create a manager account with specific credentials. """
    print("--- Creating Manager Account ---")
    
    # Ensure DB is ready (tables exist and migrations are applied)
    init_db()
    migrate_db()
    
    name = "Piotr Nałęcz"
    username = "PNałęcz1"
    password = "qaxgyc-8Qompi-jucpym"
    role = "manager"
    
    tracker = LeaveTracker()
    
    # Check if user already exists
    existing = tracker.get_user_by_username(username)
    if existing:
        print(f"Error: User '{username}' already exists.")
        return

    hashed_pw = generate_password_hash(password)
    
    # add_user(name, username, password_hash, role='employee', leave_limit=26, team_id=None, email=None)
    success = tracker.add_user(
        name=name,
        username=username,
        password_hash=hashed_pw,
        role=role
    )
    
    if success:
        print(f"\nSuccess! Manager account '{username}' created.")
        print("You can now log in to the app with these credentials.")
    else:
        print(f"\nError: Could not create account. Username might already be taken.")

if __name__ == "__main__":
    create_specific_manager()
