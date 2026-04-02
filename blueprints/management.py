from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from db import get_connection

from extensions import tracker

management_bp = Blueprint('management', __name__)

@management_bp.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    if current_user.role not in ['admin', 'manager']:
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        limit = request.form.get('leave_limit', 26)
        team_id = request.form.get('team_id')
        
        if current_user.role == 'manager':
            managed_teams = [t[0] for t in tracker.get_all_teams(manager_id=current_user.id)]
            if not team_id or int(team_id) not in managed_teams:
                flash("Możesz dodawać pracowników tylko do swoich zespołów.", 'error')
                return redirect(url_for('management.employees'))
        
        if name and limit:
            try:
                t_id = int(team_id) if team_id else None
                token = tracker.create_invite(name, t_id, int(limit))
                if token:
                    invite_link = url_for('auth.invite', token=token, _external=True)
                    flash(f"Pracownik dodany! Link: {invite_link}", 'success')
                else:
                    flash("Błąd podczas dodawania.", 'error')
            except ValueError:
                flash("Nieprawidłowe dane.", 'error')
        return redirect(url_for('management.employees'))
    
    if current_user.role == 'admin':
        all_users = tracker.get_users_with_balance()
        teams = tracker.get_all_teams()
    else:
        managed_teams = [t[0] for t in tracker.get_all_teams(manager_id=current_user.id)]
        all_users = []
        for t_id in managed_teams:
            all_users.extend(tracker.get_users_with_balance(team_id=t_id))
        teams = tracker.get_all_teams(manager_id=current_user.id)
            
    return render_template('employees.html', employees=all_users, teams=teams)

@management_bp.route('/teams', methods=['GET', 'POST'])
@login_required
def teams_view():
    if current_user.role not in ['admin', 'manager']:
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('dashboard.dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            tracker.add_team(name, current_user.id)
            flash(f"Zespół {name} dodany.", "success")
        return redirect(url_for('management.teams_view'))
        
    if current_user.role == 'admin':
        all_teams = tracker.get_all_teams()
    else:
        all_teams = tracker.get_all_teams(manager_id=current_user.id)
    return render_template('teams.html', teams=all_teams)

@management_bp.route('/team/regenerate/<int:team_id>', methods=['POST'])
@login_required
def regenerate_team_token(team_id):
    if current_user.role not in ['admin', 'manager']:
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('dashboard.dashboard'))
        
    teams = tracker.get_all_teams(manager_id=(None if current_user.role == 'admin' else current_user.id))
    if any(t[0] == team_id for t in teams):
        tracker.regenerate_team_token(team_id, current_user.id if current_user.role != 'admin' else None)
        flash("Link do dołączenia został odświeżony.", "success")
    else:
        flash("Brak uprawnień do tego zespołu.", "error")
        
    return redirect(url_for('management.teams_view'))

@management_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_email':
            email = request.form.get('email')
            if email:
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
            return redirect(url_for('management.profile'))
            
        elif action == 'change_password':
            current_pw = request.form.get('current_password')
            new_pw = request.form.get('new_password')
            confirm_pw = request.form.get('confirm_password')
            
            if new_pw != confirm_pw:
                flash("Nowe hasła nie są identyczne.", "error")
                return redirect(url_for('management.profile'))
                
            user_data = tracker.get_user_by_id(int(current_user.id))
            if user_data and check_password_hash(user_data[3], current_pw):
                hashed_new_pw = generate_password_hash(new_pw)
                tracker.update_user_password(current_user.id, hashed_new_pw)
                flash("Hasło zostało pomyślnie zmienione.", "success")
            else:
                flash("Nieprawidłowe aktualne hasło.", "error")
            return redirect(url_for('management.profile'))
            
    user_data = tracker.get_user_by_id(current_user.id)
    email = user_data[7] if user_data and len(user_data) > 7 else None
    return render_template('profile.html', email=email)

@management_bp.route('/employee/edit/<int:emp_id>', methods=['GET', 'POST'])
@login_required
def edit_employee(emp_id):
    if current_user.role not in ['admin', 'manager']:
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('dashboard.dashboard'))
    
    user_data = tracker.get_user_by_id(emp_id)
    if not user_data:
        flash("Pracownik nie istnieje.", 'error')
        return redirect(url_for('management.employees'))

    if current_user.role == 'manager':
        managed_teams = [t[0] for t in tracker.get_all_teams(manager_id=current_user.id)]
        if user_data[6] not in managed_teams:
            flash("Możesz edytować tylko pracowników swojego zespołu.", 'error')
            return redirect(url_for('management.employees'))

    if request.method == 'POST':
        name = request.form.get('name')
        limit = request.form.get('leave_limit')
        role = request.form.get('role')
        team_id = request.form.get('team_id')
        email = request.form.get('email')
        new_password = request.form.get('new_password')

        tracker.update_user(emp_id, name, int(limit), role=role, team_id=int(team_id) if team_id else None)
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET email = ? WHERE id = ?', (email, emp_id))
        
        if new_password:
            hashed_pw = generate_password_hash(new_password)
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (hashed_pw, emp_id))
            
        conn.commit()
        conn.close()

        flash("Dane pracownika zaktualizowane.", 'success')
        return redirect(url_for('management.employees'))

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

@management_bp.route('/employee/delete/<int:emp_id>', methods=['POST'])
@login_required
def delete_employee(emp_id):
    if current_user.role != 'admin':
        flash("Brak uprawnień.", "error")
        return redirect(url_for('management.employees'))
    tracker.delete_user(emp_id)
    flash("Pracownik usunięty.", "success")
    return redirect(url_for('management.employees'))

@management_bp.route('/holidays', methods=['GET', 'POST'])
@login_required
def holidays():
    if request.method == 'POST' and current_user.role == 'admin':
        tracker.add_holiday(request.form.get('date'), request.form.get('name'))
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT date, name FROM holidays ORDER BY date')
    hols = cursor.fetchall()
    conn.close()
    return render_template('holidays.html', holidays=hols)
