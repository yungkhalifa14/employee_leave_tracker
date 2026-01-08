from tracker import LeaveTracker

def add_holidays():
    tracker = LeaveTracker()
    
    holidays = [
        ("2026-01-01", "New Year's Day"),
        ("2026-01-06", "Epiphany"),
        ("2026-04-05", "Easter Sunday"),
        ("2026-04-06", "Easter Monday"),
        ("2026-05-01", "Labour Day"),
        ("2026-05-03", "Constitution Day"),
        ("2026-05-24", "Pentecost Sunday"),
        ("2026-06-04", "Corpus Christi"),
        ("2026-08-15", "Assumption of Mary / Armed Forces Day"),
        ("2026-11-01", "All Saints' Day"),
        ("2026-11-11", "Independence Day"),
        ("2026-12-25", "Christmas Day"),
        ("2026-12-26", "Second Day of Christmas")
    ]
    
    print("Adding Polish Holidays for 2026...")
    for date, name in holidays:
        tracker.add_holiday(date, name)
        print(f"Added: {date} - {name}")
        
    print("Done.")

if __name__ == "__main__":
    add_holidays()
