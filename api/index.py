
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, date
import calendar
import json
from hindu_calendar import hindu_calendar
from functools import wraps
import secrets

# Use persistent disk on Render if available
DB_PATH = '/data/blazecore_payroll.db' if os.path.exists('/data') else 'blazecore_payroll.db'

import os

# Get the absolute path of the directory where this file is located (the 'api' folder)
_cwd = os.path.dirname(os.path.abspath(__file__))

# Tell Flask that the templates and static folders are one level up from the 'api' folder
app = Flask(__name__,
            static_folder=os.path.join(_cwd, '../static'),
            template_folder=os.path.join(_cwd, '../templates'))
app.secret_key = 'shree-balaji-centring-works-secret-key-2024'  # Fixed secret key for session management
app.config['SESSION_COOKIE_SECURE'] = False  # Allow HTTP for development
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Changed back to Lax for better compatibility

# ...existing code from app.py...

# The rest of your app.py code goes here, unchanged.

import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, date
import calendar
import json
from hindu_calendar import hindu_calendar
from functools import wraps
import secrets

# Use persistent disk on Render if available
DB_PATH = '/data/blazecore_payroll.db' if os.path.exists('/data') else 'blazecore_payroll.db'

app = Flask(__name__)
app.secret_key = 'shree-balaji-centring-works-secret-key-2024'  # Fixed secret key for session management
app.config['SESSION_COOKIE_SECURE'] = False  # Allow HTTP for development
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Changed back to Lax for better compatibility

