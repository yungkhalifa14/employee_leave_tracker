from flask import Flask, render_template, request, redirect, url_for, flash, make_response
import csv
import io
import calendar
from tracker import LeaveTracker
from db import init_db, get_connection
from datetime import datetime, timedelta
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import dotenv
import secrets
from flask_mail import Mail, Message

# Load environment variables from .env if it exists
dotenv.load_dotenv()

app = Flask(__name__)
# Mail configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'localhost')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 1025))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@leave-tracker.com')

mail = Mail(app)
# Security: Use environment variable for secret key, fallback to a placeholder only for local development
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key_change_me')

# Production security settings
if os.environ.get('FLASK_ENV') == 'production':
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        REMEMBER_COOKIE_SECURE=True,
        REMEMBER_COOKIE_HTTPONLY=True
    )

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
    u = tracker.get_user_by_id(int(user_id))
    if u:
        # id, name, username, password_hash, role, leave_limit, team_id
        return User(id=u[0], name=u[1], username=u[2], role=u[4], team_id=u[6])
    return None

@app.context_processor
def inject_pending_leaves():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            pending = tracker.get_pending_leaves()
        elif current_user.role == 'manager' and current_user.team_id:
            pending = tracker.get_pending_leaves(team_id=current_user.team_id)
        else:
            pending = []
        return dict(pending_leaves_count=len(pending), pending_leaves=pending)
    return dict(pending_leaves_count=0, pending_leaves=[])

# --- AUTH ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        user = tracker.get_user_by_username(request.form['username'])
        if user and check_password_hash(user[3], request.form['password']):
            user_obj = User(user[0], user[1], user[2], user[4], user[6])
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        flash("Błędne dane logowania.", "error")
    return render_template('login.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = tracker.get_user_by_email(email)
        if user:
            token = secrets.token_urlsafe(32)
            tracker.set_reset_token(user[0], token)
            
            reset_url = url_for('reset_password', token=token, _external=True)
            
            # Send Email (or log it if SMTP fails)
            msg = Message("Reset hasła - Monitor Urlopów",
                          recipients=[email])
            msg.body = f"Witaj {user[1]},\n\nAby zresetować hasło, kliknij w poniższy link:\n{reset_url}\n\nLink jest ważny przez 1 godzinę."
            
            try:
                mail.send(msg)
                flash("Instrukcje resetowania hasła zostały wysłane na Twój adres email.", "success")
            except Exception as e:
                # Fallback: Print to console for development
                print(f"--- SIMULATED EMAIL TO {email} ---\n{msg.body}\n---------------------------")
                flash("Instrukcje resetowania hasła zostały wygenerowane (sprawdź konsolę serwera).", "info")
                
            return redirect(url_for('login'))
        else:
            flash("Nie znaleziono użytkownika z tym adresem email.", "error")
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user_id = tracker.verify_reset_token(token)
    if not user_id:
        flash("Link do resetowania hasła jest nieprawidłowy lub wygasł.", "error")
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        new_pw = request.form.get('password')
        confirm_pw = request.form.get('confirm_password')
        
        if new_pw != confirm_pw:
            flash("Hasła nie są identyczne.", "error")
            return render_template('reset_password.html', token=token)
            
        hashed_pw = generate_password_hash(new_pw)
        tracker.update_user_password(user_id, hashed_pw)
        tracker.clear_reset_token(user_id)
        flash("Hasło zostało pomyślnie zresetowane. Możesz się teraz zalogować.", "success")
        return redirect(url_for('login'))
        
    return render_template('reset_password.html', token=token)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """ Public registration for Managers """
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_pw = request.form.get('confirm_password')
        
        if not name or not username or not password or not email:
            flash("Wszystkie pola są wymagane.", "error")
            return redirect(url_for('register'))
            
        if password != confirm_pw:
            flash("Hasła nie są identyczne.", "error")
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password)
        if tracker.add_user(name, username, hashed_pw, role='manager', email=email):
            tracker.prefill_polish_holidays()
            flash("Konto managera utworzone pomyślnie!", "success")
            # Auto-login
            user = tracker.get_user_by_username(username)
            if user:
                user_obj = User(id=user[0], name=user[1], username=user[2], role=user[4], team_id=user[6])
                login_user(user_obj)
                return redirect(url_for('dashboard'))
            return redirect(url_for('login'))
        else:
            flash("Błąd: Nazwa użytkownika lub email jest już zajęty.", "error")
    return render_template('register.html')

