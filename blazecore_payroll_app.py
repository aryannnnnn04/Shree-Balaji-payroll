import tkinter as tk
from tkinter import messagebox, Toplevel
from datetime import datetime
import calendar
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import sqlite3

class ModernStyle:
    """Modern color palette and styling constants."""
    # Color Palette
    PRIMARY_BG = "#111827"        # Very dark charcoal
    CONTENT_BG = "#1F2937"        # Slightly lighter dark gray
    ACCENT_PRIMARY = "#F97316"    # BlazeCore Orange
    ACCENT_SECONDARY = "#9CA3AF"  # Light gray
    TEXT_PRIMARY = "#FFFFFF"      # White
    STATUS_SUCCESS = "#22C55E"    # Modern green
    STATUS_DANGER = "#EF4444"     # Modern red
    STATUS_WARNING = "#F59E0B"    # Modern amber
    
    # Typography
    FONT_FAMILY = "Segoe UI"
    FONT_H1 = (FONT_FAMILY, 24, "bold")
    FONT_H2 = (FONT_FAMILY, 18, "bold")
    FONT_CARD_TITLE = (FONT_FAMILY, 16, "bold")
    FONT_BODY = (FONT_FAMILY, 14, "normal")
    FONT_SUBTLE = (FONT_FAMILY, 12, "normal")
    
    # Spacing
    MAIN_PADDING = 20
    CARD_PADDING = 15
    ELEMENT_GAP = 10
    BORDER_RADIUS = 12
    BUTTON_RADIUS = 8

class Icons:
    """Minimalist icon collection."""
    BACK = "❮"
    FORWARD = "➔"
    ADD = "+"
    PERSON = "👤"
    TEAM = "👥"
    MONEY = "💰"
    CALENDAR = "📅"
    CHECK = "✓"
    CROSS = "✗"
    CLOCK = "⏰"
    CHART = "📊"
    SETTINGS = "⚙"

