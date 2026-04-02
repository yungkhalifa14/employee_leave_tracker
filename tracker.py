from db import get_connection
from datetime import datetime, timedelta
import secrets
import sqlite3
import collections

class LeaveTracker:
    # --- USER MANAGEMENT ---

    def add_user(self, name, username, password_hash, role='employee', leave_limit=26, team_id=None, email=None):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (name, username, password_hash, role, leave_limit, team_id, email)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, username, password_hash, role, leave_limit, team_id, email))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_user_by_username(self, username):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, username, password_hash, role, leave_limit, team_id, email
            FROM users WHERE username = ?
        ''', (username,))
        user = cursor.fetchone()
        conn.close()
        return user

    def get_user_by_id(self, user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, username, password_hash, role, leave_limit, team_id, email
            FROM users WHERE id = ?
        ''', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user

    def update_user(self, user_id, name, leave_limit, role=None, team_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        query = 'UPDATE users SET name = ?, leave_limit = ?'
        params = [name, leave_limit]
        if role:
            query += ', role = ?'
            params.append(role)
        if team_id is not None:
            query += ', team_id = ?'
            params.append(team_id if team_id != -1 else None)
        
        query += ' WHERE id = ?'
        params.append(user_id)
        
        cursor.execute(query, tuple(params))
        conn.commit()
        conn.close()

    def delete_user(self, user_id):
        conn = get_connection()
        cursor = conn.cursor()
        # Leaves will be deleted via CASCADE in schema (if supported) 
        # but let's be explicit for safety or if foreign keys aren't enabled.
        cursor.execute('DELETE FROM leaves WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()

    # --- TEAM / INVITE MANAGEMENT ---

    def add_team(self, name, manager_id):
        conn = get_connection()
        cursor = conn.cursor()
        token = secrets.token_urlsafe(16)
        try:
            cursor.execute('INSERT INTO teams (name, manager_id, join_token) VALUES (?, ?, ?)', (name, manager_id, token))
            team_id = cursor.lastrowid
            conn.commit()
            return team_id
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def get_all_teams(self, manager_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        if manager_id:
            cursor.execute('SELECT id, name, manager_id, join_token FROM teams WHERE manager_id = ? ORDER BY name', (manager_id,))
        else:
            cursor.execute('SELECT id, name, manager_id, join_token FROM teams ORDER BY name')
        teams = cursor.fetchall()
        conn.close()
        return teams

    def get_team_by_join_token(self, token):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, manager_id FROM teams WHERE join_token = ?', (token,))
        team = cursor.fetchone()
        conn.close()
        return team

    def regenerate_team_token(self, team_id, manager_id):
        conn = get_connection()
        cursor = conn.cursor()
        new_token = secrets.token_urlsafe(16)
        cursor.execute('UPDATE teams SET join_token = ? WHERE id = ? AND manager_id = ?', (new_token, team_id, manager_id))
        conn.commit()
        conn.close()
        return new_token

    def create_invite(self, name, team_id, leave_limit=26):
        """ Creates a placeholder user with an invite token """
        conn = get_connection()
        cursor = conn.cursor()
        token = secrets.token_urlsafe(16)
        try:
            # We use a dummy unique username or keep it null if nullable (schema requires NOT NULL)
            # Actually schema says username NOT NULL. Let's use token as temporary username.
            temp_username = f"invite_{token[:8]}"
            cursor.execute('''
                INSERT INTO users (name, username, password_hash, role, leave_limit, team_id, invite_token)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, temp_username, 'PENDING', 'employee', leave_limit, team_id, token))
            conn.commit()
            return token
        except sqlite3.Error:
            return None
        finally:
            conn.close()

    def get_user_by_token(self, token):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE invite_token = ?', (token,))
        user = cursor.fetchone()
        conn.close()
        return user

    def claim_invite(self, token, username, password_hash, email=None):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Update user with token (which is their current username/tag)
            cursor.execute('''
                UPDATE users 
                SET username = ?, password_hash = ?, invite_token = NULL, email = ?
                WHERE invite_token = ?
            ''', (username, password_hash, email, token))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    # --- LEAVE MANAGEMENT ---

    def add_leave(self, user_id, start_date, end_date, reason, status='pending'):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO leaves (user_id, start_date, end_date, reason, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, start_date, end_date, reason, status))
        leave_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return leave_id

    def get_leave_by_id(self, leave_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.id, l.user_id, l.start_date, l.end_date, l.reason, l.status, l.manager_comment, u.name
            FROM leaves l
            JOIN users u ON l.user_id = u.id
            WHERE l.id = ?
        ''', (leave_id,))
        leave = cursor.fetchone()
        conn.close()
        return leave

    def update_leave(self, leave_id, start_date, end_date, reason):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE leaves SET start_date = ?, end_date = ?, reason = ?
            WHERE id = ?
        ''', (start_date, end_date, reason, leave_id))
        conn.commit()
        conn.close()

    def delete_leave(self, leave_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM leaves WHERE id = ?', (leave_id,))
        conn.commit()
        conn.close()

    def approve_leave(self, leave_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE leaves SET status = 'approved', manager_comment = NULL WHERE id = ?", (leave_id,))
        conn.commit()
        conn.close()

    def decline_leave(self, leave_id, comment):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE leaves SET status = 'declined', manager_comment = ? WHERE id = ?", (comment, leave_id))
        conn.commit()
        conn.close()

    def get_all_leaves(self, team_id=None, user_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        query = '''
            SELECT l.id, u.name, l.start_date, l.end_date, l.reason, l.status, l.manager_comment, l.user_id
            FROM leaves l
            JOIN users u ON l.user_id = u.id
        '''
        params = []
        if user_id:
            query += " WHERE l.user_id = ?"
            params.append(user_id)
        elif team_id:
            query += " WHERE u.team_id = ?"
            params.append(team_id)
            
        query += " ORDER BY l.start_date DESC"
        cursor.execute(query, tuple(params))
        leaves = cursor.fetchall()
        conn.close()
        return leaves

    def get_pending_leaves(self, team_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        query = '''
            SELECT l.id, u.name, l.start_date, l.end_date, l.reason 
            FROM leaves l
            JOIN users u ON l.user_id = u.id
            WHERE l.status = 'pending'
        '''
        params = []
        if team_id:
            query += " AND u.team_id = ?"
            params.append(team_id)
            
        query += " ORDER BY l.start_date ASC"
        cursor.execute(query, tuple(params))
        leaves = cursor.fetchall()
        conn.close()
        return leaves

    # --- HOLIDAYS & CALCULATIONS ---

    def add_holiday(self, date_str, name):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO holidays (date, name) VALUES (?, ?)', (date_str, name))
        conn.commit()
        conn.close()

    def prefill_polish_holidays(self, start_year=None, end_year=None):
        try:
            import holidays
        except ImportError:
            return False

        if start_year is None:
            start_year = datetime.now().year
        if end_year is None:
            # The prompt requested for 2026 and future years (let's say 5 years ahead)
            end_year = start_year + 5

        pl_holidays = holidays.Poland(years=range(start_year, end_year + 1))
        
        conn = get_connection()
        cursor = conn.cursor()
        for dt, name in pl_holidays.items():
            date_str = dt.strftime('%Y-%m-%d')
            cursor.execute('INSERT OR IGNORE INTO holidays (date, name) VALUES (?, ?)', (date_str, name))
        conn.commit()
        conn.close()
        return True

    def update_user_password(self, user_id, hashed_pw):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (hashed_pw, user_id))
        conn.commit()
        conn.close()
        return True

    def get_user_by_email(self, email):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()
        return user

    def set_reset_token(self, user_id, token, expiry_mins=60):
        expiry = (datetime.now() + timedelta(minutes=expiry_mins)).strftime('%Y-%m-%d %H:%M:%S')
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET reset_token = ?, reset_token_expiry = ? WHERE id = ?', (token, expiry, user_id))
        conn.commit()
        conn.close()

    def verify_reset_token(self, token):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, reset_token_expiry FROM users 
            WHERE reset_token = ? AND reset_token_expiry > ?
        ''', (token, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def clear_reset_token(self, user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET reset_token = NULL, reset_token_expiry = NULL WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()

    def get_holidays_set(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT date FROM holidays')
        holidays = {row[0] for row in cursor.fetchall()}
        conn.close()
        return holidays

    def calculate_used_days(self, start_date_str, end_date_str, holidays_set):
        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        end = datetime.strptime(end_date_str, "%Y-%m-%d")
        days = 0
        curr = start
        while curr <= end:
            if curr.weekday() < 5: # Mon-Fri
                d_str = curr.strftime("%Y-%m-%d")
                if d_str not in holidays_set:
                    days += 1
            curr += timedelta(days=1)
        return days

    def get_users_with_balance(self, team_id=None):
        """ Returns list of dicts: id, name, leave_limit, used_days, remaining_days, role, team_name """
        conn = get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT u.id, u.name, u.leave_limit, t.name, u.role, u.invite_token, u.team_id, u.email
            FROM users u
            LEFT JOIN teams t ON u.team_id = t.id
        '''
        params = []
        if team_id:
            query += " WHERE u.team_id = ?"
            params.append(team_id)
            
        cursor.execute(query, tuple(params))
        users_list = cursor.fetchall()
        
        current_year = datetime.now().year
        start_of_year = f"{current_year}-01-01"
        end_of_year = f"{current_year}-12-31"
        
        cursor.execute('''
            SELECT user_id, start_date, end_date 
            FROM leaves 
            WHERE status = 'approved' AND end_date >= ? AND start_date <= ?
        ''', (start_of_year, end_of_year))
        all_leaves = cursor.fetchall()
        conn.close()
        
        holidays_set = self.get_holidays_set()
        user_leaves = collections.defaultdict(list)
        for u_id, start, end in all_leaves:
            user_leaves[u_id].append((start, end))
            
        result = []
        for u_id, name, limit, team_name, role, invite_token, t_id, email in users_list:
            if role == 'admin' or role == 'manager':
                # Managers/Admins don't typically track leave balance in this app
                # but we'll include them with 0 used for now.
                used = 0
            else:
                used = 0
                if u_id in user_leaves:
                    for start, end in user_leaves[u_id]:
                        s = max(start, start_of_year)
                        e = min(end, end_of_year)
                        used += self.calculate_used_days(s, e, holidays_set)
            
            remaining = (limit or 0) - used
            result.append({
                'id': u_id,
                'name': name,
                'team': team_name or 'Brak zespołu',
                'team_id': t_id,
                'leave_limit': limit,
                'used_days': used,
                'remaining_days': remaining,
                'role': role,
                'invite_token': invite_token,
                'email': email
            })
        return result

    def get_monthly_data(self, start_date, end_date, team_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        data = {}
        
        # Holidays
        cursor.execute('SELECT date, name FROM holidays WHERE date BETWEEN ? AND ?', (start_date, end_date))
        for d, n in cursor.fetchall():
            data[d] = {'holiday': n, 'absentees': []}

        # Leaves
        query = '''
            SELECT l.id, l.start_date, l.end_date, u.name, l.reason, l.status 
            FROM leaves l
            JOIN users u ON l.user_id = u.id
            WHERE l.start_date <= ? AND l.end_date >= ? AND l.status != 'declined'
        '''
        params = [end_date, start_date]
        if team_id:
            query += " AND u.team_id = ?"
            params.append(team_id)
            
        cursor.execute(query, tuple(params))
        leaves = cursor.fetchall()
        conn.close()

        fmt = '%Y-%m-%d'
        r_start = datetime.strptime(start_date, fmt)
        r_end = datetime.strptime(end_date, fmt)

        for l_id, l_start, l_end, name, reason, status in leaves:
            s = datetime.strptime(l_start, fmt)
            e = datetime.strptime(l_end, fmt)
            curr = max(s, r_start)
            end = min(e, r_end)
            while curr <= end:
                d_str = curr.strftime(fmt)
                if d_str not in data: data[d_str] = {'holiday': None, 'absentees': []}
                data[d_str]['absentees'].append({
                    'id': l_id, 'name': name, 'reason': reason, 'status': status
                })
                curr += timedelta(days=1)
        return data
