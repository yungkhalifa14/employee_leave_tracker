from flask import Flask, render_template, request, redirect, url_for, flash, make_response
import csv
import io
import calendar
from tracker import LeaveTracker
from db import init_db
from datetime import datetime, timedelta
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'super_secret_key'  # Needed for flash messages

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

tracker = LeaveTracker()
# Ensure DB is ready
init_db()

POLISH_MONTHS = {
    1: "Styczeń", 2: "Luty", 3: "Marzec", 4: "Kwiecień",
    5: "Maj", 6: "Czerwiec", 7: "Lipiec", 8: "Sierpień",
    9: "Wrzesień", 10: "Październik", 11: "Listopad", 12: "Grudzień"
}

# User Class for Flask-Login
class User(UserMixin):
    def __init__(self, id, name, username, role, team_id):
        self.id = str(id)
        self.name = name
        self.username = username
        self.role = role
        self.team_id = team_id

@login_manager.user_loader
def load_user(user_id):
    emp = tracker.get_employee_by_id(int(user_id))
    if emp and emp[3]: # ensure username exists
        return User(id=emp[0], name=emp[1], username=emp[3], role=emp[5], team_id=emp[6])
    return None

@app.context_processor
def inject_pending_leaves():
    if current_user.is_authenticated and current_user.role == 'admin':
        pending = tracker.get_pending_leaves()
        return dict(pending_leaves_count=len(pending), pending_leaves=pending)
    return dict(pending_leaves_count=0, pending_leaves=[])

# --- AUTH ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_data = tracker.get_user_by_username(username)
        # user_data: id, name, leave_limit, username, password_hash, role, team_id
        if user_data and user_data[4] and check_password_hash(user_data[4], password):
            user = User(id=user_data[0], name=user_data[1], username=user_data[3], role=user_data[5], team_id=user_data[6])
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Nieprawidłowa nazwa użytkownika lub hasło', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Only allow registration if no users exist, OR if current user is admin
    # Actually, let's let anyone register for now, but in reality you'd want admin only.
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        password = request.form.get('password')
        team_id = request.form.get('team_id') or None
        
        if not name or not username or not password:
            flash("Wszystkie pola są wymagane", "error")
            return redirect(url_for('register'))
            
        existing = tracker.get_user_by_username(username)
        if existing:
            flash("Użytkownik już istnieje", "error")
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password)
        
        # Make the first user an admin automatically, others user
        # We can check if any user exists. For simplicity, just make everyone 'user'
        # and we can make a CLI command to make admin, but let's make the first user admin.
        all_emps = tracker.get_employees_with_balance() # just to check count roughly
        role = 'admin' if len(all_emps) == 0 else 'user'
        
        if team_id:
            team_id = int(team_id)
            
        tracker.add_employee(name, username, hashed_pw, role, team_id)
        flash("Konto utworzone. Możesz się zalogować.", "success")
        return redirect(url_for('login'))
        
    teams = tracker.get_all_teams()
    return render_template('register.html', teams=teams)


def get_safe_year_month():
    today = datetime.now()
    try:
        year = int(request.args.get('year', today.year))
    except (ValueError, TypeError):
        year = today.year
        
    try:
        month = int(request.args.get('month', today.month))
    except (ValueError, TypeError):
        month = today.month
    return year, month

def get_calendar_context(year, month, team_id_filter=None):
    _, last_day = calendar.monthrange(year, month)
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    
    events = tracker.get_monthly_data(start_date, end_date)
    
    # Optional team filter
    # If team_id_filter is set, we need to filter the absentees
    if team_id_filter:
        team_emps = tracker.get_employees_by_team(team_id_filter)
        team_emp_names = {t[1] for t in team_emps}
        
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
                
                # Apply team filter to events
                filtered_events = None
                if day_events:
                    filtered_absentees = day_events['absentees']
                    if team_id_filter:
                        filtered_absentees = [a for a in filtered_absentees if a['name'] in team_emp_names]
                    
                    filtered_events = {
                        'holiday': day_events['holiday'],
                        'absentees': filtered_absentees
                    }

                week_data.append({
                    'day': day,
                    'date': date_str,
                    'events': filtered_events
                })
        calendar_data.append(week_data)
    
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
        
    return {
        'calendar_data': calendar_data,
        'month_name': POLISH_MONTHS[month],
        'month': month,
        'year': year,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'current_team_filter': team_id_filter
    }

@app.route('/')
@login_required
def dashboard():
    year, month = get_safe_year_month()
    
    # Team filtering
    team_filter = request.args.get('team_id')
    if team_filter and team_filter.isdigit():
        team_filter = int(team_filter)
    else:
        team_filter = None
        
    context = get_calendar_context(year, month, team_id_filter=team_filter)
    teams = tracker.get_all_teams()
    return render_template('dashboard.html', **context, teams=teams, endpoint='dashboard')