class Database:
    """Handles all database operations for the application."""
    def __init__(self, db_name=DB_PATH):
        self.db_name = db_name
        self.create_tables()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn

    def create_tables(self):
        """Create the necessary tables if they don't exist."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                daily_wage REAL NOT NULL,
                phone TEXT DEFAULT '',
                start_date TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER,
                date TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (worker_id) REFERENCES workers (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS advances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (worker_id) REFERENCES workers (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS holidays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                type TEXT DEFAULT 'manual',
                description TEXT DEFAULT ''
            )
        ''')
        conn.commit()
        conn.close()

    def add_worker(self, name, daily_wage, phone='', start_date=''):
        """Add a new worker with validation."""
        if not name or not str(name).strip():
            raise ValueError("Worker name cannot be empty")
        if daily_wage <= 0:
            raise ValueError("Daily wage must be greater than 0")
        
        name = str(name).strip()
        phone = str(phone).strip() if phone else ''
        start_date = str(start_date).strip() if start_date else ''
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check for duplicate names
        cursor.execute("SELECT id FROM workers WHERE LOWER(name) = LOWER(?)", (name,))
        if cursor.fetchone():
            conn.close()
            raise ValueError(f"Worker '{name}' already exists")
        
        # Add phone and start_date columns if they don't exist
        try:
            cursor.execute("ALTER TABLE workers ADD COLUMN phone TEXT DEFAULT ''")
            cursor.execute("ALTER TABLE workers ADD COLUMN start_date TEXT DEFAULT ''")
            cursor.execute("ALTER TABLE workers ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Columns already exist
            
        cursor.execute("INSERT INTO workers (name, daily_wage, phone, start_date) VALUES (?, ?, ?, ?)", 
                      (name, daily_wage, phone, start_date))
        worker_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return worker_id

    def get_workers(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workers ORDER BY name")
        workers = cursor.fetchall()
        conn.close()
        return [dict(worker) for worker in workers]

    def get_worker(self, worker_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
        worker = cursor.fetchone()
        conn.close()
        return dict(worker) if worker else None

    def mark_attendance(self, worker_id, date_str, status):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if the date is a holiday
        holiday = self.is_holiday(date_str)
        if holiday and status in ['Present', 'Half Day']:
            # Allow marking attendance on holidays but warn the caller
            pass  # We'll handle this in the API endpoint
        
        cursor.execute("SELECT id FROM attendance WHERE worker_id = ? AND date = ?", (worker_id, date_str))
        record = cursor.fetchone()
        
        if status == 'unmarked':
            if record:
                cursor.execute("DELETE FROM attendance WHERE id = ?", (record['id'],))
        else:
            if record:
                cursor.execute("UPDATE attendance SET status = ? WHERE id = ?", (status, record['id']))
            else:
                cursor.execute("INSERT INTO attendance (worker_id, date, status) VALUES (?, ?, ?)", (worker_id, date_str, status))
        
        conn.commit()
        conn.close()
        
        return holiday  # Return holiday info if date is a holiday

    def get_attendance_for_month(self, worker_id, month, year):
        month_str = f"{year}-{str(month).zfill(2)}"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT date, status FROM attendance WHERE worker_id = ? AND strftime('%Y-%m', date) = ?", (worker_id, month_str))
        results = cursor.fetchall()
        conn.close()
        
        attendance_data = {}
        for row in results:
            day = datetime.strptime(row['date'], '%Y-%m-%d').day
            attendance_data[day] = row['status']
        return attendance_data

    def add_advance(self, worker_id, amount, date_str, note=''):
        """Add advance payment with validation."""
        if amount <= 0:
            raise ValueError("Advance amount must be greater than 0")
        if amount > 50000:
            raise ValueError("Advance amount seems too high (max: ₹50,000)")
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Add note column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE advances ADD COLUMN note TEXT DEFAULT ''")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        cursor.execute("INSERT INTO advances (worker_id, amount, date, note) VALUES (?, ?, ?, ?)", 
                      (worker_id, amount, date_str, note))
        conn.commit()
        conn.close()

    def delete_worker(self, worker_id):
        """Delete a worker and all related records."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Delete related records first
        cursor.execute("DELETE FROM attendance WHERE worker_id = ?", (worker_id,))
        cursor.execute("DELETE FROM advances WHERE worker_id = ?", (worker_id,))
        
        # Delete the worker
        cursor.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
        
        conn.commit()
        conn.close()

    def get_attendance(self, worker_id, year, month):
        """Get attendance records for a specific worker and month."""
        month_str = f"{year}-{str(month).zfill(2)}"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT date, status FROM attendance WHERE worker_id = ? AND strftime('%Y-%m', date) = ? ORDER BY date DESC",
            (worker_id, month_str)
        )
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]

    def get_advances(self, worker_id, year, month):
        """Get advance records for a specific worker and month."""
        month_str = f"{year}-{str(month).zfill(2)}"
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Add note column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE advances ADD COLUMN note TEXT DEFAULT ''")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        cursor.execute(
            "SELECT amount, date, COALESCE(note, '') as reason FROM advances WHERE worker_id = ? AND strftime('%Y-%m', date) = ? ORDER BY date DESC",
            (worker_id, month_str)
        )
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]

    def get_advances_for_month(self, worker_id, month, year):
        """Get total advances for a month (legacy method)."""
        month_str = f"{year}-{str(month).zfill(2)}"
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) as total FROM advances WHERE worker_id = ? AND strftime('%Y-%m', date) = ?", (worker_id, month_str))
        result = cursor.fetchone()
        conn.close()
        return result['total'] if result['total'] else 0.0

    def update_worker(self, worker_id, name, daily_wage):
        """Update a worker with validation."""
        if not name or not str(name).strip():
            raise ValueError("Worker name cannot be empty")
        if daily_wage <= 0:
            raise ValueError("Daily wage must be greater than 0")
        
        name = str(name).strip()
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if worker exists
        cursor.execute("SELECT id FROM workers WHERE id = ?", (worker_id,))
        if not cursor.fetchone():
            conn.close()
            raise ValueError("Worker not found")
        
        # Check for duplicate names (excluding current worker)
        cursor.execute("SELECT id FROM workers WHERE LOWER(name) = LOWER(?) AND id != ?", (name, worker_id))
        if cursor.fetchone():
            conn.close()
            raise ValueError(f"Worker '{name}' already exists")
        
        cursor.execute("UPDATE workers SET name = ?, daily_wage = ? WHERE id = ?", (name, daily_wage, worker_id))
        conn.commit()
        conn.close()

    # Holiday management methods
    def add_holiday(self, date_str, name, holiday_type='manual', description=''):
        """Add a holiday."""
        if not name or not str(name).strip():
            raise ValueError("Holiday name cannot be empty")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT INTO holidays (date, name, type, description) VALUES (?, ?, ?, ?)", 
                          (date_str, name.strip(), holiday_type, description))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Holiday already exists for date {date_str}")
        
        conn.close()
    
    def get_holidays(self, year=None, month=None):
        """Get holidays for a specific year/month or all holidays."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if year and month:
            month_str = f"{year}-{str(month).zfill(2)}"
            cursor.execute("SELECT * FROM holidays WHERE strftime('%Y-%m', date) = ? ORDER BY date", (month_str,))
        elif year:
            cursor.execute("SELECT * FROM holidays WHERE strftime('%Y', date) = ? ORDER BY date", (str(year),))
        else:
            cursor.execute("SELECT * FROM holidays ORDER BY date DESC")
        
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]
    
    def delete_holiday(self, holiday_id):
        """Delete a holiday."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM holidays WHERE id = ?", (holiday_id,))
        conn.commit()
        conn.close()
    
    def is_holiday(self, date_str):
        """Check if a date is a holiday."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM holidays WHERE date = ?", (date_str,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
db = Database()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
            print(f"Login attempt - Username: '{username}', Password length: {len(password)}")  # Debug log
            
            # Check if fields are provided
            if not username or not password:
                flash('Please enter both username and password', 'error')
                return render_template('login.html')
            
            # Simple hardcoded authentication
            if username == 'admin' and password == 'shreebalaji2024':
                session.clear()  # Clear any existing session data
                session['logged_in'] = True
                session['username'] = username
                session.permanent = True  # Make session permanent
                
                flash('Welcome to Shree Balaji Centring Works!', 'success')
                print(f"Login successful for user: {username}")  # Debug log
                print(f"Session data: {dict(session)}")  # Debug log
                
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'error')
                print(f"Login failed for user: '{username}'")  # Debug log
                
        except Exception as e:
            print(f"Login error: {str(e)}")  # Debug log
            flash('An error occurred during login. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/simple-login')
def simple_login():
    """Simple login page for testing."""
    return render_template('simple_login.html')

@app.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/test')
def test_route():
    """Test route to check if app is working."""
    return jsonify({
        'status': 'OK',
        'message': 'App is working',
        'session': dict(session),
        'logged_in': session.get('logged_in', False)
    })

@app.route('/test-session', methods=['GET', 'POST'])
def test_session():
    """Test route to debug session issues."""
    if request.method == 'POST':
        # Set session data
        session['test_key'] = 'test_value'
        session['logged_in'] = True
        return jsonify({
            'status': 'Session set',
            'session_data': dict(session)
        })
    else:
        # Get session data
        return jsonify({
            'status': 'Session check',
            'session_data': dict(session),
            'logged_in': session.get('logged_in', False)
        })

@app.route('/test-session-page')
def test_session_page():
    """Test session page."""
    return render_template('test_session.html')

@app.route('/')
@login_required
def dashboard():
    """Main dashboard showing all workers."""
    try:
        workers = db.get_workers()
        # Add attendance count for each worker
        for worker in workers:
            current_month = datetime.now().month
            current_year = datetime.now().year
            attendance = db.get_attendance(worker['id'], current_year, current_month)
            worker['attendance_count'] = len([a for a in attendance if a['status'] in ['Present', 'Half Day']])
            # Ensure consistent field naming
            worker['wage'] = worker['daily_wage']  # Add wage field for frontend compatibility
        return render_template('dashboard.html', workers=workers)
    except Exception as e:
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/reports')
@login_required
def reports():
    """Reports page."""
    return render_template('reports.html')

@app.route('/settings')
@login_required
def settings():
    """Settings page."""
    return render_template('settings.html')

@app.route('/worker/<int:worker_id>')
@login_required
def worker_details(worker_id):
    """Worker details page with comprehensive data."""
    try:
        worker = db.get_worker(worker_id)
        if not worker:
            return redirect(url_for('dashboard'))
        
        current_date = datetime.now()
        current_month = current_date.month
        current_year = current_date.year
        
        # Get current month data
        attendance = db.get_attendance(worker_id, current_year, current_month)
        advances = db.get_advances(worker_id, current_year, current_month)
        
        # Calculate totals
        attendance_count = len([a for a in attendance if a['status'] in ['Present', 'Half Day']])
        total_earned = sum(worker['daily_wage'] if a['status'] == 'Present' else worker['daily_wage']/2 
                          for a in attendance if a['status'] in ['Present', 'Half Day'])
        total_advance = sum(a['amount'] for a in advances)
        balance = total_earned - total_advance
        
        current_month_name = calendar.month_name[current_month] + ' ' + str(current_year)
        
        return render_template('worker_details.html', 
                             worker=worker,
                             attendance_count=attendance_count,
                             total_earned=total_earned,
                             total_advance=total_advance,
                             balance=balance,
                             current_month=current_month_name)
    except Exception as e:
        return f"Error loading worker details: {str(e)}", 500

@app.route('/api/workers')
@login_required
def get_workers():
    """API endpoint to get all workers with attendance data."""
    try:
        workers = db.get_workers()
        current_month = datetime.now().month
        current_year = datetime.now().year
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Add attendance count and today's status for each worker
        for worker in workers:
            attendance = db.get_attendance(worker['id'], current_year, current_month)
            worker['attendance_count'] = len([a for a in attendance if a['status'] in ['Present', 'Half Day']])
            
            # Check if worker is present today for live status
            today_attendance = next((a for a in attendance if a['date'] == today), None)
            worker['present_today'] = today_attendance and today_attendance['status'] in ['Present', 'Half Day']
            
            # Ensure consistent field naming for frontend
            worker['wage'] = worker['daily_wage']
        
        return jsonify(workers)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
@login_required
def get_stats():
    """Get dashboard statistics."""
    try:
        current_date = date.today()
        workers = db.get_workers()
        total_workers = len(workers)
        
        # Calculate stats for current month
        present_today = 0
        total_payroll = 0
        total_attendance_days = 0

        today_str = current_date.strftime('%Y-%m-%d')

        for worker in workers:
            attendance = db.get_attendance(worker['id'], current_date.year, current_date.month)
            # Only count each worker once for present_today
            present_today_for_worker = any(
                record['date'] == today_str and record['status'] in ['Present', 'Half Day']
                for record in attendance
            )
            if present_today_for_worker:
                present_today += 1
            # Payroll and avg attendance for the month (unchanged)
            for record in attendance:
                if record['status'] == 'Present':
                    total_payroll += worker['daily_wage']
                    total_attendance_days += 1
                elif record['status'] == 'Half Day':
                    total_payroll += worker['daily_wage'] / 2
                    total_attendance_days += 0.5

        # Calculate average attendance
        if total_workers > 0:
            avg_attendance = round((total_attendance_days / total_workers / current_date.day) * 100)
            avg_attendance = min(avg_attendance, 100)
        else:
            avg_attendance = 0

        return jsonify({
            'total_workers': total_workers,
            'present_today': present_today,
            'total_payroll': int(total_payroll),
            'avg_attendance': avg_attendance
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_worker/<int:worker_id>', methods=['DELETE'])
@login_required
def delete_worker_api(worker_id):
    """Delete a worker and all related records."""
    try:
        db.delete_worker(worker_id)
        return jsonify({'success': True, 'message': 'Worker deleted successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/worker/<int:worker_id>/attendance')
@login_required
def get_worker_attendance(worker_id):
    """Get attendance records for a worker."""
    try:
        year = request.args.get('year', type=int) or datetime.now().year
        month = request.args.get('month', type=int) or datetime.now().month
        
        attendance = db.get_attendance(worker_id, year, month)
        worker = db.get_worker(worker_id)
        
        # Add wage earned and Hindu calendar info for each record
        for record in attendance:
            if record['status'] == 'Present':
                record['wage_earned'] = worker['daily_wage']
            elif record['status'] == 'Half Day':
                record['wage_earned'] = worker['daily_wage'] / 2
            else:
                record['wage_earned'] = 0
            
            # Add Hindu calendar information
            try:
                record_date = datetime.strptime(record['date'], '%Y-%m-%d').date()
                panchang = hindu_calendar.get_panchang_summary(record_date)
                record['hindu_date'] = {
                    'tithi': panchang['tithi'],
                    'paksha': panchang['paksha'], 
                    'hindu_month': panchang['hindu_month'],
                    'festival': panchang['festival'],
                    'is_shraddha': panchang['is_shraddha']
                }
            except:
                record['hindu_date'] = None
        
        return jsonify(attendance)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/worker/<int:worker_id>/advances')
@login_required
def get_worker_advances(worker_id):
    """Get advance records for a worker."""
    try:
        year = request.args.get('year', type=int) or datetime.now().year
        month = request.args.get('month', type=int) or datetime.now().month
        
        advances = db.get_advances(worker_id, year, month)
        return jsonify(advances)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/mark_attendance', methods=['POST'])
@login_required
def mark_attendance_api():
    """Mark attendance for a worker."""
    try:
        data = request.get_json()
        worker_id = data.get('worker_id')
        date_str = data.get('date')
        status = data.get('status')
        
        if not worker_id or not date_str or not status:
            return jsonify({'success': False, 'error': 'Missing required fields: worker_id, date, and status are required'}), 400
        
        # Validate worker exists
        worker = db.get_worker(worker_id)
        if not worker:
            return jsonify({'success': False, 'error': f'Worker with ID {worker_id} not found'}), 404
        
        # Validate status
        valid_statuses = ['Present', 'Absent', 'Half Day', 'unmarked']
        if status not in valid_statuses:
            return jsonify({'success': False, 'error': f'Invalid status. Must be one of: {valid_statuses}'}), 400
        
        # Validate date format
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        holiday = db.mark_attendance(worker_id, date_str, status)
        
        message = f'Attendance marked as {status} for {worker["name"]}'
        if holiday and status in ['Present', 'Half Day']:
            message += f' (Note: {holiday["name"]} is marked as a holiday)'
        
        return jsonify({
            'success': True, 
            'message': message,
            'holiday_warning': holiday is not None,
            'worker_name': worker['name']
        })
    except Exception as e:
        print(f"Error in mark_attendance_api: {str(e)}")  # Debug logging
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500

@app.route('/api/update_worker/<int:worker_id>', methods=['PUT'])
@login_required
def update_worker_api(worker_id):
    """Update a worker's information."""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        wage = float(data.get('wage', 0))
        
        db.update_worker(worker_id, name, wage)
        return jsonify({'success': True, 'message': f"Worker '{name}' updated successfully!"})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f"Failed to update worker: {str(e)}"}), 500