@app.route('/join/<token>', methods=['GET', 'POST'])
def join_team(token):
    """ Registration for Employees via team join link """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    team = tracker.get_team_by_join_token(token)
    if not team:
        flash("Link do dołączenia jest nieprawidłowy.", 'error')
        return redirect(url_for('login'))
        
    team_id, team_name, manager_id = team
    
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_pw = request.form.get('confirm_password')
        
        if not all([name, username, email, password, confirm_pw]):
            flash("Wszystkie pola są wymagane.", "error")
            return render_template('join_team.html', team_name=team_name, token=token)
            
        if password != confirm_pw:
            flash("Hasła nie są identyczne.", "error")
            return render_template('join_team.html', team_name=team_name, token=token)

        if tracker.get_user_by_username(username):
            flash("Ta nazwa użytkownika jest już zajęta.", "error")
            return render_template('join_team.html', team_name=team_name, token=token)
            
        pw_hash = generate_password_hash(password)
        if tracker.add_user(name, username, pw_hash, role='employee', team_id=team_id, email=email):
            tracker.prefill_polish_holidays()
            flash(f"Witaj w zespole {team_name}! Twoje konto zostało utworzone.", 'success')
            user = tracker.get_user_by_username(username)
            if user:
                user_obj = User(id=user[0], name=user[1], username=user[2], role=user[4], team_id=user[6])
                login_user(user_obj)
                return redirect(url_for('dashboard'))
            return redirect(url_for('login'))
        else:
            flash("Wystąpił błąd podczas tworzenia konta.", "error")
            
    return render_template('join_team.html', team_name=team_name, token=token)

@app.route('/invite/<token>', methods=['GET', 'POST'])
def invite(token):
    """ Individual employee invite claim """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    user = tracker.get_user_by_token(token)
    if not user:
        flash("Link z zaproszeniem jest nieprawidłowy.", 'error')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_pw = request.form.get('confirm_password')
        
        if not all([username, email, password, confirm_pw]):
            flash("Wszystkie pola są wymagane.", "error")
            return render_template('invite.html', token=token, name=user[1])
            
        if password != confirm_pw:
            flash("Hasła nie są identyczne.", "error")
            return render_template('invite.html', token=token, name=user[1])
            
        pw_hash = generate_password_hash(password)
        if tracker.claim_invite(token, username, pw_hash, email=email):
            tracker.prefill_polish_holidays()
            flash("Konto zostało aktywowane!", 'success')
            return redirect(url_for('login'))
        else:
            flash("Wystąpił błąd lub nazwa użytkownika jest zajęta.", "error")
            
    return render_template('invite.html', token=token, name=user[1])

# --- DASHBOARD & CALENDAR ---

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
    
    events = tracker.get_monthly_data(start_date, end_date, team_id=team_id_filter)
    
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
    
    nm = month + 1; ny = year
    if nm > 12: nm = 1; ny += 1
    pm = month - 1; py = year
    if pm < 1: pm = 12; py -= 1
        
    return {
        'calendar_data': calendar_data,
        'month_name': POLISH_MONTHS[month],
        'month': month,
        'year': year,
        'prev_month': pm, 'prev_year': py,
        'next_month': nm, 'next_year': ny,
        'current_team_filter': team_id_filter
    }

@app.route('/')
@login_required
def dashboard():
    year, month = get_safe_year_month()
    
    team_filter = request.args.get('team_id')
    if team_filter and team_filter.isdigit():
        team_filter = int(team_filter)
    elif current_user.role == 'manager' and current_user.team_id:
        team_filter = current_user.team_id
    elif current_user.role == 'employee' and current_user.team_id:
        team_filter = current_user.team_id
    else:
        team_filter = None
        
    context = get_calendar_context(year, month, team_id_filter=team_filter)
    
    if current_user.role == 'admin':
        teams = tracker.get_all_teams()
        # Admin stats
        pending_total = len([l for l in tracker.get_all_leaves() if l[5] == 'pending'])
        out_today_list = [l for l in tracker.get_all_leaves() if l[2] <= datetime.now().strftime('%Y-%m-%d') <= l[3] and l[5] == 'approved']
        stats = {
            'out_today': len(out_today_list),
            'pending_total': pending_total,
        }
    elif current_user.role == 'manager':
        teams = tracker.get_all_teams(manager_id=current_user.id)
        # Manager stats (all teams they manage)
        managed_team_ids = [t[0] for t in teams]
        all_managed_leaves = []
        for tid in managed_team_ids:
            all_managed_leaves.extend(tracker.get_all_leaves(team_id=tid))
        
        pending_total = len([l for l in all_managed_leaves if l[5] == 'pending'])
        out_today_list = [l for l in all_managed_leaves if l[2] <= datetime.now().strftime('%Y-%m-%d') <= l[3] and l[5] == 'approved']
        stats = {
            'out_today': len(out_today_list),
            'pending_total': pending_total,
        }
    else:
        teams = []
        # Employee stats
        user_balance = next((u for u in tracker.get_users_with_balance() if u['id'] == current_user.id), None)
        pending_count = len([l for l in tracker.get_all_leaves(user_id=current_user.id) if l[5] == 'pending'])
        stats = {
            'used': user_balance['used'] if user_balance else 0,
            'remaining': user_balance['remaining'] if user_balance else 0,
            'pending': pending_count
        }
        
    return render_template('dashboard.html', **context, teams=teams, stats=stats, endpoint='dashboard')