@app.route('/public')
def public_calendar():
    year, month = get_safe_year_month()
    context = get_calendar_context(year, month)
    return render_template('dashboard.html', **context, public_mode=True, endpoint='public_calendar')

@app.route('/export_csv')
@login_required
def export_csv():
    year, month = get_safe_year_month()
    _, last_day = calendar.monthrange(year, month)
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    
    data = tracker.get_monthly_data(start_date, end_date)
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Type', 'Details'])
    
    curr = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    while curr <= end:
        d_str = curr.strftime("%Y-%m-%d")
        day_data = data.get(d_str)
        
        if day_data:
            if day_data.get('holiday'):
                cw.writerow([d_str, 'Holiday', day_data['holiday']])
            
            for absentee in day_data.get('absentees', []):
                cw.writerow([d_str, 'Leave', f"{absentee['name']}: {absentee['reason']}"])
        
        curr += timedelta(days=1)
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=calendar_{year}_{month:02d}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/invite/<token>', methods=['GET', 'POST'])
def invite(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    emp = tracker.get_employee_by_token(token)
    if not emp:
        flash("Link aktywacyjny jest nieprawidłowy lub wygasł.", 'error')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username and password:
            if tracker.get_user_by_username(username):
                flash("Ta nazwa użytkownika jest już zajęta.", "error")
            else:
                pw_hash = generate_password_hash(password)
                if tracker.claim_invite(token, username, pw_hash):
                    flash("Konto zostało aktywowane! Możesz się teraz zalogować.", 'success')
                    return redirect(url_for('login'))
                else:
                    flash("Wystąpił błąd podczas aktywacji.", "error")
        else:
            flash("Wszystkie pola są wymagane.", 'error')
            
    return render_template('invite.html', employee=emp)

@app.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    if request.method == 'POST':
        if current_user.role != 'admin':
            flash("Brak uprawnień.", 'error')
            return redirect(url_for('employees'))
            
        name = request.form.get('name')
        limit = request.form.get('leave_limit', 26)
        team_id = request.form.get('team_id')
        
        if name and limit:
            try:
                limit = int(limit)
                t_id = int(team_id) if team_id else None
                # Create without credentials, generating invite token
                token = tracker.add_employee(name, limit, None, None, 'user', t_id)
                if token:
                    invite_link = url_for('invite', token=token, _external=True)
                    flash(f"Pracownik dodany! Link do zaproszenia: {invite_link}", 'success')
                else:
                    flash("Nie udało się dodać pracownika.", 'error')
            except ValueError:
                flash("Limit urlopu musi być liczbą.", 'error')
        else:
            flash("Imię i limit są wymagane.", 'error')
        return redirect(url_for('employees'))
    
    # Scope to current_user
    all_emps = tracker.get_employees_with_balance(current_user.id if current_user.role == 'admin' else None)
    teams = tracker.get_all_teams(current_user.id if current_user.role == 'admin' else None)
    
    # We also want to map team names
    team_map = {t[0]: t[1] for t in teams}
    for emp in all_emps:
        # We need team_id and role from full data
        full_data = tracker.get_employee_by_id(emp['id'])
        if full_data:
            emp['role'] = full_data[5]
            t_id = full_data[6]
            emp['team_name'] = team_map.get(t_id, 'Brak')
            
    return render_template('employees.html', employees=all_emps, teams=teams)

@app.route('/employees/edit/<int:emp_id>', methods=['GET', 'POST'])
@login_required
def edit_employee(emp_id):
    if current_user.role != 'admin' and int(current_user.id) != emp_id:
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('employees'))
        
    emp = tracker.get_employee_by_id(emp_id)
    if not emp:
        flash("Pracownik nie znaleziony.", 'error')
        return redirect(url_for('employees'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        limit = request.form.get('leave_limit')
        team_id = request.form.get('team_id')
        
        # Only admin can change limits and teams
        if current_user.role == 'admin':
            if name and limit:
                t_id = int(team_id) if team_id else None
                tracker.update_employee(emp_id, name, int(limit), t_id)
                flash(f"Dane pracownika {name} zostały zaktualizowane.", 'success')
                return redirect(url_for('employees'))
            else:
                flash("Wszystkie pola są wymagane.", 'error')
        else:
            flash("Nie masz uprawnień do edycji tych danych.", "error")
            
    teams = tracker.get_all_teams()
    return render_template('edit_employee.html', employee=emp, teams=teams)

@app.route('/employees/delete/<int:emp_id>', methods=['POST'])
@login_required
def delete_employee(emp_id):
    if current_user.role != 'admin':
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('employees'))
        
    tracker.delete_employee(emp_id)
    flash("Pracownik został usunięty.", 'success')
    return redirect(url_for('employees'))

@app.route('/teams', methods=['GET', 'POST'])
@login_required
def teams_view():
    if current_user.role != 'admin':
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            tracker.add_team(name, current_user.id)
            flash(f"Zespół {name} dodany.", "success")
        return redirect(url_for('teams_view'))
        
    all_teams = tracker.get_all_teams(current_user.id)
    return render_template('teams.html', teams=all_teams)

@app.route('/holidays', methods=['GET', 'POST'])
@login_required
def holidays():
    if request.method == 'POST':
        if current_user.role != 'admin':
            flash("Brak uprawnień.", 'error')
            return redirect(url_for('holidays'))
            
        name = request.form.get('name')
        date = request.form.get('date')
        if name and date:
            tracker.add_holiday(date, name)
            flash(f"Święto '{name}' ({date}) zostało dodane.", 'success')
        else:
            flash("Nazwa i data są wymagane.", 'error')
        return redirect(url_for('holidays'))
        
    from db import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT date, name FROM holidays ORDER BY date')
    existing_holidays = cursor.fetchall()
    conn.close()
    
    return render_template('holidays.html', holidays=existing_holidays)

@app.route('/leaves', methods=['GET', 'POST'])
@login_required
def leaves():
    if request.method == 'POST':
        emp_id = request.form.get('employee_id')
        start = request.form.get('start_date')
        end = request.form.get('end_date')
        reason = request.form.get('reason')
        
        # Only admin can add leave for others
        if current_user.role != 'admin' and str(current_user.id) != str(emp_id):
            flash("Brak uprawnień do dodawania urlopu dla innej osoby.", 'error')
            return redirect(url_for('leaves'))
            
        if emp_id and start and end and reason:
            status = 'approved' if current_user.role == 'admin' else 'pending'
            tracker.add_leave(emp_id, start, end, reason, status=status)
            if status == 'pending':
                flash("Wniosek o urlop został wysłany i oczekuje na akceptację.", 'success')
            else:
                flash("Urlop został zarezerwowany.", 'success')
        else:
            flash("Wszystkie pola są wymagane.", 'error')
        return redirect(url_for('leaves'))
    
    if current_user.role == 'admin':
        all_emps = tracker.get_all_employees()
    else:
        # Normal user can only see themselves in dropdown
        all_emps = [(current_user.id, current_user.name)]
        
    all_leaves = tracker.get_all_leaves()
    # If not admin, maybe filter leaves list to just their team or themselves? 
    # Let's show all for transparency or team only.
    if current_user.role != 'admin' and current_user.team_id:
        # Filter leaves by team
        team_emps = tracker.get_employees_by_team(current_user.team_id)
        team_names = {t[1] for t in team_emps}
        all_leaves = [l for l in all_leaves if l[1] in team_names]
        
    return render_template('leaves.html', employees=all_emps, leaves=all_leaves)

@app.route('/leaves/edit/<int:leave_id>', methods=['GET', 'POST'])
@login_required
def edit_leave(leave_id):
    leave = tracker.get_leave_by_id(leave_id)
    if not leave:
        flash("Urlop nie znaleziony.", 'error')
        return redirect(url_for('leaves'))
        
    if current_user.role != 'admin' and str(leave[1]) != str(current_user.id):
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('leaves'))
    
    if request.method == 'POST':
        emp_id = request.form.get('employee_id')
        start = request.form.get('start_date')
        end = request.form.get('end_date')
        reason = request.form.get('reason')
        
        if emp_id and start and end and reason:
            tracker.update_leave(leave_id, emp_id, start, end, reason)
            flash("Wpis o urlopie został zaktualizowany.", 'success')
            return redirect(url_for('leaves'))
        else:
            flash("Wszystkie pola są wymagane.", 'error')
            
    if current_user.role == 'admin':
        all_emps = tracker.get_all_employees()
    else:
        all_emps = [(current_user.id, current_user.name)]
        
    return render_template('edit_leave.html', leave=leave, employees=all_emps)

