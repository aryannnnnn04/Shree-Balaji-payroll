import os
import logging
from psycopg2.pool import SimpleConnectionPool
import psycopg2
from datetime import datetime
from functools import wraps
from flask import Flask, request, render_template, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from api.hindu_calendar import get_hindu_holidays as fetch_hindu_holidays

# Configure logging
logging.basicConfig(level=logging.INFO)

class Cache:
    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value

    def delete(self, key):
        if key in self.cache:
            del self.cache[key]

class Database:
    def __init__(self):
        self.pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=os.environ.get("BLAZECORE_PAYROLL_DATABASE_URL")
        )

    def get_connection(self):
        return self.pool.getconn()

    def release_connection(self, conn):
        self.pool.putconn(conn)

    def execute_query(self, query, params=None, fetch=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch == 'one':
                    result = cur.fetchone()
                elif fetch == 'all':
                    result = cur.fetchall()
                else:
                    result = None
                conn.commit()
                return result
        except psycopg2.Error as e:
            logging.error(f"Database query failed: {e}")
            conn.rollback()
            return None
        finally:
            self.release_connection(conn)

    def execute_script(self, script):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(script)
                conn.commit()
        except psycopg2.Error as e:
            logging.error(f"Database script execution failed: {e}")
            conn.rollback()
        finally:
            self.release_connection(conn)

    def get_user_by_username(self, username):
        query = "SELECT * FROM users WHERE username = %s;"
        return self.execute_query(query, (username,), fetch='one')

    def get_user_by_id(self, user_id):
        query = "SELECT * FROM users WHERE id = %s;"
        return self.execute_query(query, (user_id,), fetch='one')

    def close_all_connections(self):
        self.pool.closeall()

    def get_all_users(self):
        query = "SELECT id, username, role, created_at FROM users;"
        return self.execute_query(query, fetch='all')

    def get_all_user_data(self):
        query = "SELECT id, name, position, salary, hire_date FROM users;"
        return self.execute_query(query, fetch='all')

    def add_user(self, name, position, salary, hire_date, username, password, role):
        hashed_password = generate_password_hash(password)
        query = """
            INSERT INTO users (name, position, salary, hire_date, username, password, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        params = (name, position, salary, hire_date, username, hashed_password, role)
        self.execute_query(query, params)

    def update_user(self, user_id, name, position, salary, hire_date, username, role):
        query = """
            UPDATE users
            SET name = %s, position = %s, salary = %s, hire_date = %s, username = %s, role = %s
            WHERE id = %s;
        """
        params = (name, position, salary, hire_date, username, role, user_id)
        self.execute_query(query, params)

    def delete_user(self, user_id):
        query = "DELETE FROM users WHERE id = %s;"
        self.execute_query(query, (user_id,))


app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key')
db = Database()
cache = Cache()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = db.get_user_by_username(username)
        if user and check_password_hash(user[6], password):
            session['user_id'] = user[0]
            session['username'] = user[5]
            session['role'] = user[7]
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    workers = db.get_all_user_data()
    return render_template('dashboard.html', workers=workers)

@app.route('/worker_details/<int:worker_id>')
@login_required
def worker_details(worker_id):
    user = db.get_user_by_id(worker_id)
    if user:
        return render_template('worker_details.html', worker=user)
    else:
        flash('Worker not found.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/add_worker', methods=['GET', 'POST'])
@login_required
def add_worker():
    if request.method == 'POST':
        name = request.form['name']
        position = request.form['position']
        salary = request.form['salary']
        hire_date = request.form['hire_date']
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        db.add_user(name, position, salary, hire_date, username, password, role)
        flash('Worker added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_worker.html')

@app.route('/update_worker/<int:worker_id>', methods=['GET', 'POST'])
@login_required
def update_worker(worker_id):
    if request.method == 'POST':
        name = request.form['name']
        position = request.form['position']
        salary = request.form['salary']
        hire_date = request.form['hire_date']
        username = request.form['username']
        role = request.form['role']
        db.update_user(worker_id, name, position, salary, hire_date, username, role)
        flash('Worker updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    user = db.get_user_by_id(worker_id)
    if user:
        return render_template('update_worker.html', worker=user)
    else:
        flash('Worker not found.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/delete_worker/<int:worker_id>', methods=['POST'])
@login_required
def delete_worker(worker_id):
    db.delete_user(worker_id)
    flash('Worker deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')

@app.route('/get_hindu_holidays')
@login_required
def get_hindu_holidays():
    year = datetime.now().year
    holidays = cache.get(f'hindu_holidays_{year}')
    if not holidays:
        holidays = fetch_hindu_holidays(year)
        cache.set(f'hindu_holidays_{year}', holidays)
    return jsonify(holidays)

if __name__ == '__main__':
    app.run(debug=True)