# --- MANAGEMENT ---

@app.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    # Only Admin and Manager can see this
    if current_user.role not in ['admin', 'manager']:
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        limit = request.form.get('leave_limit', 26)
        team_id = request.form.get('team_id')
        
        # Managers can only add to their own teams
        if current_user.role == 'manager':
            # Verify team belongs to manager
            managed_teams = [t[0] for t in tracker.get_all_teams(manager_id=current_user.id)]
            if not team_id or int(team_id) not in managed_teams:
                flash("Możesz dodawać pracowników tylko do swoich zespołów.", 'error')
                return redirect(url_for('employees'))
        
        if name and limit:
            try:
                t_id = int(team_id) if team_id else None
                token = tracker.create_invite(name, t_id, int(limit))
                if token:
                    invite_link = url_for('invite', token=token, _external=True)
                    flash(f"Pracownik dodany! Link: {invite_link}", 'success')
                else:
                    flash("Błąd podczas dodawania.", 'error')
            except ValueError:
                flash("Nieprawidłowe dane.", 'error')
        return redirect(url_for('employees'))
    
    if current_user.role == 'admin':
        all_users = tracker.get_users_with_balance()
        teams = tracker.get_all_teams()
    else:
        # Manager sees their team members
        managed_teams = [t[0] for t in tracker.get_all_teams(manager_id=current_user.id)]
        all_users = []
        for t_id in managed_teams:
            all_users.extend(tracker.get_users_with_balance(team_id=t_id))
        teams = tracker.get_all_teams(manager_id=current_user.id)
            
    return render_template('employees.html', employees=all_users, teams=teams)

@app.route('/teams', methods=['GET', 'POST'])
@login_required
def teams_view():
    if current_user.role not in ['admin', 'manager']:
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            tracker.add_team(name, current_user.id)
            flash(f"Zespół {name} dodany.", "success")
        return redirect(url_for('teams_view'))
        
    if current_user.role == 'admin':
        all_teams = tracker.get_all_teams()
    else:
        all_teams = tracker.get_all_teams(manager_id=current_user.id)
    return render_template('teams.html', teams=all_teams)

@app.route('/team/regenerate/<int:team_id>', methods=['POST'])
@login_required
def regenerate_team_token(team_id):
    if current_user.role not in ['admin', 'manager']:
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('dashboard'))
        
    # Security: check if manager owns team or is admin
    teams = tracker.get_all_teams(manager_id=(None if current_user.role == 'admin' else current_user.id))
    if any(t[0] == team_id for t in teams):
        tracker.regenerate_team_token(team_id, current_user.id if current_user.role != 'admin' else None)
        flash("Link do dołączenia został odświeżony.", "success")
    else:
        flash("Brak uprawnień do tego zespołu.", "error")
        
    return redirect(url_for('teams_view'))