@app.route('/api/give_advance', methods=['POST'])
@login_required
def give_advance_api():
    """Give advance to a worker."""
    try:
        data = request.get_json()
        worker_id = data.get('worker_id')
        amount = data.get('amount')
        date_str = data.get('date')
        note = data.get('note', '')
        
        if not worker_id or not amount or not date_str:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        db.add_advance(worker_id, amount, date_str, note)
        return jsonify({'success': True, 'message': f'Advance of ₹{amount} given successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/add_worker', methods=['POST'])
@login_required
def add_worker():
    """Add a new worker."""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        wage = float(data.get('wage', 0))
        phone = data.get('phone', '').strip()
        start_date = data.get('start_date', '').strip()
        
        worker_id = db.add_worker(name, wage, phone, start_date)
        return jsonify({'success': True, 'worker_id': worker_id, 'message': f"Worker '{name}' added successfully!"})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f"Failed to add worker: {str(e)}"}), 500

@app.route('/api/attendance/<int:worker_id>')
@login_required
def get_attendance(worker_id):
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    
    attendance_data = db.get_attendance_for_month(worker_id, month, year)
    return jsonify(attendance_data)

@app.route('/api/attendance/<int:worker_id>', methods=['POST'])
@login_required
def mark_attendance(worker_id):
    try:
        data = request.get_json()
        date_str = data.get('date')
        status = data.get('status')
        
        db.mark_attendance(worker_id, date_str, status)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/summary/<int:worker_id>')
