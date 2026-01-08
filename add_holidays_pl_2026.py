from tracker import LeaveTracker

def add_holidays():
    tracker = LeaveTracker()
    
    holidays = [
        ("2026-01-01", "Nowy Rok"),
        ("2026-01-06", "Święto Trzech Króli"),
        ("2026-04-05", "Niedziela Wielkanocna"),
        ("2026-04-06", "Poniedziałek Wielkanocny"),
        ("2026-05-01", "Święto Pracy"),
        ("2026-05-03", "Święto Konstytucji 3 Maja"),
        ("2026-05-24", "Zesłanie Ducha Świętego (Zielone Świątki)"),
        ("2026-06-04", "Boże Ciało"),
        ("2026-08-15", "Wniebowzięcie NMP / Święto Wojska Polskiego"),
        ("2026-11-01", "Wszystkich Świętych"),
        ("2026-11-11", "Narodowe Święto Niepodległości"),
        ("2026-12-25", "Pierwszy Dzień Bożego Narodzenia"),
        ("2026-12-26", "Drugi Dzień Bożego Narodzenia")
    ]
    
    print("Adding Polish Holidays for 2026...")
    for date, name in holidays:
        tracker.add_holiday(date, name)
        print(f"Added: {date} - {name}")
        
    print("Done.")

if __name__ == "__main__":
    add_holidays()
