# crud.py
import sqlite3

DATABASE = "database/database.db"

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row 
    return conn

# USERS CRUD
def create_user(username, password, is_staff=0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password, is_staff) VALUES (?, ?, ?)",
        (username, password, is_staff)
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

def update_user_password(user_id, new_password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# MENU ITEMS CRUD
def create_menu_item(name, price, image):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO menu_items (name, price, image) VALUES (?, ?, ?)",
        (name, price, image)
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

def update_menu_item(item_id, name, price, image):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE menu_items SET name = ?, price = ?, image = ? WHERE id = ?",
        (name, price, image, item_id)
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
    conn.commit()
    conn.close()

def get_orders():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders")
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