class Database:
    """Handles all database operations for the application."""
    _instance = None
    _connection_pool = {}
    
    def __new__(cls, db_name="blazecore_payroll.db"):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.db_name = db_name
            cls._instance._init_connection()
        return cls._instance
    
    def _init_connection(self):
        """Initialize database connection with optimized settings"""
        self.conn = sqlite3.connect(
            self.db_name,
            timeout=30,  # Increased timeout for busy database
            isolation_level=None  # Enable autocommit mode
        )
        # Enable WAL mode for better concurrent access
        self.conn.execute("PRAGMA journal_mode=WAL")
        # Optimize for better performance
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=10000")
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Create the necessary tables if they don't exist."""
        with self.conn:  # Use context manager for automatic commit/rollback
            # Create workers table with indexed name for faster lookups
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS workers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL COLLATE NOCASE,
                    daily_wage REAL NOT NULL,
                    active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_worker_name ON workers(name)')
            
            # Create attendance table with indexes for common queries
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id INTEGER,
                    date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (worker_id) REFERENCES workers (id),
                    UNIQUE(worker_id, date)
                )
            ''')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_worker_date ON attendance(worker_id, date)')
            
            # Create advances table with indexes for financial queries
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS advances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id INTEGER,
                    amount REAL NOT NULL,
                    date TEXT NOT NULL,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (worker_id) REFERENCES workers (id)
                )
            ''')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_advances_date ON advances(date)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_advances_worker_date ON advances(worker_id, date)')

    def add_worker(self, name, daily_wage):
        """Add a new worker with validation."""
        if not name or not str(name).strip():
            raise ValueError("Worker name cannot be empty")
        if not isinstance(daily_wage, (int, float)) or daily_wage <= 0:
            raise ValueError("Daily wage must be a positive number")
        
        name = str(name).strip()
        
        with self.conn:  # Use context manager for automatic transaction handling
            # Check for duplicate names using indexed column
            self.cursor.execute("SELECT id FROM workers WHERE name = ? AND active = 1", (name,))
            if self.cursor.fetchone():
                raise ValueError(f"Worker '{name}' already exists")
            
            # Insert new worker with current timestamp
            self.cursor.execute(
                "INSERT INTO workers (name, daily_wage, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (name, daily_wage)
            )
            return self.cursor.lastrowid

    def get_workers(self, active_only=True):
        """Get all workers with optional filtering."""
        query = """
            SELECT id, name, daily_wage, created_at 
            FROM workers 
            WHERE active = ? 
            ORDER BY name
        """
        self.cursor.execute(query, (1 if active_only else 0,))
        return [dict(zip(['id', 'name', 'daily_wage', 'created_at'], row)) 
                for row in self.cursor.fetchall()]

    def mark_attendance(self, worker_id, date_str, status):
        """Mark or update worker attendance with improved error handling."""
        valid_statuses = {'present', 'absent', 'half-day', 'unmarked'}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            
        with self.conn:  # Use transaction
            # First verify worker exists and is active
            self.cursor.execute("SELECT 1 FROM workers WHERE id = ? AND active = 1", (worker_id,))
            if not self.cursor.fetchone():
                raise ValueError("Worker not found or inactive")
            
            if status == 'unmarked':
                self.cursor.execute(
                    "DELETE FROM attendance WHERE worker_id = ? AND date(date) = ?",
                    (worker_id, date_str)
                )
            else:
                # Use UPSERT for cleaner code and better performance
                self.cursor.execute("""
                    INSERT INTO attendance (worker_id, date, status, created_at) 
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(worker_id, date) 
                    DO UPDATE SET status = excluded.status, created_at = CURRENT_TIMESTAMP
                """, (worker_id, date_str, status))

    def get_attendance_for_month(self, worker_id, month, year):
        """Get monthly attendance with optimized query and error checking."""
        # Validate input
        if not (1 <= month <= 12 and 1900 <= year <= 9999):
            raise ValueError("Invalid month or year")
            
        month_str = f"{year}-{str(month).zfill(2)}"
        
        # Use indexed columns for better performance
        query = """
            SELECT date, status 
            FROM attendance 
            WHERE worker_id = ? 
            AND strftime('%Y-%m', date) = ?
            AND EXISTS (SELECT 1 FROM workers WHERE id = worker_id AND active = 1)
        """
        
        self.cursor.execute(query, (worker_id, month_str))
        return {
            datetime.strptime(d.split(' ')[0], '%Y-%m-%d').day: s 
            for d, s in self.cursor.fetchall()
        }

    def add_advance(self, worker_id, amount, date_str, notes=None):
        """Add advance payment with enhanced validation and error handling."""
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Advance amount must be a positive number")
        if amount > 50000:  # Reasonable upper limit
            raise ValueError("Advance amount seems too high (max: ₹50,000)")
            
        with self.conn:
            # Verify worker exists and is active
            self.cursor.execute("SELECT daily_wage FROM workers WHERE id = ? AND active = 1", (worker_id,))
            worker = self.cursor.fetchone()
            if not worker:
                raise ValueError("Worker not found or inactive")
                
            # Check if total advances for the month don't exceed monthly wage
            daily_wage = worker[0]
            month_str = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m')
            
            self.cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) 
                FROM advances 
                WHERE worker_id = ? AND strftime('%Y-%m', date) = ?
            """, (worker_id, month_str))
            
            current_advances = self.cursor.fetchone()[0] or 0
            days_in_month = calendar.monthrange(int(month_str[:4]), int(month_str[5:]))[1]
            max_possible_wage = daily_wage * days_in_month
            
            if current_advances + amount > max_possible_wage:
                raise ValueError(f"Total advances ({current_advances + amount}) would exceed maximum monthly wage ({max_possible_wage})")
            
            # Insert advance with audit trail
            self.cursor.execute("""
                INSERT INTO advances (worker_id, amount, date, notes, created_at) 
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (worker_id, amount, date_str, notes))
            
            return self.cursor.lastrowid

    def get_advances_for_month(self, worker_id, month, year):
        """Get monthly advances with improved error handling and caching."""
        if not (1 <= month <= 12 and 1900 <= year <= 9999):
            raise ValueError("Invalid month or year")
            
        month_str = f"{year}-{str(month).zfill(2)}"
        
        # Use optimized query with worker existence check
        query = """
            SELECT COALESCE(SUM(amount), 0) 
            FROM advances a
            WHERE a.worker_id = ? 
            AND strftime('%Y-%m', a.date) = ?
            AND EXISTS (SELECT 1 FROM workers w WHERE w.id = a.worker_id AND w.active = 1)
        """
        
        self.cursor.execute(query, (worker_id, month_str))
        return self.cursor.fetchone()[0] or 0.0

    def get_advance_history(self, worker_id, limit=10):
        """Get recent advance history for a worker."""
        query = """
            SELECT a.date, a.amount, a.notes, a.created_at
            FROM advances a
            WHERE a.worker_id = ?
            ORDER BY a.date DESC, a.created_at DESC
            LIMIT ?
        """
        
        self.cursor.execute(query, (worker_id, limit))
        return [dict(zip(['date', 'amount', 'notes', 'created_at'], row)) 
                for row in self.cursor.fetchall()]

    def __enter__(self):
        """Enable context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources properly."""
        if hasattr(self, 'conn'):
            try:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
                self.conn.close()
            except Exception:
                pass

