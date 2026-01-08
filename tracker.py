from db import get_connection
from datetime import datetime

class LeaveTracker:
    def add_employee(self, name):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO employees (name) VALUES (?)', (name,))
        emp_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return emp_id

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

    def add_leave(self, employee_id, start_date, end_date, reason):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO leaves (employee_id, start_date, end_date, reason)
            VALUES (?, ?, ?, ?)
        ''', (employee_id, start_date, end_date, reason))
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

    def get_employees_with_balance(self):
        """ Returns list of dicts: id, name, leave_limit, used_days, remaining_days """
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get all employees
        cursor.execute('SELECT id, name, leave_limit FROM employees')
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
            
        for emp_id, name, limit in employees:
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
                'leave_limit': limit,
                'used_days': used,
                'remaining_days': remaining
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
        # Logic: find leaves that OVERLAP with the requested range
        # l.start_date <= end_date AND l.end_date >= start_date
        cursor.execute('''
            SELECT l.start_date, l.end_date, e.name, l.reason 
            FROM leaves l
            JOIN employees e ON l.employee_id = e.id
            WHERE l.start_date <= ? AND l.end_date >= ?
        ''', (end_date, start_date))
        
        leaves = cursor.fetchall()
        conn.close()

        # Iterate leaves and populate days
        # We need to expand the leave ranges into individual days
        from datetime import datetime, timedelta
        
        fmt = '%Y-%m-%d'
        range_start = datetime.strptime(start_date, fmt)
        range_end = datetime.strptime(end_date, fmt)

        for l_start, l_end, emp_name, reason in leaves:
            s = datetime.strptime(l_start, fmt)
            e = datetime.strptime(l_end, fmt)
            
            # Clip to the requested range
            curr = max(s, range_start)
            end = min(e, range_end)
            
            while curr <= end:
                d_str = curr.strftime(fmt)
                if d_str not in data: data[d_str] = {'holiday': None, 'absentees': []}
                data[d_str]['absentees'].append({'name': emp_name, 'reason': reason})
                curr += timedelta(days=1)
                
        return data