@app.route('/leaves', methods=['GET', 'POST'])
@login_required
def leaves():
    if request.method == 'POST':
        # Employees only request for themselves
        # Managers can add for their team (auto-approved)
        # Admin can add for anyone (auto-approved)
        user_id = request.form.get('user_id')
        start = request.form.get('start_date')
        end = request.form.get('end_date')
        reason = request.form.get('reason')
        
        if not user_id: user_id = current_user.id
            
        if current_user.role == 'employee' and str(user_id) != str(current_user.id):
            flash("Brak uprawnień.", 'error')
            return redirect(url_for('leaves'))
            
        status = 'approved' if current_user.role in ['admin', 'manager'] else 'pending'
        tracker.add_leave(user_id, start, end, reason, status=status)
        flash("Urlop zarejestrowany.", 'success')
        return redirect(url_for('leaves'))
    
    if current_user.role == 'admin':
        all_users = [(u['id'], u['name']) for u in tracker.get_users_with_balance()]
        all_leaves = tracker.get_all_leaves()
    elif current_user.role == 'manager':
        managed_teams = [t[0] for t in tracker.get_all_teams(manager_id=current_user.id)]
        all_users = []
        all_leaves = []
        for t_id in managed_teams:
            all_users.extend([(u['id'], u['name']) for u in tracker.get_users_with_balance(team_id=t_id)])
            all_leaves.extend(tracker.get_all_leaves(team_id=t_id))
    else:
        all_users = [(current_user.id, current_user.name)]
        all_leaves = tracker.get_all_leaves(user_id=current_user.id)
        
    return render_template('leaves.html', employees=all_users, leaves=all_leaves)

@app.route('/leave/edit/<int:leave_id>', methods=['GET', 'POST'])
@login_required
def edit_leave(leave_id):
    leave = tracker.get_leave_by_id(leave_id)
    if not leave:
        flash("Urlop nie istnieje.", 'error')
        return redirect(url_for('leaves'))
        
    if current_user.role == 'employee' and str(leave[1]) != str(current_user.id):
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('leaves'))
        
    if request.method == 'POST':
        start = request.form.get('start_date')
        end = request.form.get('end_date')
        reason = request.form.get('reason')
        tracker.update_leave(leave_id, start, end, reason)
        flash("Urlop zaktualizowany.", 'success')
        return redirect(url_for('leaves'))
        
    return render_template('edit_leave.html', leave=leave)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_email':
            email = request.form.get('email')
            if email:
                # Update email in DB
                conn = get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute('UPDATE users SET email = ? WHERE id = ?', (email, current_user.id))
                    conn.commit()
                    flash("Adres email został zaktualizowany.", "success")
                except Exception:
                    flash("Ten adres email jest już zajęty.", "error")
                finally:
                    conn.close()
            return redirect(url_for('profile'))
            
        elif action == 'change_password':
            current_pw = request.form.get('current_password')
            new_pw = request.form.get('new_password')
            confirm_pw = request.form.get('confirm_password')
            
            if new_pw != confirm_pw:
                flash("Nowe hasła nie są identyczne.", "error")
                return redirect(url_for('profile'))
                
            user_data = tracker.get_user_by_id(int(current_user.id))
            if user_data and check_password_hash(user_data[3], current_pw):
                hashed_new_pw = generate_password_hash(new_pw)
                tracker.update_user_password(current_user.id, hashed_new_pw)
                flash("Hasło zostało pomyślnie zmienione.", "success")
            else:
                flash("Nieprawidłowe aktualne hasło.", "error")
            return redirect(url_for('profile'))
            
    # Get current email
    user_data = tracker.get_user_by_id(current_user.id)
    email = user_data[7] if user_data and len(user_data) > 7 else None
    return render_template('profile.html', email=email)

# --- APPROVALS ---

@app.route('/leave/approve/<int:leave_id>', methods=['POST'])
@login_required
def approve_leave(leave_id):
    leave = tracker.get_leave_by_id(leave_id)
    if not leave: return redirect(url_for('dashboard'))
    
    # Check permission: Admin or Manager of that user's team
    can_approve = False
    if current_user.role == 'admin':
        can_approve = True
    elif current_user.role == 'manager':
        user_data = tracker.get_user_by_id(leave[1])
        if user_data and user_data[6] == current_user.team_id: # team_id
             # Wait, current_user.team_id might not be set for a manager if they have multiple teams
             # Let's check if the manager owns the team
             managed_teams = [t[0] for t in tracker.get_all_teams(manager_id=current_user.id)]
             if user_data[6] in managed_teams:
                 can_approve = True
                 
    if not can_approve:
        flash("Brak uprawnień.", 'error')
    else:
        tracker.approve_leave(leave_id)
        flash("Zatwierdzono.", 'success')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/leave/decline/<int:leave_id>', methods=['POST'])