class App(ttkb.Window):
    """The main application window with modern dark theme."""
    def __init__(self):
        super().__init__(themename="darkly")
        self.db = Database()
        self.title("BlazeCore Payroll Manager")
        self.geometry("900x700")
        self.minsize(800, 600)
        self.configure(bg=ModernStyle.PRIMARY_BG)

        # Configure grid weights for responsiveness
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Create custom styles
        self.setup_custom_styles()

        # Bind keyboard shortcuts
        self.bind('<Control-n>', lambda e: self.frames["dashboardframe"].open_add_worker_popup())
        self.bind('<Control-q>', lambda e: self.quit())
        self.bind('<F1>', self.show_help)
        self.bind('<Escape>', lambda e: self.show_frame("dashboardframe"))

        container = ttkb.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (DashboardFrame, WorkerView):
            page_name = F.__name__.lower()
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        self.show_frame("dashboardframe")
        
    def setup_custom_styles(self):
        """Setup custom styles for modern appearance."""
        style = ttkb.Style()

        # Configure modern card style
        style.configure(
            "Modern.TFrame",
            background=ModernStyle.CONTENT_BG,
            relief="flat",
            borderwidth=1
        )

        # Configure modern button styles
        style.configure(
            "ModernPrimary.TButton",
            background=ModernStyle.ACCENT_PRIMARY,
            foreground=ModernStyle.TEXT_PRIMARY,
            borderwidth=0,
            font=ModernStyle.FONT_BODY
        )

        style.configure(
            "ModernSecondary.TButton",
            background="transparent",
            foreground=ModernStyle.ACCENT_PRIMARY,
            borderwidth=1,
            font=ModernStyle.FONT_BODY
        )
        
    def show_help(self, event=None):
        """Show keyboard shortcuts help."""
        help_text = """🚀 BlazeCore Payroll Manager - Keyboard Shortcuts:

⌨️ Navigation:
• Ctrl+N - Add new worker
• F1 - Show this help
• Escape - Return to dashboard
• Ctrl+Q - Quit application

📅 Calendar:
• Click dates to cycle: Unmarked → Present → Absent
• Use arrow buttons to navigate months

📊 Features:
• Monthly summary with navigation
• Automatic calculations
• Input validation
• Data persistence"""
        
        messagebox.showinfo("Help - Keyboard Shortcuts", help_text)

    def show_frame(self, page_name, worker_data=None):
        frame = self.frames[page_name]
        if worker_data:
            frame.set_worker_data(worker_data)
        frame.tkraise()

