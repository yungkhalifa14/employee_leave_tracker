import argparse
from tracker import LeaveTracker
from db import init_db
import sys

def main():
    # Ensure DB is initialized
    init_db()
    
    tracker = LeaveTracker()
    
    parser = argparse.ArgumentParser(description="Employee Leave Tracker")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add Employee
    parser_add_emp = subparsers.add_parser('add-emp', help='Add a new employee')
    parser_add_emp.add_argument('name', help='Name of the employee')
    
    # Add Holiday
    parser_add_hol = subparsers.add_parser('add-holiday', help='Add a holiday')
    parser_add_hol.add_argument('date', help='Date of holiday (YYYY-MM-DD)')
    parser_add_hol.add_argument('name', help='Name of the holiday')

    # Book Leave
    parser_leave = subparsers.add_parser('book-leave', help='Book a leave for an employee')
    parser_leave.add_argument('emp_id', type=int, help='Employee ID')
    parser_leave.add_argument('start', help='Start date (YYYY-MM-DD)')
    parser_leave.add_argument('end', help='End date (YYYY-MM-DD)')
    parser_leave.add_argument('reason', help='Reason for leave')

    # Status
    parser_status = subparsers.add_parser('status', help='Check status of an employee on a date')
    parser_status.add_argument('emp_id', type=int, help='Employee ID')
    parser_status.add_argument('date', help='Date to check (YYYY-MM-DD)')

    # Absent
    parser_absent = subparsers.add_parser('absent', help='Check who is absent on a date')
    parser_absent.add_argument('date', help='Date to check (YYYY-MM-DD)')

    # List Employees
    parser_list = subparsers.add_parser('list-emps', help='List all employees')

    args = parser.parse_args()

    if args.command == 'add-emp':
        emp_id = tracker.add_employee(args.name)
        print(f"Employee added with ID: {emp_id}")
    
    elif args.command == 'add-holiday':
        tracker.add_holiday(args.date, args.name)
        print(f"Holiday '{args.name}' added on {args.date}")
    
    elif args.command == 'book-leave':
        tracker.add_leave(args.emp_id, args.start, args.end, args.reason)
        print("Leave booked successfully.")
    
    elif args.command == 'status':
        status = tracker.check_employee_status(args.emp_id, args.date)
        print(f"Status for Employee {args.emp_id} on {args.date}: {status}")

    elif args.command == 'absent':
        absentees, holiday_msg = tracker.get_absent_employees(args.date)
        if holiday_msg:
            print(holiday_msg)
        else:
            print(f"Absent employees on {args.date}:")
            if not absentees:
                print("None. Everyone is working.")
            for name, reason in absentees:
                print(f"- {name} ({reason})")
                
    elif args.command == 'list-emps':
        emps = tracker.get_all_employees()
        for eid, name in emps:
            print(f"{eid}: {name}")
            
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