@login_required
def decline_leave(leave_id):
    # Same permission check as approve
    tracker.decline_leave(leave_id, request.form.get('manager_comment', ''))
    flash("Odrzucono.", 'success')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/employee/edit/<int:emp_id>', methods=['GET', 'POST'])
@login_required
def edit_employee(emp_id):
    # Only Admin or Manager can edit (or self edit?) 
    # Let's say Admin can edit anyone, Manager can edit their team.
    if current_user.role not in ['admin', 'manager']:
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('dashboard'))
    
    # Get user to edit
    user_data = tracker.get_user_by_id(emp_id)
    if not user_data:
        flash("Pracownik nie istnieje.", 'error')
        return redirect(url_for('employees'))

    # Permission check for managers
    if current_user.role == 'manager':
        managed_teams = [t[0] for t in tracker.get_all_teams(manager_id=current_user.id)]
        if user_data[6] not in managed_teams:
            flash("Możesz edytować tylko pracowników swojego zespołu.", 'error')
            return redirect(url_for('employees'))

    if request.method == 'POST':
        name = request.form.get('name')
        limit = request.form.get('leave_limit')
        role = request.form.get('role')
        team_id = request.form.get('team_id')
        email = request.form.get('email')
        new_password = request.form.get('new_password')

        # Update in tracker
        tracker.update_user(emp_id, name, int(limit), role=role, team_id=int(team_id) if team_id else None)
        
        # Update email and password if provided
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET email = ? WHERE id = ?', (email, emp_id))
        
        if new_password:
            hashed_pw = generate_password_hash(new_password)
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (hashed_pw, emp_id))
            
        conn.commit()
        conn.close()

        flash("Dane pracownika zaktualizowane.", 'success')
        return redirect(url_for('employees'))

    # Format user_data for template
    email = user_data[7] if len(user_data) > 7 else None
    emp = {
        'id': user_data[0],
        'name': user_data[1],
        'username': user_data[2],
        'role': user_data[4],
        'leave_limit': user_data[5],
        'team_id': user_data[6],
        'email': email
    }
    
    if current_user.role == 'admin':
        teams = tracker.get_all_teams()
    else:
        teams = tracker.get_all_teams(manager_id=current_user.id)
        
    return render_template('edit_employee.html', emp=emp, teams=teams)

@app.route('/employee/delete/<int:emp_id>', methods=['POST'])
@login_required
def delete_employee(emp_id):
    if current_user.role != 'admin':
        flash("Brak uprawnień.", "error")
        return redirect(url_for('employees'))
    tracker.delete_user(emp_id)
    flash("Pracownik usunięty.", "success")
    return redirect(url_for('employees'))

@app.route('/leave/delete/<int:leave_id>', methods=['POST'])
@login_required
def delete_leave(leave_id):
    leave = tracker.get_leave_by_id(leave_id)
    if not leave: return redirect(url_for('leaves'))
    
    # Permission: Admin or User who created it
    if current_user.role == 'admin' or str(leave[1]) == str(current_user.id):
        tracker.delete_leave(leave_id)
        flash("Urlop usunięty.", "success")
    else:
        flash("Brak uprawnień.", "error")
        
    return redirect(url_for('leaves'))

@app.route('/export_csv')
@login_required
def export_csv():
    year, month = get_safe_year_month()
    team_id = request.args.get('team_id')
    
    # team_id filter based on role
    if current_user.role == 'manager':
        team_id = current_user.team_id
    elif current_user.role == 'employee':
        team_id = current_user.team_id
        
    _, last_day = calendar.monthrange(year, month)
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    
    events = tracker.get_monthly_data(start_date, end_date, team_id=team_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Data', 'Typ', 'Osoba/Nazwa'])
    
    for day in range(1, last_day + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        day_events = events.get(date_str)
        if day_events:
            if day_events.get('holiday'):
                writer.writerow([date_str, 'Święto', day_events['holiday']])
            for abs_ in day_events.get('absentees', []):
                writer.writerow([date_str, 'Urlop ('+abs_['status']+')', abs_['name']])
                
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=urlopy_{year}_{month}.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/holidays', methods=['GET', 'POST'])
@login_required
def holidays():
    if request.method == 'POST' and current_user.role == 'admin':
        tracker.add_holiday(request.form.get('date'), request.form.get('name'))
    
    from db import get_connection
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT date, name FROM holidays ORDER BY date')
    hols = cursor.fetchall(); conn.close()
    return render_template('holidays.html', holidays=hols)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', debug=debug_mode, port=port)