@app.route('/leaves/delete/<int:leave_id>', methods=['POST'])
@login_required
def delete_leave(leave_id):
    leave = tracker.get_leave_by_id(leave_id)
    if leave and (current_user.role == 'admin' or str(leave[1]) == str(current_user.id)):
        tracker.delete_leave(leave_id)
        flash("Wpis o urlopie został usunięty.", 'success')
    else:
        flash("Brak uprawnień.", 'error')
    return redirect(url_for('leaves'))

@app.route('/leave/approve/<int:leave_id>', methods=['POST'])
@login_required
def approve_leave(leave_id):
    if current_user.role != 'admin':
        flash("Brak uprawnień.", 'error')
        return redirect(request.referrer or url_for('dashboard'))
        
    tracker.approve_leave(leave_id)
    flash("Wniosek urlopowy został zatwierdzony.", 'success')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/leave/decline/<int:leave_id>', methods=['POST'])
@login_required
def decline_leave(leave_id):
    if current_user.role != 'admin':
        flash("Brak uprawnień.", 'error')
        return redirect(request.referrer or url_for('dashboard'))
        
    comment = request.form.get('manager_comment', 'Odrzucono bez komentarza')
    tracker.decline_leave(leave_id, comment)
    flash("Wniosek urlopowy został odrzucony.", 'success')
    return redirect(request.referrer or url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)
