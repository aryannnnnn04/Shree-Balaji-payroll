import os
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from datetime import datetime, date
import calendar
import json
from hindu_calendar import HinduCalendar # Corrected import
from functools import wraps
import secrets

# --- This is the corrected Flask app definition with absolute paths ---
_cwd = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            static_folder=os.path.join(_cwd, '../static'),
            template_folder=os.path.join(_cwd, '../templates'))

# --- Configure the Flask app ---
# It's better to get the secret key from an environment variable for security
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


# --- This is the new, final Database class for Neon (PostgreSQL) ---
class Database:
    def __init__(self):
        # This reads the secret connection URL that Vercel provides
        self.db_url = os.environ.get("POSTGRES_URL")
        if not self.db_url:
            raise Exception("POSTGRES_URL environment variable not set")
        # The create_tables() function will be called once when the app starts
        # self.create_tables() # You may want to run this manually or check if tables exist

    def get_connection(self):
        """Establishes a connection to the PostgreSQL database."""
        return psycopg2.connect(self.db_url)

    # --- Add all your database functions below, converted for PostgreSQL ---
    # For example:
    def get_workers(self):
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SELECT * FROM workers ORDER BY name")
                workers = [dict(row) for row in cur.fetchall()]
            return workers
        finally:
            conn.close()
            
    # --- IMPORTANT ---
    # You will need to add ALL your other database functions (add_worker, mark_attendance, etc.) here.
    # Make sure you replace all SQLite '?' placeholders with PostgreSQL '%s' placeholders in your SQL queries.


# --- Create the single, global database object ---
db = Database()


# --- All your @app.route functions go below this line ---

@app.route('/')
def home():
    # A good home route redirects to the main functionality, like the login page
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # This is just a placeholder - replace with your actual login logic
    # For now, it just shows the login page
    return render_template('login.html')

# --- IMPORTANT ---
# You will need to add ALL your other Flask routes (@app.route('/dashboard'), etc.) here.

# This allows the app to be run for local development as well
if __name__ == "__main__":
    app.run(debug=True)