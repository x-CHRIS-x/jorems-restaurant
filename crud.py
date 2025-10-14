# crud.py
import sqlite3
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = "database/database.db"

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row 
    return conn

# USERS CRUD
def create_user(username, password, is_staff=0):
    conn = get_connection()
    cursor = conn.cursor()
    hashed_password = generate_password_hash(password)
    cursor.execute(
        "INSERT INTO users (username, password, is_staff) VALUES (?, ?, ?)",
        (username, hashed_password, is_staff)
    )
    conn.commit()
    conn.close()

def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user_password(user_id, new_password):
    conn = get_connection()
    cursor = conn.cursor()
    hashed_password = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_password, user_id))
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# MENU ITEMS CRUD
def create_menu_item(name, price, image, description=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO menu_items (name, price, image, description) VALUES (?, ?, ?, ?)",
        (name, price, image, description)
    )
    conn.commit()
    conn.close()

def get_menu_items():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM menu_items")
    items = cursor.fetchall()
    conn.close()
    return items

def get_menu_item_by_id(item_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    return item

def update_menu_item(item_id, name, price, image, description=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE menu_items SET name = ?, price = ?, image = ?, description = ? WHERE id = ?",
        (name, price, image, description, item_id)
    )
    conn.commit()
    conn.close()

def delete_menu_item(item_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


# ORDERS CRUD
def create_order(user_id, items, total, status="pending"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (user_id, items, total, status) VALUES (?, ?, ?, ?)",
        (user_id, items, total, status)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_orders(limit=None):
    conn = get_connection()
    cursor = conn.cursor()
    if limit:
        cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,))
    else:
        cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_orders_by_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders

def update_order(order_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()

def delete_order(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()


# ORDER UTILS
def get_next_order_number():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM orders")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 1

def get_all_orders():
    """Get all orders from the database"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM (
            SELECT * FROM orders
            UNION ALL
            SELECT * FROM dummy_orders
        )
        ORDER BY created_at DESC
    """)
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_orders_by_date(date):
    """Get orders for a specific date"""
    conn = get_connection()
    cursor = conn.cursor()
    date_str = date.strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT * FROM (
            SELECT * FROM orders
            UNION ALL
            SELECT * FROM dummy_orders
        )
        WHERE DATE(created_at) = DATE(?)
        ORDER BY created_at DESC
    """, (date_str,))
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_orders_by_month(date):
    """Get orders for a specific month"""
    conn = get_connection()
    cursor = conn.cursor()
    year_month = date.strftime('%Y-%m')
    cursor.execute("""
        SELECT * FROM (
            SELECT * FROM orders
            UNION ALL
            SELECT * FROM dummy_orders
        )
        WHERE strftime('%Y-%m', created_at) = ?
        ORDER BY created_at DESC
    """, (year_month,))
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_daily_orders_stats(date):
    conn = get_connection()
    cursor = conn.cursor()
    # Get orders for specific date grouped by hour
    cursor.execute("""
        SELECT 
            strftime('%H', created_at) as hour,
            COUNT(*) as order_count,
            SUM(total) as total_sales
        FROM (
            SELECT * FROM orders
            UNION ALL
            SELECT * FROM dummy_orders
        )
        WHERE date(created_at) = date(?)
        GROUP BY strftime('%H', created_at)
        ORDER BY hour
    """, (date,))
    hourly_stats = cursor.fetchall()
    conn.close()
    return hourly_stats

def get_monthly_orders_stats(year, month):
    conn = get_connection()
    cursor = conn.cursor()
    # Get orders for specific month grouped by day
    cursor.execute("""
        SELECT 
            strftime('%d', created_at) as day,
            COUNT(*) as order_count,
            SUM(total) as total_sales
        FROM (
            SELECT * FROM orders
            UNION ALL
            SELECT * FROM dummy_orders
        )
        WHERE strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ?
        GROUP BY strftime('%d', created_at)
        ORDER BY day
    """, (str(year), f"{month:02d}"))
    daily_stats = cursor.fetchall()
    conn.close()
    return daily_stats

def get_orders_summary(start_date, end_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as order_count,
            SUM(total) as total_sales,
            AVG(total) as avg_order_value
        FROM orders
        WHERE date(created_at) BETWEEN date(?) AND date(?)
    """, (start_date, end_date))
    summary = cursor.fetchone()
    conn.close()
    return summary