@login_required
def get_summary(worker_id):
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    
    worker = db.get_worker(worker_id)
    attendance_data = db.get_attendance_for_month(worker_id, month, year)
    
    present_days = list(attendance_data.values()).count('present')
    absent_days = list(attendance_data.values()).count('absent')
    total_working_days = len(attendance_data)
    
    total_earnings = present_days * worker['daily_wage']
    total_advances = db.get_advances_for_month(worker_id, month, year)
    net_salary = total_earnings - total_advances
    
    return jsonify({
        'present_days': present_days,
        'absent_days': absent_days,
        'total_working_days': total_working_days,
        'total_earnings': total_earnings,
        'total_advances': total_advances,
        'net_salary': net_salary,
        'month_name': calendar.month_name[month],
        'year': year
    })

@app.route('/api/add_advance/<int:worker_id>', methods=['POST'])
@login_required
def add_advance(worker_id):
    try:
        data = request.get_json()
        amount = float(data.get('amount', 0))
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        db.add_advance(worker_id, amount, date_str)
        return jsonify({'success': True, 'message': f"Advance of ₹{amount:.2f} added successfully!"})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f"Failed to add advance: {str(e)}"}), 500

@app.route('/api/panchang')
@login_required
def get_panchang():
    """Get Hindu calendar (Panchang) information for today or specified date."""
    try:
        date_str = request.args.get('date')
        if date_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            target_date = date.today()
        
        panchang_info = hindu_calendar.get_panchang_summary(target_date)
        return jsonify(panchang_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/festivals/<int:year>/<int:month>')
@login_required
def get_month_festivals(year, month):
    """Get all festivals for a specific month."""
    try:
        if month == 0:  # Special case for all months
            festivals = []
            for m in range(1, 13):
                monthly_festivals = hindu_calendar.get_month_festivals(year, m)
                festivals.extend(monthly_festivals)
        else:
            festivals = hindu_calendar.get_month_festivals(year, month)
        return jsonify(festivals)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/suggested-holidays/<int:year>/<int:month>')
@login_required
def get_suggested_holidays(year, month):
    """Get suggested holidays for admin to add."""
    try:
        if month == 0:  # All months
            suggestions = []
            for m in range(1, 13):
                monthly_suggestions = hindu_calendar.get_suggested_holidays(year, m)
                suggestions.extend(monthly_suggestions)
        else:
            suggestions = hindu_calendar.get_suggested_holidays(year, month)
        return jsonify(suggestions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Holiday Management API
@app.route('/api/holidays', methods=['GET'])
@login_required
def get_holidays_api():
    """Get holidays for a specific year/month."""
    try:
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        holidays = db.get_holidays(year, month)
        return jsonify(holidays)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/holidays', methods=['POST'])
@login_required
def add_holiday_api():
    """Add a new holiday."""
    try:
        data = request.get_json()
        date_str = data.get('date')
        name = data.get('name')
        holiday_type = data.get('type', 'manual')
        description = data.get('description', '')
        
        if not date_str or not name:
            return jsonify({'success': False, 'error': 'Date and name are required'}), 400
        
        db.add_holiday(date_str, name, holiday_type, description)
        return jsonify({'success': True, 'message': f'Holiday "{name}" added successfully!'})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to add holiday: {str(e)}'}), 500

@app.route('/api/holidays/<int:holiday_id>', methods=['DELETE'])
@login_required
def delete_holiday_api(holiday_id):
    """Delete a holiday."""
    try:
        db.delete_holiday(holiday_id)
        return jsonify({'success': True, 'message': 'Holiday deleted successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/reports/payroll')
@login_required
def get_payroll_report():
    """Get payroll report for a specific month/year."""
    try:
        year = request.args.get('year', type=int) or datetime.now().year
        month = request.args.get('month', type=int) or datetime.now().month
        
        workers = db.get_workers()
        report_data = []
        
        total_payroll = 0
        total_advances = 0
        total_net = 0
        
        for worker in workers:
            attendance = db.get_attendance(worker['id'], year, month)
            advances = db.get_advances(worker['id'], year, month)
            
            present_days = len([a for a in attendance if a['status'] == 'Present'])
            half_days = len([a for a in attendance if a['status'] == 'Half Day'])
            
            gross_salary = (present_days * worker['daily_wage']) + (half_days * worker['daily_wage'] / 2)
            worker_advances = sum(a['amount'] for a in advances)
            net_salary = gross_salary - worker_advances
            
            total_payroll += gross_salary
            total_advances += worker_advances  
            total_net += net_salary
            
            report_data.append({
                'worker_id': worker['id'],
                'worker_name': worker['name'],
                'daily_wage': worker['daily_wage'],
                'present_days': present_days,
                'half_days': half_days,
                'total_days': present_days + (half_days * 0.5),
                'gross_salary': gross_salary,
                'advances': worker_advances,
                'net_salary': net_salary
            })
        
        return jsonify({
            'month': calendar.month_name[month],
            'year': year,
            'workers': report_data,
            'summary': {
                'total_workers': len(workers),
                'total_payroll': total_payroll,
                'total_advances': total_advances,
                'total_net': total_net
            }
        })
    except Exception as e:
        print(f"Error in payroll report: {str(e)}")  # Debug logging
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/attendance')
@login_required
def get_attendance_report():
    """Get attendance report for a specific month/year."""
    try:
        year = request.args.get('year', type=int) or datetime.now().year
        month = request.args.get('month', type=int) or datetime.now().month
        
        workers = db.get_workers()
        report_data = []
        
        # Get holidays for the month
        holidays = db.get_holidays(year, month)
        holiday_dates = [h['date'] for h in holidays]
        
        # Get all days in the month
        _, days_in_month = calendar.monthrange(year, month)
        
        for worker in workers:
            attendance = db.get_attendance(worker['id'], year, month)
            attendance_dict = {a['date']: a['status'] for a in attendance}
            
            present_count = 0
            absent_count = 0
            holiday_count = 0
            half_day_count = 0
            
            for day in range(1, days_in_month + 1):
                date_str = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
                
                if date_str in holiday_dates:
                    holiday_count += 1
                elif date_str in attendance_dict:
                    if attendance_dict[date_str] == 'Present':
                        present_count += 1
                    elif attendance_dict[date_str] == 'Half Day':
                        half_day_count += 1
                    else:
                        absent_count += 1
                else:
                    absent_count += 1
            
            attendance_percentage = ((present_count + (half_day_count * 0.5)) / (days_in_month - holiday_count)) * 100 if (days_in_month - holiday_count) > 0 else 0
            
            report_data.append({
                'worker_id': worker['id'],
                'worker_name': worker['name'],
                'present_days': present_count,
                'half_days': half_day_count,
                'absent_days': absent_count,
                'holidays': holiday_count,
                'total_working_days': days_in_month - holiday_count,
                'attendance_percentage': round(attendance_percentage, 1)
            })
        
        return jsonify({
            'month': calendar.month_name[month],
            'year': year,
            'workers': report_data,
            'holidays': holidays,
            'summary': {
                'total_days': days_in_month,
                'working_days': days_in_month - len(holidays),
                'holidays': len(holidays)
            }
        })
    except Exception as e:
        print(f"Error in attendance report: {str(e)}")  # Debug logging
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # For production, use a WSGI server like gunicorn or waitress
    # Example: gunicorn -w 4 app:app
    app.run(host='0.0.0.0', port=5000)