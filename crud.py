from db import get_db

# USERS CRUD

def create_user(username, password, is_staff=0):
    db = get_db()
    db.execute(
        'INSERT INTO users (username, password, is_staff) VALUES (?, ?, ?)',
        (username, password, is_staff)
    )
    db.commit()

def get_user_by_username(username):
    db = get_db()
    return db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

def update_user_password(user_id, new_password):
    db = get_db()
    db.execute('UPDATE users SET password = ? WHERE id = ?', (new_password, user_id))
    db.commit()

def delete_user(user_id):
    db = get_db()
    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.commit()

# MENU ITEMS CRUD

def create_menu_item(name, price, image):
    db = get_db()
    db.execute(
        'INSERT INTO menu_items (name, price, image) VALUES (?, ?, ?)',
        (name, price, image)
    )
    db.commit()

def get_menu_items():
    db = get_db()
    return db.execute('SELECT * FROM menu_items').fetchall()

def update_menu_item(item_id, name, price, image):
    db = get_db()
    db.execute('UPDATE menu_items SET name = ?, price = ?, image = ? WHERE id = ?', (name, price, image, item_id))
    db.commit()

def delete_menu_item(item_id):
    db = get_db()
    db.execute('DELETE FROM menu_items WHERE id = ?', (item_id,))
    db.commit()

# ORDERS CRUD

def create_order(user_id, items, total, status='pending'):
    db = get_db()
    db.execute(
        'INSERT INTO orders (user_id, items, total, status) VALUES (?, ?, ?, ?)',
        (user_id, items, total, status)
    )
    db.commit()

def get_orders():
    db = get_db()
    return db.execute('SELECT * FROM orders').fetchall()

def update_order(order_id, status):
    db = get_db()
    db.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    db.commit()

def delete_order(order_id):
    db = get_db()
    db.execute('DELETE FROM orders WHERE id = ?', (order_id,))
    db.commit()