class DashboardFrame(ttkb.Frame):
    """Modern dashboard with clean worker cards."""
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        self.configure(style="Modern.TFrame")

        # Main container with proper padding
        main_container = ttkb.Frame(self)
        main_container.pack(fill=BOTH, expand=True, padx=ModernStyle.MAIN_PADDING, pady=ModernStyle.MAIN_PADDING)

        # Clean header - just logo and title
        self.create_header(main_container)

        # Team section
        self.create_team_section(main_container)
        
    def create_header(self, parent):
        """Create clean, minimal header."""
        header_frame = ttkb.Frame(parent)
        header_frame.pack(fill=X, pady=(0, 30))

        # Simple logo and title
        title_frame = ttkb.Frame(header_frame)
        title_frame.pack(anchor=W)

        ttkb.Label(title_frame, text="BlazeCore", 
                   font=ModernStyle.FONT_H1, 
                   foreground=ModernStyle.TEXT_PRIMARY).pack(anchor=W)

        ttkb.Label(title_frame, text="Payroll Management", 
                   font=ModernStyle.FONT_SUBTLE, 
                   foreground=ModernStyle.ACCENT_SECONDARY).pack(anchor=W, pady=(0, 0))
        
    def create_team_section(self, parent):
        """Create the team members section."""
        # Section header
        header_container = ttkb.Frame(parent)
        header_container.pack(fill=X, pady=(0, ModernStyle.ELEMENT_GAP))

        ttkb.Label(header_container, text="Team Members", 
                   font=ModernStyle.FONT_H2, 
                   foreground=ModernStyle.TEXT_PRIMARY).pack(side=LEFT)

        # Add Worker button - modern primary style
        add_btn = ttkb.Button(header_container, 
                             text=f"{Icons.ADD} Add Worker",
                             style="ModernPrimary.TButton",
                             command=self.open_add_worker_popup)
        add_btn.pack(side=RIGHT)

        # Worker list container
        self.worker_list_frame = ttkb.Frame(parent)
        self.worker_list_frame.pack(fill=BOTH, expand=True, pady=(ModernStyle.ELEMENT_GAP, 0))

        self.populate_workers()

    def populate_workers(self):
        """Populate worker list with modern clean cards."""
        for widget in self.worker_list_frame.winfo_children():
            widget.destroy()

        workers = self.db.get_workers()
        if not workers:
            self.create_empty_state()
            return

        for worker in workers:
            self.create_worker_card(worker)
            
    def create_empty_state(self):
        """Create clean empty state."""
        empty_container = ttkb.Frame(self.worker_list_frame)
        empty_container.pack(expand=True, fill=BOTH)

        # Center the empty state content
        empty_content = ttkb.Frame(empty_container)
        empty_content.place(relx=0.5, rely=0.5, anchor=CENTER)

        # Large icon
        ttkb.Label(empty_content, text=Icons.TEAM, 
                   font=(ModernStyle.FONT_FAMILY, 48), 
                   foreground=ModernStyle.ACCENT_SECONDARY).pack(pady=(0, 20))

        # Title
        ttkb.Label(empty_content, text="No Team Members Yet", 
                   font=ModernStyle.FONT_H2, 
                   foreground=ModernStyle.TEXT_PRIMARY).pack(pady=(0, 8))

        # Description
        ttkb.Label(empty_content, text="Add your first worker to get started", 
                   font=ModernStyle.FONT_BODY, 
                   foreground=ModernStyle.ACCENT_SECONDARY).pack(pady=(0, 24))

        # Call-to-action button
        ttkb.Button(empty_content, text=f"{Icons.ADD} Add First Worker", 
                    style="ModernPrimary.TButton",
                    command=self.open_add_worker_popup).pack()
                  
    def create_worker_card(self, worker):
        """Create a clean, modern worker card."""
        # Card container with modern styling
        card_container = ttkb.Frame(self.worker_list_frame, style="Modern.TFrame")
        card_container.pack(fill=X, pady=(0, ModernStyle.ELEMENT_GAP))

        # Inner card content with padding
        card_content = ttkb.Frame(card_container)
        card_content.pack(fill=X, padx=ModernStyle.CARD_PADDING, pady=ModernStyle.CARD_PADDING)

        # Left side - Worker info
        info_frame = ttkb.Frame(card_content)
        info_frame.pack(side=LEFT, fill=X, expand=True)

        # Worker name - most prominent
        name_frame = ttkb.Frame(info_frame)
        name_frame.pack(anchor=W, fill=X)

        ttkb.Label(name_frame, text=Icons.PERSON, 
                   font=ModernStyle.FONT_BODY, 
                   foreground=ModernStyle.ACCENT_SECONDARY).pack(side=LEFT, padx=(0, 8))

        ttkb.Label(name_frame, text=worker[1], 
                   font=ModernStyle.FONT_CARD_TITLE, 
                   foreground=ModernStyle.TEXT_PRIMARY).pack(side=LEFT)

        # Daily wage - clear and prominent
        wage_frame = ttkb.Frame(info_frame)
        wage_frame.pack(anchor=W, pady=(4, 0))

        ttkb.Label(wage_frame, text=f"₹{worker[2]:,.0f}/day", 
                   font=ModernStyle.FONT_BODY, 
                   foreground=ModernStyle.ACCENT_SECONDARY).pack(side=LEFT)

        # Right side - Action button
        action_frame = ttkb.Frame(card_content)
        action_frame.pack(side=RIGHT)

        # Clean arrow button
        ttkb.Button(action_frame, text=f"View Details {Icons.FORWARD}", 
                    style="ModernSecondary.TButton",
                    command=lambda w=worker: self.controller.show_frame("workerview", worker_data=w)).pack()
                  
    def open_add_worker_popup(self):
        """Open modern add worker popup."""
        popup = ModernPopup(self.controller, "Add New Worker", "Enter worker details")
        popup.add_field("Worker Name", "name")
        popup.add_field("Daily Wage (₹)", "wage", "number")
        
        def save_worker(data):
            name = data["name"]
            wage = data["wage"]
            
            # Validation
            if not name:
                messagebox.showerror("Invalid Input", "Please enter a worker name")
                return False
                
            if len(name) < 2:
                messagebox.showerror("Invalid Input", "Worker name must be at least 2 characters long")
                return False
                
            if not wage:
                messagebox.showerror("Invalid Input", "Please enter a daily wage")
                return False
                
            try:
                wage_float = float(wage)
                if wage_float <= 0:
                    messagebox.showerror("Invalid Input", "Daily wage must be greater than 0")
                    return False
                if wage_float > 5000:
                    messagebox.showerror("Invalid Input", "Daily wage seems too high (max: ₹5,000)")
                    return False
                    
                self.db.add_worker(name, wage_float)
                self.populate_workers()
                messagebox.showinfo("Success", f"Worker '{name}' added successfully!")
                return True
                
            except ValueError as e:
                if "already exists" in str(e):
                    messagebox.showerror("Duplicate Worker", str(e))
                else:
                    messagebox.showerror("Invalid Input", "Please enter a valid number for wage")
                return False
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add worker: {str(e)}")
                return False
                
        popup.set_callback(save_worker)
        popup.show()

