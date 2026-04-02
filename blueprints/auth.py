from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
import secrets

from extensions import tracker, mail
from models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
        
    if request.method == 'POST':
        user = tracker.get_user_by_username(request.form['username'])
        if user and check_password_hash(user[3], request.form['password']):
            user_obj = User(user[0], user[1], user[2], user[4], user[6])
            login_user(user_obj)
            return redirect(url_for('dashboard.dashboard'))
        flash("Błędne dane logowania.", "error")
    return render_template('login.html')

@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = tracker.get_user_by_email(email)
        if user:
            token = secrets.token_urlsafe(32)
            tracker.set_reset_token(user[0], token)
            
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            msg = Message("Reset hasła - Monitor Urlopów",
                          recipients=[email])
            msg.body = f"Witaj {user[1]},\n\nAby zresetować hasło, kliknij w poniższy link:\n{reset_url}\n\nLink jest ważny przez 1 godzinę."
            
            try:
                mail.send(msg)
                flash("Instrukcje resetowania hasła zostały wysłane na Twój adres email.", "success")
            except Exception as e:
                print(f"--- SIMULATED EMAIL TO {email} ---\n{msg.body}\n---------------------------")
                flash("Instrukcje resetowania hasła zostały wygenerowane (sprawdź konsolę serwera).", "info")
                
            return redirect(url_for('auth.login'))
        else:
            flash("Nie znaleziono użytkownika z tym adresem email.", "error")
    return render_template('forgot_password.html')

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user_id = tracker.verify_reset_token(token)
    if not user_id:
        flash("Link do resetowania hasła jest nieprawidłowy lub wygasł.", "error")
        return redirect(url_for('auth.forgot_password'))
        
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
        return redirect(url_for('auth.login'))
        
    return render_template('reset_password.html', token=token)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_pw = request.form.get('confirm_password')
        
        if not name or not username or not password or not email:
            flash("Wszystkie pola są wymagane.", "error")
            return redirect(url_for('auth.register'))
            
        if password != confirm_pw:
            flash("Hasła nie są identyczne.", "error")
            return redirect(url_for('auth.register'))
            
        hashed_pw = generate_password_hash(password)
        if tracker.add_user(name, username, hashed_pw, role='manager', email=email):
            tracker.prefill_polish_holidays()
            flash("Konto managera utworzone pomyślnie!", "success")
            user = tracker.get_user_by_username(username)
            if user:
                user_obj = User(id=user[0], name=user[1], username=user[2], role=user[4], team_id=user[6])
                login_user(user_obj)
                return redirect(url_for('dashboard.dashboard'))
            return redirect(url_for('auth.login'))
        else:
            flash("Błąd: Nazwa użytkownika lub email jest już zajęty.", "error")
    return render_template('register.html')

@auth_bp.route('/join/<token>', methods=['GET', 'POST'])
def join_team(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
        
    team = tracker.get_team_by_join_token(token)
    if not team:
        flash("Link do dołączenia jest nieprawidłowy.", 'error')
        return redirect(url_for('auth.login'))
        
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
                return redirect(url_for('dashboard.dashboard'))
            return redirect(url_for('auth.login'))
        else:
            flash("Wystąpił błąd podczas tworzenia konta.", "error")
            
    return render_template('join_team.html', team_name=team_name, token=token)

@auth_bp.route('/invite/<token>', methods=['GET', 'POST'])
def invite(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    
    user = tracker.get_user_by_token(token)
    if not user:
        flash("Link z zaproszeniem jest nieprawidłowy.", 'error')
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_pw = request.form.get('confirm_password')
        
        if not all([username, email, password, confirm_pw]):
            flash("Wszystkie pola są wymagane.", "error")
            return render_template('invite.html', token=token, employee=user)
            
        if password != confirm_pw:
            flash("Hasła nie są identyczne.", "error")
            return render_template('invite.html', token=token, employee=user)
            
        pw_hash = generate_password_hash(password)
        if tracker.claim_invite(token, username, pw_hash, email=email):
            tracker.prefill_polish_holidays()
            flash("Konto zostało aktywowane!", 'success')
            return redirect(url_for('auth.login'))
        else:
            flash("Wystąpił błąd lub nazwa użytkownika jest zajęta.", "error")
            
    return render_template('invite.html', token=token, employee=user)
