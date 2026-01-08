from flask import Flask, render_template, request, redirect, url_for, flash
from tracker import LeaveTracker
from db import init_db
from datetime import datetime
import sys
import os
import webbrowser
import threading
import time
import subprocess

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def start_browser():
    """ Opens the browser and shows a notification """
    time.sleep(1.5) # Give Flask a moment to start
    url = "http://127.0.0.1:5001"
    
    # Simple logging to debug
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'app.log')
        with open(log_path, 'a') as f:
            f.write(f"[{datetime.now()}] Próba otwarcia przeglądarki dla {url}\n")
    except:
        pass

    # Try webbrowser first
    try:
        webbrowser.open(url)
    except Exception as e:
        try:
            with open(log_path, 'a') as f: f.write(f"Błąd webbrowser: {e}\n")
        except: pass

    # Additional macOS explicit handling for notification
    if sys.platform == 'darwin':
        try:
            # Notification
            script = f'display notification "Aplikacja działa pod adresem {url}" with title "Monitor Urlopów Uruchomiony"'
            subprocess.run(["osascript", "-e", script])
        except Exception as e:
            try:
                with open(log_path, 'a') as f: f.write(f"Błąd subprocess: {e}\n")
            except: pass

template_folder = resource_path('templates')
static_folder = resource_path('static')

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
app.secret_key = 'super_secret_key'  # Needed for flash messages

tracker = LeaveTracker()
# Ensure DB is ready
init_db()

POLISH_MONTHS = {
    1: "Styczeń", 2: "Luty", 3: "Marzec", 4: "Kwiecień",
    5: "Maj", 6: "Czerwiec", 7: "Lipiec", 8: "Sierpień",
    9: "Wrzesień", 10: "Październik", 11: "Listopad", 12: "Grudzień"
}

@app.route('/')
def dashboard():
    # Month navigation
    today = datetime.now()
    year = int(request.args.get('year', today.year))
    month = int(request.args.get('month', today.month))
    
    # Calculate start and end of month
    import calendar
    _, last_day = calendar.monthrange(year, month)
    
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    
    # Get calendar data
    events = tracker.get_monthly_data(start_date, end_date)
    
    # We need to construct the calendar grid
    cal = calendar.monthcalendar(year, month)
    calendar_data = []
    
    for week in cal:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append(None)
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                day_events = events.get(date_str)
                week_data.append({
                    'day': day,
                    'date': date_str,
                    'events': day_events
                })
        calendar_data.append(week_data)
    
    # Navigation links
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
        
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
        
    month_name = POLISH_MONTHS[month]
    
    return render_template('dashboard.html', 
                           calendar_data=calendar_data,
                           month_name=month_name,
                           year=year,
                           prev_month=prev_month, prev_year=prev_year,
                           next_month=next_month, next_year=next_year)

@app.route('/employees', methods=['GET', 'POST'])
def employees():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            tracker.add_employee(name)
            flash(f"Pracownik {name} został dodany.", 'success')
        else:
            flash("Imię jest wymagane.", 'error')
        return redirect(url_for('employees'))
    
    # Use new method to get balance info
    all_emps = tracker.get_employees_with_balance()
    return render_template('employees.html', employees=all_emps)

@app.route('/holidays', methods=['GET', 'POST'])
def holidays():
    if request.method == 'POST':
        name = request.form.get('name')
        date = request.form.get('date')
        if name and date:
            tracker.add_holiday(date, name)
            flash(f"Święto '{name}' ({date}) zostało dodane.", 'success')
        else:
            flash("Nazwa i data są wymagane.", 'error')
        return redirect(url_for('holidays'))
        
    # We don't have a get_all_holidays method in tracker yet.
    # Let's add a quick query here or update tracker. 
    # For speed, I'll do a quick query here, but cleaner would be in tracker.
    # I'll rely on the user just adding them for now, but listing them is good.
    # Let's add a helper method in this file for now to list holidays.
    from db import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT date, name FROM holidays ORDER BY date')
    existing_holidays = cursor.fetchall()
    conn.close()
    
    return render_template('holidays.html', holidays=existing_holidays)

@app.route('/leaves', methods=['GET', 'POST'])
def leaves():
    if request.method == 'POST':
        emp_id = request.form.get('employee_id')
        start = request.form.get('start_date')
        end = request.form.get('end_date')
        reason = request.form.get('reason')
        
        if emp_id and start and end and reason:
            tracker.add_leave(emp_id, start, end, reason)
            flash("Urlop został zarezerwowany.", 'success')
        else:
            flash("Wszystkie pola są wymagane.", 'error')
        return redirect(url_for('leaves'))
    
    all_emps = tracker.get_all_employees()
    return render_template('leaves.html', employees=all_emps)

@app.route('/shutdown')
def shutdown():
    """ Gracefully shut down the server """
    def delayed_shutdown():
        time.sleep(1)
        os._exit(0)
        
    threading.Thread(target=delayed_shutdown).start()
    return "Serwer jest wyłączany... Możesz zamknąć to okno."

if __name__ == '__main__':
    try:
        threading.Thread(target=start_browser, daemon=True).start()
        app.run(debug=False, port=5001)
    except Exception as e:
        try:
            log_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'app.log')
            with open(log_path, 'a') as f:
                f.write(f"[{datetime.now()}] CRITICAL ERROR: {e}\n")
                import traceback
                traceback.print_exc(file=f)
        except:
            pass