class ModernPopup:
    """Modern popup dialog with clean styling."""
    def __init__(self, parent, title, subtitle=""):
        self.parent = parent
        self.title = title
        self.subtitle = subtitle
        self.fields = []
        self.callback = None
        
    def add_field(self, label, key, field_type="text"):
        """Add a field to the popup."""
        self.fields.append({
            "label": label,
            "key": key,
            "type": field_type
        })
        
    def set_callback(self, callback):
        """Set the callback function for form submission."""
        self.callback = callback
        
    def show(self):
        """Show the popup dialog."""
        popup = Toplevel(self.parent)
        popup.title(self.title)
        popup.geometry("400x300")
        popup.resizable(False, False)
        popup.transient(self.parent)
        popup.grab_set()
        popup.configure(bg=ModernStyle.PRIMARY_BG)

        # Center the popup
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (popup.winfo_width() // 2)
        y = (popup.winfo_screenheight() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")

        # Main container
        main_frame = ttkb.Frame(popup)
        main_frame.pack(fill=BOTH, expand=True, padx=ModernStyle.MAIN_PADDING, pady=ModernStyle.MAIN_PADDING)

        # Header
        header_frame = ttkb.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 30))

        ttkb.Label(header_frame, text=self.title, 
                   font=ModernStyle.FONT_H2, 
                   foreground=ModernStyle.TEXT_PRIMARY).pack(anchor=W)

        if self.subtitle:
            ttkb.Label(header_frame, text=self.subtitle, 
                       font=ModernStyle.FONT_SUBTLE, 
                       foreground=ModernStyle.ACCENT_SECONDARY).pack(anchor=W, pady=(4, 0))

        # Form fields
        form_frame = ttkb.Frame(main_frame)
        form_frame.pack(fill=X, pady=(0, 30))

        entries = {}
        for i, field in enumerate(self.fields):
            # Field label
            ttkb.Label(form_frame, text=field["label"], 
                       font=ModernStyle.FONT_BODY, 
                       foreground=ModernStyle.TEXT_PRIMARY).pack(anchor=W, pady=(0 if i == 0 else 20, 5))

            # Field entry
            entry = ttkb.Entry(form_frame, font=ModernStyle.FONT_BODY)
            entry.pack(fill=X, ipady=8)
            entries[field["key"]] = entry

            if i == 0:
                entry.focus_set()

        # Buttons
        button_frame = ttkb.Frame(main_frame)
        button_frame.pack(fill=X)

        def on_submit():
            data = {key: entry.get().strip() for key, entry in entries.items()}
            if self.callback and self.callback(data):
                popup.destroy()

        def on_cancel():
            popup.destroy()

        ttkb.Button(button_frame, text="Cancel", 
                    style="ModernSecondary.TButton",
                    command=on_cancel).pack(side=LEFT)

        ttkb.Button(button_frame, text="Save", 
                    style="ModernPrimary.TButton",
                    command=on_submit).pack(side=RIGHT)

        # Bind keys
        popup.bind('<Escape>', lambda e: on_cancel())
        popup.bind('<Return>', lambda e: on_submit())

