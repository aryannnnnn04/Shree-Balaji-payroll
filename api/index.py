import os
import time
import threading
import psycopg2
import psycopg2.extras # Important for getting dictionary-like results
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from datetime import datetime, date
import calendar
from functools import wraps
import secrets
from typing import Optional
# Assuming hindu_calendar.py is in the 'api' folder and has a HinduCalendar class
from hindu_calendar import HinduCalendar 

# --- This is the corrected Flask app definition with absolute paths ---
_cwd = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            static_folder=os.path.join(_cwd, '../static'),
            template_folder=os.path.join(_cwd, '../templates'))

# Request performance monitoring
@app.before_request
def before_request():
    """Record start time of request processing."""
    request.start_time = time.time()

@app.after_request
def after_request(response):
    """Log request performance metrics."""
    if hasattr(request, 'start_time'):
        elapsed = time.time() - request.start_time
        logger.info(f"{request.method} {request.path} completed in {elapsed:.2f}s")
    return response

# --- Configure the Flask app ---
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16)) # More secure for production
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # Session timeout
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max file size 16MB

# Global error handler
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    return jsonify({'error': 'Internal server error'}), 500

# Add password validation
def validate_password(password):
    """Validate password complexity."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    return True, ""

# --- The Rewritten Database Class for PostgreSQL (Neon) ---
from psycopg2.pool import SimpleConnectionPool
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    """Handles all database operations for the application."""
    def __init__(self):
        self.db_url = os.environ.get("POSTGRES_URL")
        if not self.db_url:
            raise Exception("POSTGRES_URL environment variable not set")
        self._pool = SimpleConnectionPool(
            minconn=1,
            maxconn=20,
            dsn=self.db_url,
            connect_timeout=3,  # Connection timeout in seconds
            keepalives=1,  # Enable TCP keepalive
            keepalives_idle=30,  # Number of seconds after which TCP should send keepalive
            keepalives_interval=10,  # Number of seconds between TCP keepalives
            keepalives_count=5  # Number of TCP keepalives before dropping connection
        )
        self._init_db()

    def _init_db(self):
        """Initialize database and create tables."""
        retries = 3
        for attempt in range(retries):
            try:
                self.create_tables()
                return
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Failed to initialize database after {retries} attempts: {e}")
                    raise
                logger.warning(f"Database initialization attempt {attempt + 1} failed: {e}")
                time.sleep(1)  # Wait before retry

    def get_connection(self):
        """Gets a connection from the connection pool with retry logic."""
        retries = 3
        last_error = None
        
        for attempt in range(retries):
            try:
                conn = self._pool.getconn()
                conn.set_session(autocommit=False)  # Explicit transaction management
                return conn
            except Exception as e:
                last_error = e
                logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(1)  # Wait before retry
                
        logger.error(f"Failed to get database connection after {retries} attempts: {last_error}")
        raise last_error

    def create_tables(self):
        """Create the necessary tables if they don't exist."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS workers (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        daily_wage NUMERIC NOT NULL,
                        phone TEXT DEFAULT '',
                        start_date TEXT DEFAULT '',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS attendance (
                        id SERIAL PRIMARY KEY,
                        worker_id INTEGER REFERENCES workers(id) ON DELETE CASCADE,
                        date DATE NOT NULL,
                        status TEXT NOT NULL,
                        UNIQUE(worker_id, date)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS advances (
                        id SERIAL PRIMARY KEY,
                        worker_id INTEGER REFERENCES workers(id) ON DELETE CASCADE,
                        amount NUMERIC NOT NULL,
                        date DATE NOT NULL,
                        note TEXT DEFAULT ''
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS holidays (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL UNIQUE,
                        name TEXT NOT NULL,
                        type TEXT DEFAULT 'manual',
                        description TEXT DEFAULT ''
                    )
                ''')
            conn.commit()
        finally:
            conn.close()

    def add_worker(self, name, daily_wage, phone='', start_date=''):
        if not name or not str(name).strip(): raise ValueError("Worker name cannot be empty")
        if daily_wage <= 0: raise ValueError("Daily wage must be greater than 0")
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id FROM workers WHERE LOWER(name) = LOWER(%s)", (name.strip(),))
                if cursor.fetchone(): raise ValueError(f"Worker '{name.strip()}' already exists")
                cursor.execute("INSERT INTO workers (name, daily_wage, phone, start_date) VALUES (%s, %s, %s, %s) RETURNING id", (name.strip(), daily_wage, phone.strip() if phone else '', start_date.strip() if start_date else ''))
                worker_id = cursor.fetchone()['id']
            conn.commit()
            return worker_id
        finally: conn.close()

    def get_workers(self):
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT * FROM workers ORDER BY name")
                workers = cursor.fetchall()
                result = []
                for row in workers:
                    worker = dict(row)
                    if 'daily_wage' in worker:
                        worker['daily_wage'] = float(worker['daily_wage'])
                    result.append(worker)
                return result
        finally: conn.close()

    def get_worker(self, worker_id):
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
                worker = cursor.fetchone()
                if worker:
                    result = dict(worker)
                    if 'daily_wage' in result:
                        result['daily_wage'] = float(result['daily_wage'])
                    return result
                return None
        finally: conn.close()

    def mark_attendance(self, worker_id, date_str, status):
        if not worker_id or not date_str:
            raise ValueError("Worker ID and date are required")
        if status not in ['Present', 'Half Day', 'Absent', 'unmarked']:
            raise ValueError("Invalid attendance status")

        conn = self.get_connection()
        try:
            # First verify the worker exists
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM workers WHERE id = %s", (worker_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Worker with ID {worker_id} not found")

                # Then handle attendance
                if status == 'unmarked':
                    cursor.execute("DELETE FROM attendance WHERE worker_id = %s AND date = %s", (worker_id, date_str))
                else:
                    cursor.execute("""
                        INSERT INTO attendance (worker_id, date, status) 
                        VALUES (%s, %s, %s) 
                        ON CONFLICT (worker_id, date) 
                        DO UPDATE SET status = EXCLUDED.status
                        RETURNING id
                    """, (worker_id, date_str, status))
                    if not cursor.fetchone():
                        raise Exception("Failed to update attendance record")
                conn.commit()
                return self.is_holiday(date_str)
        except Exception as e:
            conn.rollback()
            logger.error(f"Error marking attendance: {e}")
            raise
        finally:
            conn.close()

    def get_attendance(self, worker_id, year, month):
        """Get attendance records for a specific worker in a given month.
        
        Args:
            worker_id (int): The ID of the worker
            year (int): The year to fetch attendance for
            month (int): The month to fetch attendance for
            
        Returns:
            List[Dict]: List of attendance records
        """
        cache_key = f"attendance_{worker_id}_{year}_{month}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT date, status 
                    FROM attendance 
                    WHERE worker_id = %s 
                    AND EXTRACT(YEAR FROM date) = %s 
                    AND EXTRACT(MONTH FROM date) = %s 
                    ORDER BY date DESC
                """, (worker_id, year, month))
                result = [dict(row) for row in cursor.fetchall()]
                cache.set(cache_key, result, timeout_seconds=300)  # Cache for 5 minutes
                return result
        except Exception as e:
            logger.error(f"Error fetching attendance: {e}")
            raise
        finally:
            conn.close()

    def get_attendance_for_date(self, target_date):
        """Get attendance records for all workers on a specific date.
        
        Args:
            target_date (date): The date to fetch attendance for
            
        Returns:
            List[Dict]: List of attendance records with worker_id and status
        """
        cache_key = f"attendance_date_{target_date}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT worker_id, status 
                    FROM attendance 
                    WHERE date = %s
                """, (target_date,))
                result = [dict(row) for row in cursor.fetchall()]
                cache.set(cache_key, result, timeout_seconds=300)  # Cache for 5 minutes
                return result
        except Exception as e:
            logger.error(f"Error fetching attendance for date: {e}")
            raise
        finally:
            conn.close()

    def add_advance(self, worker_id, amount, date_str, note=''):
        # Input validation
        if not worker_id:
            raise ValueError("Worker ID is required")
        try:
            amount = float(amount)  # Convert to float to handle string inputs
        except (TypeError, ValueError):
            raise ValueError("Invalid advance amount")
            
        if amount <= 0:
            raise ValueError("Advance amount must be greater than 0")
        if amount > 50000:
            raise ValueError("Advance amount seems too high (max: ₹50,000)")
            
        if not date_str:
            raise ValueError("Date is required")

        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # Verify worker exists
                cursor.execute("SELECT id FROM workers WHERE id = %s", (worker_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Worker with ID {worker_id} not found")
                
                # Check total advances for the month to prevent excessive advances
                month_start = datetime.strptime(date_str, '%Y-%m-%d').replace(day=1).strftime('%Y-%m-%d')
                month_end = (datetime.strptime(date_str, '%Y-%m-%d').replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                month_end = month_end.strftime('%Y-%m-%d')
                
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0) 
                    FROM advances 
                    WHERE worker_id = %s AND date BETWEEN %s AND %s
                """, (worker_id, month_start, month_end))
                
                total_advances = cursor.fetchone()[0]
                if total_advances + amount > 100000:  # ₹100,000 monthly limit
                    raise ValueError("Total advances for the month would exceed ₹100,000")
                
                # Insert the advance
                cursor.execute("""
                    INSERT INTO advances (worker_id, amount, date, note) 
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (worker_id, amount, date_str, note))
                
                if not cursor.fetchone():
                    raise Exception("Failed to insert advance record")
                    
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error adding advance: {e}")
            raise
        finally:
            conn.close()

    def delete_worker(self, worker_id):
        if not worker_id:
            raise ValueError("Worker ID is required")

        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # Start transaction
                cursor.execute("BEGIN")
                
                # Verify worker exists
                cursor.execute("SELECT id FROM workers WHERE id = %s FOR UPDATE", (worker_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Worker with ID {worker_id} not found")
                
                # Delete attendance records
                cursor.execute("DELETE FROM attendance WHERE worker_id = %s", (worker_id,))
                
                # Delete advances
                cursor.execute("DELETE FROM advances WHERE worker_id = %s", (worker_id,))
                
                # Finally delete the worker
                cursor.execute("DELETE FROM workers WHERE id = %s RETURNING id", (worker_id,))
                if not cursor.fetchone():
                    raise Exception("Failed to delete worker")
                
                cursor.execute("COMMIT")
        except Exception as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Error deleting worker: {e}")
            raise
        finally:
            conn.close()

    def get_advances(self, worker_id, year, month):
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT amount, date, COALESCE(note, '') as reason FROM advances WHERE worker_id = %s AND EXTRACT(YEAR FROM date) = %s AND EXTRACT(MONTH FROM date) = %s ORDER BY date DESC", (worker_id, year, month))
                return [dict(row) for row in cursor.fetchall()]
        finally: conn.close()

    def update_worker(self, worker_id, name, daily_wage):
        if not worker_id:
            raise ValueError("Worker ID is required")
        if not name or not str(name).strip():
            raise ValueError("Worker name cannot be empty")
        
        try:
            daily_wage = float(daily_wage)  # Convert to float to handle string inputs
        except (TypeError, ValueError):
            raise ValueError("Invalid daily wage")
            
        if daily_wage <= 0:
            raise ValueError("Daily wage must be greater than 0")
        if daily_wage > 5000:  # Reasonable maximum daily wage
            raise ValueError("Daily wage seems too high (max: ₹5,000)")

        name = str(name).strip()
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Use transaction to prevent race conditions
                cursor.execute("BEGIN")
                
                # Check if worker exists using FOR UPDATE to lock the row
                cursor.execute("SELECT id FROM workers WHERE id = %s FOR UPDATE", (worker_id,))
                if not cursor.fetchone():
                    raise ValueError("Worker not found")
                
                # Check for duplicate names excluding current worker
                cursor.execute("SELECT id FROM workers WHERE LOWER(name) = LOWER(%s) AND id != %s", (name, worker_id))
                if cursor.fetchone():
                    raise ValueError(f"Worker '{name}' already exists")
                
                # Update the worker
                cursor.execute("""
                    UPDATE workers 
                    SET name = %s, 
                        daily_wage = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id
                """, (name, daily_wage, worker_id))
                
                if not cursor.fetchone():
                    raise Exception("Failed to update worker")
                
                cursor.execute("COMMIT")
        except Exception as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Error updating worker: {e}")
            raise
        finally:
            conn.close()

    def add_holiday(self, date_str, name, holiday_type='manual', description=''):
        if not name or not str(name).strip(): raise ValueError("Holiday name cannot be empty")
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO holidays (date, name, type, description) VALUES (%s, %s, %s, %s)", (date_str, name.strip(), holiday_type, description))
            conn.commit()
        except psycopg2.IntegrityError:
            conn.rollback()
            raise ValueError(f"Holiday already exists for date {date_str}")
        finally: conn.close()

    def get_holidays(self, year=None, month=None):
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                if year and month:
                    cursor.execute("SELECT * FROM holidays WHERE EXTRACT(YEAR FROM date) = %s AND EXTRACT(MONTH FROM date) = %s ORDER BY date", (year, month))
                elif year:
                    cursor.execute("SELECT * FROM holidays WHERE EXTRACT(YEAR FROM date) = %s ORDER BY date", (str(year),))
                else:
                    cursor.execute("SELECT * FROM holidays ORDER BY date DESC")
                return [dict(row) for row in cursor.fetchall()]
        finally: conn.close()

    def delete_holiday(self, holiday_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM holidays WHERE id = %s", (holiday_id,))
            conn.commit()
        finally: conn.close()

    def is_holiday(self, date_str):
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT name FROM holidays WHERE date = %s", (date_str,))
                result = cursor.fetchone()
                return dict(result) if result else None
        finally: conn.close()

# --- Create the single, global database object ---
db = Database()
hindu_calendar = HinduCalendar()

# Cleanup on app shutdown
@app.teardown_appcontext
def cleanup_db_pool(error):
    """Cleanup database connections when the app shuts down."""
    if hasattr(db, '_pool'):
        db._pool.closeall()
        logger.info("Database connection pool cleaned up")

from functools import lru_cache
from datetime import datetime, timedelta

class Cache:
    """Enhanced time-based cache implementation with statistics and LRU eviction"""
    def __init__(self):
        self._cache = {}
        self._timeouts = {}
        self._max_size = 1000  # Maximum number of cache entries
        self._hits = 0
        self._misses = 0
        self._last_accessed = {}  # For LRU tracking
        self._lock = threading.Lock()  # Thread safety

    def get(self, key: str) -> Optional[any]:
        """Get value from cache with thread safety and metrics."""
        with self._lock:
            self.cleanup()  # Clean expired items before access
            now = datetime.now()
            
            if key in self._cache and now < self._timeouts[key]:
                self._hits += 1
                self._last_accessed[key] = now
                return self._cache[key]
            
            self._misses += 1
            return None

    def set(self, key: str, value: any, timeout_seconds: int = 300):
        """Set value in cache with LRU eviction and thread safety."""
        with self._lock:
            self.cleanup()  # Clean expired items before setting new one
            now = datetime.now()
            
            # LRU eviction if cache is full
            if len(self._cache) >= self._max_size:
                # Find least recently used item
                lru_key = min(self._last_accessed.items(), key=lambda x: x[1])[0]
                self.delete(lru_key)
            
            self._cache[key] = value
            self._timeouts[key] = now + timedelta(seconds=timeout_seconds)
            self._last_accessed[key] = now

    def delete(self, key: str):
        """Delete item from cache with thread safety."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timeouts[key]
                if key in self._last_accessed:
                    del self._last_accessed[key]

    def cleanup(self):
        """Remove expired cache entries with thread safety."""
        with self._lock:
            now = datetime.now()
            expired_keys = [k for k, v in self._timeouts.items() if now > v]
            for k in expired_keys:
                self.delete(k)

    def clear(self):
        """Clear all cache entries with thread safety."""
        with self._lock:
            self._cache.clear()
            self._timeouts.clear()
            self._last_accessed.clear()
            self._hits = 0
            self._misses = 0

    def get_stats(self):
        """Get cache performance statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': f"{hit_rate:.2f}%",
                'items': len(self._cache)
            }

cache = Cache()

# --- YOUR FLASK ROUTES WITH CACHING ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta

def validate_api_response(func):
    """Decorator to validate and standardize API responses."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            
            # Add performance metrics to response headers
            if isinstance(result, tuple):
                response, status_code = result
            else:
                response, status_code = result, 200
                
            if isinstance(response, dict):
                response['metadata'] = {
                    'timestamp': datetime.now().isoformat(),
                    'execution_time': f"{elapsed:.3f}s"
                }
            
            return jsonify(response), status_code
            
        except ValueError as e:
            logger.warning(f"Validation error in {func.__name__}: {str(e)}")
            return jsonify({
                'error': str(e),
                'type': 'ValidationError'
            }), 400
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Internal server error',
                'type': 'ServerError'
            }), 500
    return wrapper

# Store failed login attempts
login_attempts = {}

def check_login_attempts(ip):
    """Check if IP is allowed to attempt login"""
    if ip in login_attempts:
        attempts = login_attempts[ip]
        if len(attempts) >= 5:  # Max 5 attempts
            last_attempt = max(attempts)
            if datetime.now() - last_attempt < timedelta(minutes=15):
                return False
            login_attempts[ip] = set()  # Reset after 15 minutes
    return True

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ip = request.remote_addr
        if not check_login_attempts(ip):
            flash('Too many failed attempts. Please try again later.', 'error')
            return render_template('login.html'), 429

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('login.html')

        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password_hash = os.environ.get('ADMIN_PASSWORD_HASH')
        
        if not admin_password_hash:
            logger.error("ADMIN_PASSWORD_HASH environment variable not set")
            flash('Server configuration error', 'error')
            return render_template('login.html'), 500

        if username == admin_username and check_password_hash(admin_password_hash, password):
            session.clear()
            session['logged_in'] = True
            session['username'] = username
            session.permanent = True
            if ip in login_attempts:
                del login_attempts[ip]  # Reset successful login
            return redirect(url_for('dashboard'))
        else:
            if ip not in login_attempts:
                login_attempts[ip] = set()
            login_attempts[ip].add(datetime.now())
            flash('Invalid username or password', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/')
def home():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Security check: use 'logged_in' session key
    if 'logged_in' not in session:
        flash("You must be logged in to view the dashboard.", "danger")
        return redirect(url_for('login'))
    try:
        workers = db.get_workers()
        return render_template('dashboard.html', workers=workers, worker_count=len(workers))
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
        return render_template('dashboard.html', workers=[], worker_count=0)

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/worker/<int:worker_id>')
@login_required
def worker_details(worker_id):
    worker = db.get_worker(worker_id)
    if not worker:
        return redirect(url_for('dashboard'))
    return render_template('worker_details.html', worker=worker)

# --- ALL YOUR API ROUTES, RESTORED AND CONVERTED ---

from typing import List, Dict, Union, Optional
from flask import Response

@app.route('/api/workers')
@login_required
def get_workers_api() -> Response:
    """Get all workers with their current day attendance status.
    
    Returns:
        Response: JSON response containing:
            - List of worker objects with their details and present_today status
            - 500 error response if database operation fails
    """
    try:
        workers = db.get_workers()
        today = date.today()
        
        # Fetch all attendance records for today in a single query
        attendance_records = {}
        try:
            records = db.get_attendance_for_date(today)
            if records:
                attendance_records = {
                    record['worker_id']: record['status'] 
                    for record in records if record and 'worker_id' in record and 'status' in record
                }
        except Exception as e:
            logger.error(f"Error fetching attendance records: {e}")
            attendance_records = {}
        
        for worker in workers:
            try:
                status = attendance_records.get(worker.get('id'))
                worker['present_today'] = status in ['Present', 'Half Day'] if status else False
            except Exception as e:
                logger.error(f"Error processing worker attendance: {e}")
                worker['present_today'] = False
            # Convert all numeric fields to float for JSON serialization
            worker['daily_wage'] = float(worker['daily_wage'])
            worker['wage'] = float(worker['daily_wage'])  # Backwards compatibility for older clients
        
        return jsonify(workers)
    except Exception as e:
        logger.error(f"Error fetching workers: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
@login_required
def get_stats():
    """Get dashboard statistics for workers attendance and payroll.
    
    Returns:
        JSON response containing:
        - On success: Statistics object with total_workers, present_today, total_payroll, and avg_attendance
        - On error: Error object with message and appropriate status code
    """
    try:
        # Get current date and validate workers
        current_date = date.today()
        workers = db.get_workers()
        
        if workers is None:
            raise ValueError("Failed to retrieve workers from database")
            
        if not isinstance(workers, list):
            raise ValueError("Invalid worker data format received from database")
        
        # Initialize statistics
        total_workers = len(workers)
        present_today = 0
        total_payroll = 0.0
        total_attendance_days = 0.0
        today_str = current_date.strftime('%Y-%m-%d')
        
        # Process each worker
        for worker in workers:
            try:
                # Validate worker data
                if 'id' not in worker:
                    logger.warning(f"Worker missing ID field: {worker}")
                    continue
                    
                if 'daily_wage' not in worker:
                    logger.warning(f"Worker {worker.get('id')} missing daily_wage")
                    continue
                
                # Get and validate attendance
                attendance = db.get_attendance(worker['id'], current_date.year, current_date.month)
                if attendance is None:
                    attendance = []
                
                if not isinstance(attendance, list):
                    logger.warning(f"Invalid attendance data for worker {worker['id']}")
                    continue
                
                # Process attendance
                try:
                    daily_wage_float = float(worker['daily_wage'])
                except (TypeError, ValueError):
                    logger.warning(f"Invalid daily wage for worker {worker['id']}")
                    continue
                
                # Check present today
                for record in attendance:
                    try:
                        record_date = record['date'].strftime('%Y-%m-%d') if hasattr(record['date'], 'strftime') else record['date']
                        if record_date == today_str and record['status'] in ['Present', 'Half Day']:
                            present_today += 1
                            break
                    except (AttributeError, KeyError, TypeError) as e:
                        logger.warning(f"Invalid attendance record for worker {worker['id']}: {e}")
                        continue
                
                # Calculate payroll and attendance
                for record in attendance:
                    try:
                        if record['status'] == 'Present':
                            total_payroll += daily_wage_float
                            total_attendance_days += 1
                        elif record['status'] == 'Half Day':
                            total_payroll += daily_wage_float / 2
                            total_attendance_days += 0.5
                    except (KeyError, TypeError) as e:
                        logger.warning(f"Error processing attendance record: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing worker {worker.get('id', 'unknown')}: {e}")
                continue
        
        # Calculate average attendance
        avg_attendance = 0
        if total_workers > 0 and current_date.day > 0:
            avg_attendance = round((total_attendance_days / total_workers / current_date.day) * 100)
            avg_attendance = min(avg_attendance, 100)
        
        return jsonify({
            'total_workers': total_workers,
            'present_today': present_today,
            'total_payroll': float(total_payroll),  # Convert Decimal to float
            'avg_attendance': float(avg_attendance)  # Ensure percentage is float
        })
        
    except ValueError as e:
        # Handle expected errors
        logger.error(f"Validation error in get_stats: {e}")
        return jsonify({'error': str(e)}), 400
        
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error in get_stats: {e}")
        return jsonify({'error': 'An unexpected error occurred while fetching statistics'}), 500

@app.route('/api/delete_worker/<int:worker_id>', methods=['DELETE'])
@login_required
def delete_worker_api(worker_id):
    try:
        db.delete_worker(worker_id)
        return jsonify({'success': True, 'message': 'Worker deleted successfully!'})
    except Exception as e: return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/worker/<int:worker_id>/attendance')
@login_required
def get_worker_attendance(worker_id):
    """Get attendance records for a specific worker.
    
    Args:
        worker_id (int): The ID of the worker
        
    Query Parameters:
        year (int): The year to fetch attendance for (default: current year)
        month (int): The month to fetch attendance for (default: current month)
        
    Returns:
        JSON response containing:
        - On success: List of attendance records with dates, status, wages earned, and Hindu calendar info
        - On error: Error object with message and appropriate status code
    """
    try:
        # Validate input parameters
        try:
            year = request.args.get('year', type=int, default=datetime.now().year)
            month = request.args.get('month', type=int, default=datetime.now().month)
            
            if not (1 <= month <= 12):
                raise ValueError(f"Invalid month: {month}")
            if not (2000 <= year <= 2100):
                raise ValueError(f"Invalid year: {year}")
                
        except ValueError as e:
            return jsonify({'error': f"Invalid date parameters: {str(e)}"}), 400
        
        # Get worker details
        worker = db.get_worker(worker_id)
        if not worker:
            return jsonify({'error': f"Worker not found: {worker_id}"}), 404
            
        # Validate worker data
        if 'daily_wage' not in worker:
            return jsonify({'error': f"Worker {worker_id} has no daily wage set"}), 400
            
        try:
            daily_wage_float = float(worker['daily_wage'])
        except (TypeError, ValueError):
            return jsonify({'error': f"Invalid daily wage for worker {worker_id}"}), 400
        
        # Get attendance records
        attendance = db.get_attendance(worker_id, year, month)
        if attendance is None:
            attendance = []
            
        if not isinstance(attendance, list):
            raise ValueError("Invalid attendance data format received from database")
        
        # Process each attendance record
        processed_records = []
        for record in attendance:
            try:
                # Validate record structure
                if 'date' not in record or 'status' not in record:
                    logger.warning(f"Invalid attendance record for worker {worker_id}: {record}")
                    continue
                
                # Format date
                try:
                    if isinstance(record['date'], str):
                        date_obj = datetime.strptime(record['date'], '%Y-%m-%d').date()
                    else:
                        date_obj = record['date']
                    formatted_date = date_obj.strftime('%Y-%m-%d')
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Invalid date in attendance record: {e}")
                    continue
                
                # Calculate wages
                wage_earned = 0.0
                if record['status'] == 'Present':
                    wage_earned = daily_wage_float
                elif record['status'] == 'Half Day':
                    wage_earned = daily_wage_float / 2
                
                # Get Hindu calendar info
                try:
                    panchang = hindu_calendar.get_panchang_summary(date_obj)
                except Exception as e:
                    logger.warning(f"Error getting panchang for {formatted_date}: {e}")
                    panchang = None
                
                # Create processed record
                processed_records.append({
                    'date': formatted_date,
                    'status': record['status'],
                    'wage_earned': float(wage_earned),  # Ensure wage is float
                    'hindu_date': panchang
                })
                
            except Exception as e:
                logger.error(f"Error processing attendance record: {e}")
                continue
        
        return jsonify(processed_records)
        
    except ValueError as e:
        # Handle expected errors
        logger.error(f"Validation error in get_worker_attendance: {e}")
        return jsonify({'error': str(e)}), 400
        
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error in get_worker_attendance: {e}")
        return jsonify({'error': 'An unexpected error occurred while fetching attendance records'}), 500

@app.route('/api/worker/<int:worker_id>/advances')
@login_required
def get_worker_advances(worker_id):
    try:
        year = request.args.get('year', type=int, default=datetime.now().year)
        month = request.args.get('month', type=int, default=datetime.now().month)
        advances = db.get_advances(worker_id, year, month)
        for advance in advances:
            advance['date'] = advance['date'].strftime('%Y-%m-%d')
            advance['amount'] = float(advance['amount'])
        return jsonify(advances)
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/mark_attendance', methods=['POST'])
@login_required
def mark_attendance_api():
    try:
        data = request.get_json()
        worker_id = data.get('worker_id')
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
    attendance = db.get_attendance(worker_id, year, month)
    advances = db.get_advances(worker_id, year, month)
    # Ensure attendance is a list
    if not isinstance(attendance, list):
        attendance = []
    if not isinstance(advances, list):
        advances = []
        
    present_days = len([a for a in attendance if a['status'] == 'Present'])
    absent_days = len([a for a in attendance if a['status'] == 'Absent'])
    total_working_days = len(attendance)
    daily_wage_float = float(worker.get('daily_wage', 0))
    total_earnings = present_days * daily_wage_float
    total_advances = sum(float(a.get('amount', 0)) for a in advances)
    net_salary = total_earnings - total_advances
    return jsonify({
        'present_days': present_days,
        'absent_days': absent_days,
        'total_working_days': total_working_days,
        'total_earnings': float(total_earnings),  # Convert Decimal to float
        'total_advances': float(total_advances),  # Convert Decimal to float
        'net_salary': float(net_salary),         # Convert Decimal to float
        'month_name': calendar.month_name[month],
        'year': year
    })

@app.route('/api/add_advance/<int:worker_id>', methods=['POST'])
@login_required
def add_advance_api(worker_id):
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

@app.route('/api/update_worker/<int:worker_id>', methods=['PUT'])
@login_required
def update_worker_api(worker_id):
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
    try:
        data = request.get_json()
        worker_id = data.get('worker_id')
        amount = float(data.get('amount'))
        date_str = data.get('date')
        note = data.get('note', '')
        db.add_advance(worker_id, amount, date_str, note)
        return jsonify({'success': True, 'message': f'Advance of ₹{amount} given successfully!'})
    except Exception as e: return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/add_worker', methods=['POST'])
@login_required
def add_worker():
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

@app.route('/api/panchang')
@login_required
def get_panchang():
    try:
        date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        panchang_info = hindu_calendar.get_panchang_summary(target_date)
        return jsonify(panchang_info)
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/holidays', methods=['GET'])
@login_required
def get_holidays_api():
    try:
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        holidays = db.get_holidays(year, month)
        for h in holidays: h['date'] = h['date'].strftime('%Y-%m-%d')
        return jsonify(holidays)
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/holidays', methods=['POST'])
@login_required
def add_holiday_api():
    try:
        data = request.get_json()
        db.add_holiday(data.get('date'), data.get('name'), data.get('type', 'manual'), data.get('description', ''))
        return jsonify({'success': True, 'message': 'Holiday added successfully!'})
    except ValueError as e: return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e: return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/holidays/<int:holiday_id>', methods=['DELETE'])
@login_required
def delete_holiday_api(holiday_id):
    try:
        db.delete_holiday(holiday_id)
        return jsonify({'success': True, 'message': 'Holiday deleted successfully!'})
    except Exception as e: return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/reports/payroll')
@login_required
def get_payroll_report():
    try:
        year = request.args.get('year', type=int, default=datetime.now().year)
        month = request.args.get('month', type=int, default=datetime.now().month)
        workers = db.get_workers()
        report_data = []
        total_payroll, total_advances, total_net = 0.0, 0.0, 0.0
        
        for worker in workers:
            # Ensure numeric values are converted to float
            daily_wage = float(worker['daily_wage'])
            
            attendance = db.get_attendance(worker['id'], year, month)
            advances = db.get_advances(worker['id'], year, month)
            
            # Calculate attendance stats
            present_days = len([a for a in attendance if a['status'] == 'Present'])
            half_days = len([a for a in attendance if a['status'] == 'Half Day'])
            total_days = present_days + (half_days * 0.5)
            
            # Calculate salary components
            gross_salary = (present_days * daily_wage) + (half_days * daily_wage / 2)
            worker_advances = sum(float(a['amount']) for a in advances)
            net_salary = gross_salary - worker_advances
            
            # Update totals
            total_payroll += gross_salary
            total_advances += worker_advances
            total_net += net_salary
            
            # Ensure all numeric values are explicitly converted to float
            report_data.append({
                'worker_id': worker['id'], 
                'worker_name': worker['name'], 
                'daily_wage': float(daily_wage), 
                'present_days': present_days, 
                'half_days': half_days, 
                'total_days': float(total_days), 
                'gross_salary': float(gross_salary), 
                'advances': float(worker_advances), 
                'net_salary': float(net_salary)
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
        print(f"Error in payroll report: {str(e)}") # Debug logging
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/attendance')
@login_required
def get_attendance_report():
    try:
        year = request.args.get('year', type=int, default=datetime.now().year)
        month = request.args.get('month', type=int, default=datetime.now().month)
        workers = db.get_workers()
        report_data = []
        holidays = db.get_holidays(year, month)
        holiday_dates = [h['date'].strftime('%Y-%m-%d') for h in holidays]
        _, days_in_month = calendar.monthrange(year, month)
        for worker in workers:
            attendance = db.get_attendance(worker['id'], year, month)
            attendance_dict = {a['date'].strftime('%Y-%m-%d'): a['status'] for a in attendance}
            present_count, absent_count, holiday_count, half_day_count = 0, 0, 0, 0
            for day in range(1, days_in_month + 1):
                date_str = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
                if date_str in holiday_dates:
                    holiday_count += 1
                elif date_str in attendance_dict:
                    if attendance_dict[date_str] == 'Present':
                        present_count += 1
                    elif attendance_dict[date_str] == 'Half Day':
                        half_day_count += 1
                    elif attendance_dict[date_str] == 'Absent':
                        absent_count += 1
                    else:
                        # If status is not recognized, treat as absent for now
                        absent_count += 1
                else:
                    # This logic assumes non-marked, non-holiday days are absent.
                    absent_count += 1
            working_days = days_in_month - holiday_count
            attendance_percentage = ((present_count + (half_day_count * 0.5)) / working_days) * 100 if working_days > 0 else 0
            report_data.append({
                'worker_id': worker['id'], 
                'worker_name': worker['name'], 
                'present_days': present_count, 
                'half_days': half_day_count, 
                'absent_days': absent_count, 
                'holidays': holiday_count, 
                'total_working_days': working_days, 
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
        print(f"Error in attendance report: {str(e)}") # Debug logging
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)



