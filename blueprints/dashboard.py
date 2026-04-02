from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import calendar
import io
import csv

from extensions import tracker

dashboard_bp = Blueprint('dashboard', __name__)

POLISH_MONTHS = {
    1: "Styczeń", 2: "Luty", 3: "Marzec", 4: "Kwiecień",
    5: "Maj", 6: "Czerwiec", 7: "Lipiec", 8: "Sierpień",
    9: "Wrzesień", 10: "Październik", 11: "Listopad", 12: "Grudzień"
}

@dashboard_bp.app_context_processor
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

@dashboard_bp.route('/')
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
        pending_total = len([l for l in tracker.get_all_leaves() if l[5] == 'pending'])
        out_today_list = [l for l in tracker.get_all_leaves() if l[2] <= datetime.now().strftime('%Y-%m-%d') <= l[3] and l[5] == 'approved']
        stats = {
            'out_today': len(out_today_list),
            'pending_total': pending_total,
        }
    elif current_user.role == 'manager':
        teams = tracker.get_all_teams(manager_id=current_user.id)
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
        user_balance = next((u for u in tracker.get_users_with_balance() if u['id'] == current_user.id), None)
        pending_count = len([l for l in tracker.get_all_leaves(user_id=current_user.id) if l[5] == 'pending'])
        stats = {
            'used': user_balance['used_days'] if user_balance else 0,
            'remaining': user_balance['remaining_days'] if user_balance else 0,
            'pending': pending_count
        }
        
    return render_template('dashboard.html', **context, teams=teams, stats=stats, endpoint='dashboard.dashboard')


@dashboard_bp.route('/leaves', methods=['GET', 'POST'])
@login_required
def leaves():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        start = request.form.get('start_date')
        end = request.form.get('end_date')
        reason = request.form.get('reason')
        
        if not user_id: user_id = current_user.id
            
        if current_user.role == 'employee' and str(user_id) != str(current_user.id):
            flash("Brak uprawnień.", 'error')
            return redirect(url_for('dashboard.leaves'))
            
        status = 'approved' if current_user.role in ['admin', 'manager'] else 'pending'
        tracker.add_leave(user_id, start, end, reason, status=status)
        flash("Urlop zarejestrowany.", 'success')
        return redirect(url_for('dashboard.leaves'))
    
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


@dashboard_bp.route('/leave/edit/<int:leave_id>', methods=['GET', 'POST'])
@login_required
def edit_leave(leave_id):
    leave = tracker.get_leave_by_id(leave_id)
    if not leave:
        flash("Urlop nie istnieje.", 'error')
        return redirect(url_for('dashboard.leaves'))
        
    if current_user.role == 'employee' and str(leave[1]) != str(current_user.id):
        flash("Brak uprawnień.", 'error')
        return redirect(url_for('dashboard.leaves'))
        
    if request.method == 'POST':
        start = request.form.get('start_date')
        end = request.form.get('end_date')
        reason = request.form.get('reason')
        tracker.update_leave(leave_id, start, end, reason)
        flash("Urlop zaktualizowany.", 'success')
        return redirect(url_for('dashboard.leaves'))
        
    return render_template('edit_leave.html', leave=leave)


@dashboard_bp.route('/leave/delete/<int:leave_id>', methods=['POST'])
@login_required
def delete_leave(leave_id):
    leave = tracker.get_leave_by_id(leave_id)
    if not leave: return redirect(url_for('dashboard.leaves'))
    
    if current_user.role == 'admin' or str(leave[1]) == str(current_user.id):
        tracker.delete_leave(leave_id)
        flash("Urlop usunięty.", "success")
    else:
        flash("Brak uprawnień.", "error")
        
    return redirect(url_for('dashboard.leaves'))


@dashboard_bp.route('/leave/approve/<int:leave_id>', methods=['POST'])
@login_required
def approve_leave(leave_id):
    leave = tracker.get_leave_by_id(leave_id)
    if not leave:
        return jsonify({"status": "error", "message": "Urlop nie istnieje."}), 404
    
    can_approve = False
    if current_user.role == 'admin':
        can_approve = True
    elif current_user.role == 'manager':
        user_data = tracker.get_user_by_id(leave[1])
        if user_data:
             managed_teams = [t[0] for t in tracker.get_all_teams(manager_id=current_user.id)]
             if user_data[6] in managed_teams:
                 can_approve = True
                 
    if not can_approve:
        return jsonify({"status": "error", "message": "Brak uprawnień."}), 403
    else:
        tracker.approve_leave(leave_id)
        return jsonify({"status": "success", "message": "Urlop zatwierdzony."})


@dashboard_bp.route('/leave/decline/<int:leave_id>', methods=['POST'])
@login_required
def decline_leave(leave_id):
    leave = tracker.get_leave_by_id(leave_id)
    if not leave:
        return jsonify({"status": "error", "message": "Urlop nie istnieje."}), 404
    
    can_approve = False
    if current_user.role == 'admin':
        can_approve = True
    elif current_user.role == 'manager':
        user_data = tracker.get_user_by_id(leave[1])
        if user_data:
             managed_teams = [t[0] for t in tracker.get_all_teams(manager_id=current_user.id)]
             if user_data[6] in managed_teams:
                 can_approve = True
                 
    if not can_approve:
        return jsonify({"status": "error", "message": "Brak uprawnień."}), 403
    else:
        comment = ""
        if request.is_json:
            comment = request.json.get('manager_comment', '')
        else:
            comment = request.form.get('manager_comment', '')
            
        tracker.decline_leave(leave_id, comment)
        return jsonify({"status": "success", "message": "Urlop odrzucony."})


@dashboard_bp.route('/export_csv')
@login_required
def export_csv():
    year, month = get_safe_year_month()
    team_id = request.args.get('team_id')
    
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
