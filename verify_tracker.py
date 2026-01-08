import os
from db import init_db, DB_FILE
from tracker import LeaveTracker

def run_verification():
    # Clean up old DB
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    
    init_db()
    tracker = LeaveTracker()
    
    print("--- Verifying Employee Creation ---")
    alice_id = tracker.add_employee("Alice")
    bob_id = tracker.add_employee("Bob")
    print(f"Added Alice (ID: {alice_id}) and Bob (ID: {bob_id})")
    
    print("\n--- Verifying Holiday Creation ---")
    tracker.add_holiday("2023-12-25", "Christmas")
    print("Added Christmas on 2023-12-25")
    
    print("\n--- Verifying Leave Booking ---")
    # Alice takes leave from Dec 20 to Dec 22
    tracker.add_leave(alice_id, "2023-12-20", "2023-12-22", "Vacation")
    print("Booked leave for Alice: 2023-12-20 to 2023-12-22")
    
    print("\n--- Verifying Status Check ---")
    # Check Alice on leave date
    status_alice_21 = tracker.check_employee_status(alice_id, "2023-12-21")
    print(f"Alice status on 2023-12-21: {status_alice_21}")
    assert "On Leave" in status_alice_21
    
    # Check Bob on normal day
    status_bob_21 = tracker.check_employee_status(bob_id, "2023-12-21")
    print(f"Bob status on 2023-12-21: {status_bob_21}")
    assert "Working" in status_bob_21
    
    # Check Alice on Working day
    status_alice_23 = tracker.check_employee_status(alice_id, "2023-12-23")
    print(f"Alice status on 2023-12-23: {status_alice_23}")
    assert "Working" in status_alice_23
    
    # Check Holiday status
    status_alice_25 = tracker.check_employee_status(alice_id, "2023-12-25")
    print(f"Alice status on 2023-12-25: {status_alice_25}")
    assert "Holiday" in status_alice_25

    print("\n--- Verifying Absentee List ---")
    absentees, holiday_msg = tracker.get_absent_employees("2023-12-21")
    print(f"Absentees on 2023-12-21: {absentees}")
    assert any(a[0] == "Alice" for a in absentees)
    assert not any(a[0] == "Bob" for a in absentees)
    
    absentees_hol, holiday_msg_hol = tracker.get_absent_employees("2023-12-25")
    print(f"Absentees on 2023-12-25 (Christmas): {holiday_msg_hol}")
    assert "Holiday" in holiday_msg_hol

    print("\nVerification Successful!")

if __name__ == "__main__":
    run_verification()