class WorkerView(ttkb.Frame):
    """Modern worker details view."""
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = controller.db
        self.worker_data = None
        self.current_month = datetime.now().month
        self.current_year = datetime.now().year

    def set_worker_data(self, worker_data):
        self.worker_data = worker_data
        self.current_month = datetime.now().month
        self.current_year = datetime.now().year
        self.render()

    def render(self):
        """Render the modern worker view."""
        for widget in self.winfo_children():
            widget.destroy()

        if not self.worker_data:
            return

        # Main container with proper padding
        main_container = ttkb.Frame(self)
        main_container.pack(fill=BOTH, expand=True, padx=ModernStyle.MAIN_PADDING, pady=ModernStyle.MAIN_PADDING)

        # Clean header with back button and worker name
        self.create_header(main_container)

        # Worker info card
        self.create_worker_info_card(main_container)

        # Action buttons
        self.create_action_buttons(main_container)

        # Summary section
        self.create_summary_section(main_container)
        
    def create_header(self, parent):
        """Create clean header with back navigation."""
        header_frame = ttkb.Frame(parent)
        header_frame.pack(fill=X, pady=(0, 30))

        # Back button
        ttkb.Button(header_frame, text=f"{Icons.BACK} Back", 
                    style="ModernSecondary.TButton",
                    command=lambda: self.controller.show_frame("dashboardframe")).pack(side=LEFT)

        # Worker name as main title
        ttkb.Label(header_frame, text=self.worker_data[1], 
                   font=ModernStyle.FONT_H1, 
                   foreground=ModernStyle.TEXT_PRIMARY).pack(side=LEFT, padx=(20, 0))
                 
    def create_worker_info_card(self, parent):
        """Create worker information card."""
        card_container = ttkb.Frame(parent, style="Modern.TFrame")
        card_container.pack(fill=X, pady=(0, ModernStyle.ELEMENT_GAP))

        card_content = ttkb.Frame(card_container)
        card_content.pack(fill=X, padx=ModernStyle.CARD_PADDING, pady=ModernStyle.CARD_PADDING)

        # Worker icon and details
        info_row = ttkb.Frame(card_content)
        info_row.pack(fill=X)

        # Icon
        ttkb.Label(info_row, text=Icons.PERSON, 
                   font=(ModernStyle.FONT_FAMILY, 24), 
                   foreground=ModernStyle.ACCENT_SECONDARY).pack(side=LEFT, padx=(0, 15))

                  
    def create_summary_section(self, parent):
        """Create the summary section with month navigation."""
        # Month navigation header
        nav_frame = ttkb.Frame(parent)
        nav_frame.pack(fill=X, pady=(0, ModernStyle.ELEMENT_GAP))

        ttkb.Button(nav_frame, text="◀", 
                    style="ModernSecondary.TButton",
                    command=self.prev_month).pack(side=LEFT)

        month_label = ttkb.Label(nav_frame, 
                                 text=f"{calendar.month_name[self.current_month]} {self.current_year}",
                                 font=ModernStyle.FONT_H2,
                                 foreground=ModernStyle.TEXT_PRIMARY)
        month_label.pack(side=LEFT, expand=True)

        ttkb.Button(nav_frame, text="▶", 
                    style="ModernSecondary.TButton",
                    command=self.next_month).pack(side=RIGHT)

        # Summary card
        self.summary_card = ttkb.Frame(parent, style="Modern.TFrame")
        self.summary_card.pack(fill=X)

        self.refresh_summary()

    def refresh_summary(self):
        """Create modern summary with clean layout."""
        for widget in self.summary_card.winfo_children():
            widget.destroy()

        # Card content with padding
        content_frame = ttkb.Frame(self.summary_card)
        content_frame.pack(fill=X, padx=ModernStyle.CARD_PADDING, pady=ModernStyle.CARD_PADDING)

        worker_id, _, wage = self.worker_data
        attendance_data = self.db.get_attendance_for_month(worker_id, self.current_month, self.current_year)

        present_days = list(attendance_data.values()).count('present')
        absent_days = list(attendance_data.values()).count('absent')
        total_working_days = len(attendance_data)

        total_earnings = present_days * wage
        total_advances = self.db.get_advances_for_month(worker_id, self.current_month, self.current_year)
        net_salary = total_earnings - total_advances

        # Attendance summary
        self.create_summary_row(content_frame, "Present Days", str(present_days), ModernStyle.STATUS_SUCCESS)
        self.create_summary_row(content_frame, "Absent Days", str(absent_days), ModernStyle.STATUS_DANGER)
        self.create_summary_row(content_frame, "Total Days", str(total_working_days), ModernStyle.ACCENT_SECONDARY)

        # Separator
        separator = ttkb.Frame(content_frame)
        separator.pack(fill=X, pady=(20, 20))
        separator.configure(height=1, style="Modern.TFrame")

        # Financial summary
        self.create_summary_row(content_frame, "Total Earnings", f"₹{total_earnings:,.2f}", ModernStyle.STATUS_SUCCESS)
        self.create_summary_row(content_frame, "Advances Paid", f"₹{total_advances:,.2f}", ModernStyle.STATUS_DANGER)
        
                 
    def create_summary_row(self, parent, label, value, color):
        """Create a clean summary row."""
        row_frame = ttkb.Frame(parent)
        row_frame.pack(fill=X, pady=(0, 12))

        ttkb.Label(row_frame, text=label, 
                   font=ModernStyle.FONT_BODY, 
                   foreground=ModernStyle.TEXT_PRIMARY).pack(side=LEFT)

        ttkb.Label(row_frame, text=value, 
                   font=ModernStyle.FONT_BODY, 
                   foreground=color).pack(side=RIGHT)


    def prev_month(self):
        """Navigate to previous month."""
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.refresh_summary()
        
    def next_month(self):
        """Navigate to next month."""
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.refresh_summary()

    def open_calendar(self):
        """Open attendance calendar popup."""
        CalendarPopup(self.controller, self.worker_data[0], self.current_month, self.current_year)
        
    def open_add_advance(self):
        """Open add advance popup."""
        popup = ModernPopup(self.controller, "Add Advance Payment", "Enter advance amount")
        popup.add_field("Amount (₹)", "amount", "number")
        
        def save_advance(data):
            try:
                amount = float(data["amount"])
                if amount <= 0:
                    messagebox.showerror("Invalid Input", "Amount must be greater than 0")
                    return False
                    
                date_str = datetime.now().strftime("%Y-%m-%d")
                self.db.add_advance(self.worker_data[0], amount, date_str)
                self.refresh_summary()
                messagebox.showinfo("Success", f"Advance of ₹{amount:.2f} added successfully!")
                return True
                
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid amount")
                return False
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add advance: {str(e)}")
                return False
                
        popup.set_callback(save_advance)
        popup.show()

