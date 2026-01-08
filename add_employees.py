from tracker import LeaveTracker

def add_batch_employees():
    tracker = LeaveTracker()
    names = [
        "Alek",
        "Karol",
        "Szymon",
        "Wiktoria",
        "Sofia",
        "Kuba",
        "Vika",
        "Ivan",
        "Michał",
        "Piotr",
        "Krystian",
        "Hubert",
        "Natalia"
    ]
    
    print("Adding employees...")
    for name in names:
        try:
            tracker.add_employee(name)
            print(f"Added: {name}")
        except Exception as e:
            print(f"Error adding {name}: {e}")
            
    print("Done.")

if __name__ == "__main__":
    add_batch_employees()
