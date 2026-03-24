from db import get_connection
from datetime import datetime
import secrets

class LeaveTracker:
    def add_employee(self, name, leave_limit=26, username=None, password_hash=None, role='user', team_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        invite_token = None
        if not username and not password_hash:
            invite_token = secrets.token_urlsafe(16)
        try:
            cursor.execute('''
                INSERT INTO employees (name, leave_limit, username, password_hash, role, team_id, invite_token) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, leave_limit, username, password_hash, role, team_id, invite_token))
            emp_id = cursor.lastrowid
            conn.commit()
            return invite_token if invite_token else emp_id
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_employee_by_token(self, token):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM employees WHERE invite_token = ?', (token,))
        emp = cursor.fetchone()
        conn.close()
        return emp

    def claim_invite(self, token, username, password_hash):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE employees SET username = ?, password_hash = ?, invite_token = NULL WHERE invite_token = ?",
                          (username, password_hash, token))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_user_by_username(self, username):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, leave_limit, username, password_hash, role, team_id 
            FROM employees WHERE username = ?
        ''', (username,))
        user = cursor.fetchone()
        conn.close()
        return user

    def add_holiday(self, date_str, name):
        # date_str expected format: YYYY-MM-DD
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT OR REPLACE INTO holidays (date, name) VALUES (?, ?)', (date_str, name))
            conn.commit()
        except Exception as e:
            print(f"Error adding holiday: {e}")
        finally:
            conn.close()

    def add_leave(self, employee_id, start_date, end_date, reason, status='pending'):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO leaves (employee_id, start_date, end_date, reason, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (employee_id, start_date, end_date, reason, status))
        leave_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return leave_id

    def check_employee_status(self, employee_id, date_str):
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if it is a holiday
        cursor.execute('SELECT name FROM holidays WHERE date = ?', (date_str,))
        holiday = cursor.fetchone()
        if holiday:
            conn.close()
            return f"Holiday: {holiday[0]}"
        
        # Check if employee is on leave
        # Leave range is inclusive
        cursor.execute('''
            SELECT reason FROM leaves 
            WHERE employee_id = ? AND start_date <= ? AND end_date >= ?
        ''', (employee_id, date_str, date_str))
        leave = cursor.fetchone()
        
        conn.close()
        
        if leave:
            return f"On Leave: {leave[0]}"
        else:
            return "Working"

    def get_absent_employees(self, date_str):
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check for holiday first? If holiday, theoretically everyone is absent (or not working).
        # But request asks for "how many employees are absent". 
        # Usually implies people who SHOULD be working but are not.
        # But if it's a holiday, everyone is off. Let's return holiday info if it is one.
        
        cursor.execute('SELECT name FROM holidays WHERE date = ?', (date_str,))
        holiday = cursor.fetchone()
        if holiday:
            conn.close()
            return [], f"It is a Holiday: {holiday[0]}"

        # Find employees on leave
        cursor.execute('''
            SELECT e.name, l.reason 
            FROM leaves l
            JOIN employees e ON l.employee_id = e.id
            WHERE l.start_date <= ? AND l.end_date >= ?
        ''', (date_str, date_str))
        
        absentees = cursor.fetchall()
        conn.close()
        
        return absentees, None

    def get_all_employees(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM employees')
        emps = cursor.fetchall()
        conn.close()
        return emps

    def get_holidays_set(self):
        """ Returns a set of all holiday dates (YYYY-MM-DD) """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT date FROM holidays')
        holidays = {row[0] for row in cursor.fetchall()}
        conn.close()
        return holidays

    def calculate_used_days(self, start_date_str, end_date_str, holidays_set):
        """ Calculates business days between start and end (inclusive), excluding holidays """
        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        end = datetime.strptime(end_date_str, "%Y-%m-%d")
        
        days = 0
        curr = start
        from datetime import timedelta
        
        while curr <= end:
            # Check if weekend (Sat=5, Sun=6)
            if curr.weekday() < 5:
                d_str = curr.strftime("%Y-%m-%d")
                if d_str not in holidays_set:
                    days += 1
            curr += timedelta(days=1)
            
        return days

    def get_employee_by_id(self, employee_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, leave_limit, username, password_hash, role, team_id 
            FROM employees WHERE id = ?
        ''', (employee_id,))
        emp = cursor.fetchone()
        conn.close()
        return emp

    def update_employee(self, employee_id, name, leave_limit, team_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE employees SET name = ?, leave_limit = ?, team_id = ? WHERE id = ?
        ''', (name, leave_limit, team_id, employee_id))
        conn.commit()
        conn.close()

    def delete_employee(self, employee_id):
        conn = get_connection()
        cursor = conn.cursor()
        # Note: Leaves for this employee will remain but be orphaned or we should delete them too?
        # Better UX: Delete leaves associated with employee
        cursor.execute('DELETE FROM leaves WHERE employee_id = ?', (employee_id,))
        cursor.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
        conn.commit()
        conn.close()

    def get_leave_by_id(self, leave_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, employee_id, start_date, end_date, reason, status, manager_comment FROM leaves WHERE id = ?', (leave_id,))
        leave = cursor.fetchone()
        conn.close()
        return leave

    def update_leave(self, leave_id, employee_id, start_date, end_date, reason):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE leaves SET employee_id = ?, start_date = ?, end_date = ?, reason = ?
            WHERE id = ?
        ''', (employee_id, start_date, end_date, reason, leave_id))
        conn.commit()
        conn.close()

    def delete_leave(self, leave_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM leaves WHERE id = ?', (leave_id,))
        conn.commit()
        conn.close()

    def get_all_leaves(self):
        """ Returns list of (id, emp_name, start_date, end_date, reason, status, manager_comment) """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.id, e.name, l.start_date, l.end_date, l.reason, l.status, l.manager_comment
            FROM leaves l
            JOIN employees e ON l.employee_id = e.id
            ORDER BY l.start_date DESC
        ''')
        leaves = cursor.fetchall()
        conn.close()
        return leaves

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

    def get_pending_leaves(self, team_id=None):
        """ Returns list of pending requests optionally filtered by team_id """
        conn = get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT l.id, e.name, l.start_date, l.end_date, l.reason 
            FROM leaves l
            JOIN employees e ON l.employee_id = e.id
            WHERE l.status = 'pending'
        '''
        params = []
        if team_id:
            query += " AND e.team_id = ?"
            params.append(team_id)
            
        query += " ORDER BY l.start_date ASC"
        cursor.execute(query, tuple(params))
        leaves = cursor.fetchall()
        conn.close()
        return leaves

    def get_employees_with_balance(self, manager_id=None):
        """ Returns list of dicts: id, name, leave_limit, used_days, remaining_days, invite_token """
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get all employees
        query = '''
            SELECT e.id, e.name, e.leave_limit, t.name, e.invite_token
            FROM employees e
            LEFT JOIN teams t ON e.team_id = t.id
        '''
        params = []
        if manager_id:
            query += " WHERE t.owner_id = ?"
            params.append(manager_id)
            
        cursor.execute(query, tuple(params))
        employees = cursor.fetchall()
        
        # Get all leaves for the current year (simplified logic: get all and filter in python or sql)
        # Assuming limit is PER YEAR. We'll just fetch all leaves for now or maybe just this year if specified.
        # Requirement didn't specify year reset logic, so we'll assume ALL leaves count towards the limit 
        # OR better: assume current year. Let's do current year to be safe.
        current_year = datetime.now().year
        start_of_year = f"{current_year}-01-01"
        end_of_year = f"{current_year}-12-31"
        
        cursor.execute('SELECT employee_id, start_date, end_date FROM leaves WHERE end_date >= ? AND start_date <= ?', (start_of_year, end_of_year))
        all_leaves = cursor.fetchall()
        conn.close()
        
        holidays_set = self.get_holidays_set()
        
        result = []
        import collections
        emp_leaves = collections.defaultdict(list)
        for emp_id, start, end in all_leaves:
            emp_leaves[emp_id].append((start, end))
            
        for emp_id, name, limit, team_name, invite_token in employees:
            if limit is None: limit = 26 # Fallback if migration missed or new emp
            
            used = 0
            if emp_id in emp_leaves:
                for start, end in emp_leaves[emp_id]:
                    # Clip leave to current year if it overlaps year boundary
                    s = max(start, start_of_year)
                    e = min(end, end_of_year)
                    used += self.calculate_used_days(s, e, holidays_set)
            
            remaining = limit - used
            result.append({
                'id': emp_id,
                'name': name,
                'team': team_name or 'Brak zespołu',
                'leave_limit': limit,
                'used_days': used,
                'remaining_days': remaining,
                'invite_token': invite_token
            })
            
        return result
        
    def get_monthly_data(self, start_date, end_date):
        """
        Returns a dict of date -> {'holiday': name, 'absentees': [(name, reason)]}
        for the range [start_date, end_date] inclusive.
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        data = {}
        
        # Get Holidays
        cursor.execute('SELECT date, name FROM holidays WHERE date BETWEEN ? AND ?', (start_date, end_date))
        holidays = cursor.fetchall()
        for date, name in holidays:
            if date not in data: data[date] = {'holiday': None, 'absentees': []}
            data[date]['holiday'] = name

        # Get Leaves
        # Logic: find leaves that OVERLAP with the requested range and aren't declined
        # l.start_date <= end_date AND l.end_date >= start_date
        cursor.execute('''
            SELECT l.id, l.start_date, l.end_date, e.name, l.reason, l.status 
            FROM leaves l
            JOIN employees e ON l.employee_id = e.id
            WHERE l.start_date <= ? AND l.end_date >= ? AND l.status != 'declined'
        ''', (end_date, start_date))
        
        leaves = cursor.fetchall()
        conn.close()

        # Iterate leaves and populate days
        # We need to expand the leave ranges into individual days
        from datetime import datetime, timedelta
        
        fmt = '%Y-%m-%d'
        range_start = datetime.strptime(start_date, fmt)
        range_end = datetime.strptime(end_date, fmt)

        for l_id, l_start, l_end, emp_name, reason, status in leaves:
            s = datetime.strptime(l_start, fmt)
            e = datetime.strptime(l_end, fmt)
            
            # Clip to the requested range
            curr = max(s, range_start)
            end = min(e, range_end)
            
            while curr <= end:
                d_str = curr.strftime(fmt)
                if d_str not in data: data[d_str] = {'holiday': None, 'absentees': []}
                data[d_str]['absentees'].append({
                    'id': l_id,
                    'name': emp_name, 
                    'reason': reason,
                    'status': status
                })
                curr += timedelta(days=1)
                
        return data

    def get_all_teams(self, owner_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        if owner_id:
            cursor.execute('SELECT id, name FROM teams WHERE owner_id = ? ORDER BY name', (owner_id,))
        else:
            cursor.execute('SELECT id, name FROM teams ORDER BY name')
        teams = cursor.fetchall()
        conn.close()
        return teams

    def add_team(self, name, owner_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO teams (name, owner_id) VALUES (?, ?)', (name, owner_id))
            team_id = cursor.lastrowid
            conn.commit()
            return team_id
        except Exception:
            return None
        finally:
            conn.close()

    def get_employees_by_team(self, team_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM employees WHERE team_id = ? OR ? IS NULL ORDER BY name', (team_id, team_id))
        emps = cursor.fetchall()
        conn.close()
        return emps