class CalendarPopup(Toplevel):
    """Modern calendar popup for attendance marking."""
    def __init__(self, parent, worker_id, current_month, current_year):
        super().__init__(parent)
        self.parent = parent
        self.db = parent.db
        self.worker_id = worker_id
        self.month = current_month
        self.year = current_year

        self.title("Mark Attendance")
        self.geometry("420x320")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(bg=ModernStyle.PRIMARY_BG)

        self.center_window()
        self.attendance_data = self.db.get_attendance_for_month(self.worker_id, self.month, self.year)
        self.create_widgets()
        
    def center_window(self):
        """Center the popup window."""
        self.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        window_width = self.winfo_reqwidth()
        window_height = self.winfo_reqheight()
        
        x = parent_x + (parent_width // 2) - (window_width // 2)
        y = parent_y + (parent_height // 2) - (window_height // 2)
        
        self.geometry(f"+{x}+{y}")
        
    def create_widgets(self):
        """Create calendar widgets with modern styling."""
        
    def draw_calendar(self):
        """Draw the calendar grid."""
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        # Day headers
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            ttkb.Label(self.calendar_frame, text=day, 
                       font=ModernStyle.FONT_SUBTLE,
                       foreground=ModernStyle.ACCENT_SECONDARY).grid(row=0, column=i, pady=(0, 10))

        # Calendar days
        cal = calendar.monthcalendar(self.year, self.month)
        for r, week in enumerate(cal, 1):
            for c, day in enumerate(week):
                if day == 0:
                    continue
                
                status = self.attendance_data.get(day, 'unmarked')
                
                # Create day button
                btn_text = f"{day}\n{self.get_status_symbol(status)}"
                
                btn = ttkb.Button(self.calendar_frame, 
                                  text=btn_text,
                                  style=self.get_button_style(status),
                                  command=lambda d=day: self.toggle_attendance(d))
                btn.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
        
        # Configure grid weights
        for i in range(7): 
            self.calendar_frame.grid_columnconfigure(i, weight=1)
        for i in range(len(cal) + 1): 
            self.calendar_frame.grid_rowconfigure(i, weight=1)
            
    def get_status_symbol(self, status):
        """Get symbol for attendance status."""
        symbols = {
            'present': Icons.CHECK,
            'absent': Icons.CROSS,
            'unmarked': '?'
        }
        return symbols.get(status, '?')
        
    def get_button_style(self, status):
        """Get button style for attendance status."""
        if status == 'present':
            return "ModernPrimary.TButton"
        elif status == 'absent':
            return "ModernSecondary.TButton"
        else:
            return "ModernSecondary.TButton"
            
    def toggle_attendance(self, day):
        """Toggle attendance status for a day."""
        current_status = self.attendance_data.get(day, 'unmarked')
        
        # Cycle through statuses
        next_status = {
            'unmarked': 'present',
            'present': 'absent', 
            'absent': 'unmarked'
        }[current_status]
        
        date_str = f"{self.year}-{str(self.month).zfill(2)}-{str(day).zfill(2)}"
        self.db.mark_attendance(self.worker_id, date_str, next_status)
        
        self.refresh_calendar()
        
    def prev_month(self):
        """Navigate to previous month."""
        self.change_month(-1)
        
    def next_month(self):
        """Navigate to next month."""
        self.change_month(1)
        
    def change_month(self, delta):
        """Change month by delta."""
        if delta == 1:
            if self.month == 12:
                self.month = 1
                self.year += 1
            else:
                self.month += 1
        else:
            if self.month == 1:
                self.month = 12
                self.year -= 1
            else:
                self.month -= 1
        self.refresh_calendar()
        
    def refresh_calendar(self):
        """Refresh calendar display."""
        self.attendance_data = self.db.get_attendance_for_month(self.worker_id, self.month, self.year)
        self.draw_calendar()

if __name__ == "__main__":
    app = App()
    app.mainloop()
