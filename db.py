"""
db.py — SQLite data layer for Basic Retail Inventory Manager (BRIM)

NOTE ON DEPLOYMENT:
SQLite stores data in a local file (inventory.db). This works well for local
use and demos. If you deploy on Streamlit Community Cloud, the filesystem is
NOT persistent across app restarts/redeploys — data can be wiped. For a real
paid product, swap this module's connection for a hosted database instead
(e.g. Postgres on Supabase/Neon/Railway) by editing get_connection() and the
SQL below to match your driver. Everything else in the app calls the helper
functions in this file, so that's the only place you'd need to change.
"""

import sqlite3
from datetime import datetime, timedelta, date
import pandas as pd

DB_PATH = "inventory.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _to_float_or_none(v):
    """Coerces an uploaded cell to a float, or None if it's blank/unusable —
    used so 'not provided' (NULL) stays distinguishable from an explicit 0."""
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    s = str(v).strip()
    if s == "" or s.lower() == "nan" or s.lower() == "none":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            business_name TEXT,
            business_type TEXT,
            phone TEXT,
            role TEXT DEFAULT 'customer',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tier TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sku TEXT,
            product_name TEXT,
            category TEXT,
            quantity REAL,
            unit_cost REAL,
            reorder_level REAL,
            expiry_date TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sku TEXT,
            product_name TEXT,
            quantity_sold REAL,
            sale_date TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            sent INTEGER NOT NULL DEFAULT 0,
            detail TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY,
            sales_period_months INTEGER DEFAULT 3,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    # ---- Multi-branch module ----
    c.execute("""
        CREATE TABLE IF NOT EXISTS branch_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            branch TEXT,
            sku TEXT,
            product_name TEXT,
            category TEXT,
            quantity REAL,
            unit_cost REAL,
            reorder_level REAL,
            expiry_date TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS branch_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            branch TEXT,
            sku TEXT,
            product_name TEXT,
            quantity_sold REAL,
            sale_date TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()

    # Seed one default admin account on first run
    c.execute("SELECT id FROM users WHERE role='admin' LIMIT 1")
    if not c.fetchone():
        from auth import hash_password
        c.execute("""INSERT INTO users
            (username, email, password_hash, business_name, business_type, role)
            VALUES (?,?,?,?,?,?)""",
            ("admin", "admin@brim.local", hash_password("Admin@123"),
             "BRIM HQ", "Platform Admin", "admin"))
        conn.commit()

    conn.close()


# ---------- USERS ----------

def get_user_by_username(username):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(username, email, password_hash, business_name, business_type, phone):
    conn = get_connection()
    cur = conn.execute("""INSERT INTO users
        (username, email, password_hash, business_name, business_type, phone, role)
        VALUES (?,?,?,?,?,?, 'customer')""",
        (username, email, password_hash, business_name, business_type, phone))
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def update_password(user_id, new_hash):
    conn = get_connection()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    conn.commit()
    conn.close()


def list_customers():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users WHERE role = 'customer' ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- SUBSCRIPTIONS ----------

def create_subscription(user_id, tier, months=1):
    start = date.today()
    end = start + timedelta(days=30 * months)
    conn = get_connection()
    conn.execute("""INSERT INTO subscriptions (user_id, tier, start_date, end_date, status)
                     VALUES (?,?,?,?, 'active')""",
                 (user_id, tier, start.isoformat(), end.isoformat()))
    conn.commit()
    conn.close()


def get_active_subscription(user_id):
    conn = get_connection()
    row = conn.execute("""SELECT * FROM subscriptions WHERE user_id = ?
                           ORDER BY end_date DESC LIMIT 1""", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def renew_subscription(user_id, tier, months=1):
    create_subscription(user_id, tier, months)


def all_subscriptions_with_users():
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.*, u.username, u.email, u.business_name
        FROM subscriptions s
        JOIN users u ON u.id = s.user_id
        WHERE s.id IN (SELECT MAX(id) FROM subscriptions GROUP BY user_id)
        ORDER BY s.end_date ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def subscription_days_left(sub):
    if not sub:
        return None
    end = datetime.fromisoformat(sub["end_date"]).date()
    return (end - date.today()).days


# ---------- SETTINGS ----------

def get_sales_period_months(user_id):
    conn = get_connection()
    row = conn.execute("SELECT sales_period_months FROM settings WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["sales_period_months"] if row else 3


def set_sales_period_months(user_id, months):
    conn = get_connection()
    conn.execute("""INSERT INTO settings (user_id, sales_period_months) VALUES (?, ?)
                     ON CONFLICT(user_id) DO UPDATE SET sales_period_months = excluded.sales_period_months""",
                 (user_id, int(months)))
    conn.commit()
    conn.close()


# ---------- STOCK (single location) ----------

def replace_stock(user_id, df: pd.DataFrame):
    """Replaces this user's current stock snapshot with the uploaded one."""
    conn = get_connection()
    conn.execute("DELETE FROM stock WHERE user_id = ?", (user_id,))
    for _, r in df.iterrows():
        qty = _to_float_or_none(r.get("quantity", 0)) or 0.0
        conn.execute("""INSERT INTO stock
            (user_id, sku, product_name, category, quantity, unit_cost, reorder_level, expiry_date)
            VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, _to_str(r.get("sku")), _to_str(r.get("product_name")), _to_str(r.get("category")),
             qty, _to_float_or_none(r.get("unit_cost")), _to_float_or_none(r.get("reorder_level")),
             _to_str(r.get("expiry_date"))))
    conn.commit()
    conn.close()


def get_stock_df(user_id) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM stock WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df


# ---------- SALES (single location) ----------

def append_sales(user_id, df: pd.DataFrame):
    conn = get_connection()
    for _, r in df.iterrows():
        qty = _to_float_or_none(r.get("quantity_sold", 0)) or 0.0
        conn.execute("""INSERT INTO sales (user_id, sku, product_name, quantity_sold, sale_date)
                         VALUES (?,?,?,?,?)""",
                      (user_id, _to_str(r.get("sku")), _to_str(r.get("product_name")), qty,
                       _to_str(r.get("sale_date"))))
    conn.commit()
    conn.close()


def get_sales_df(user_id) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM sales WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df


def clear_sales(user_id):
    conn = get_connection()
    conn.execute("DELETE FROM sales WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ---------- BRANCH STOCK (multi-branch module) ----------

def replace_branch_stock(user_id, df: pd.DataFrame):
    """Replaces this user's current branch stock snapshot with the uploaded one."""
    conn = get_connection()
    conn.execute("DELETE FROM branch_stock WHERE user_id = ?", (user_id,))
    for _, r in df.iterrows():
        qty = _to_float_or_none(r.get("quantity", 0)) or 0.0
        conn.execute("""INSERT INTO branch_stock
            (user_id, branch, sku, product_name, category, quantity, unit_cost, reorder_level, expiry_date)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (user_id, _to_str(r.get("branch")), _to_str(r.get("sku")), _to_str(r.get("product_name")),
             _to_str(r.get("category")), qty, _to_float_or_none(r.get("unit_cost")),
             _to_float_or_none(r.get("reorder_level")), _to_str(r.get("expiry_date"))))
    conn.commit()
    conn.close()


def get_branch_stock_df(user_id) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM branch_stock WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df


def append_branch_sales(user_id, df: pd.DataFrame):
    conn = get_connection()
    for _, r in df.iterrows():
        qty = _to_float_or_none(r.get("quantity_sold", 0)) or 0.0
        conn.execute("""INSERT INTO branch_sales (user_id, branch, sku, product_name, quantity_sold, sale_date)
                         VALUES (?,?,?,?,?,?)""",
                      (user_id, _to_str(r.get("branch")), _to_str(r.get("sku")), _to_str(r.get("product_name")),
                       qty, _to_str(r.get("sale_date"))))
    conn.commit()
    conn.close()


def get_branch_sales_df(user_id) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM branch_sales WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df


def clear_branch_sales(user_id):
    conn = get_connection()
    conn.execute("DELETE FROM branch_sales WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def list_branches(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT branch FROM branch_stock WHERE user_id = ? AND branch != '' ORDER BY branch",
        (user_id,)
    ).fetchall()
    conn.close()
    return [r["branch"] for r in rows]


# ---------- NOTIFICATIONS ----------
# A log of every "someone clicked Subscribe" event, plus whether an outbound
# WhatsApp/SMS alert to the admin succeeded. Kept even when no provider is
# configured, so nothing is ever lost — the Admin page always shows it all.

def log_notification(message, sent, detail):
    conn = get_connection()
    conn.execute("INSERT INTO notifications (message, sent, detail) VALUES (?,?,?)",
                 (message, 1 if sent else 0, detail))
    conn.commit()
    conn.close()


def list_notifications(limit=50):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def unread_notification_count():
    """Notifications from the last 3 days — used to badge the admin sidebar."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as n FROM notifications WHERE created_at >= datetime('now', '-3 days')"
    ).fetchone()
    conn.close()
    return row["n"] if row else 0
