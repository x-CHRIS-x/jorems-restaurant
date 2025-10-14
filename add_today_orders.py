import sqlite3
from datetime import datetime
import random
import json

# Database connection
DATABASE = "database/database.db"

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_menu_items():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM menu_items")
    items = cursor.fetchall()
    conn.close()
    return items

def get_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE is_staff = 0")  # Get non-staff users
    users = cursor.fetchall()
    conn.close()
    return list(users)

def get_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables")
    tables = cursor.fetchall()
    conn.close()
    return list(tables)

def add_today_orders():
    # Get existing data
    menu_items = list(get_menu_items())
    users = get_users()
    tables = get_tables()
    
    if not menu_items or not users:
        print("Error: Need menu items and users in the database first!")
        return

    # Set today's date
    today = datetime(2025, 10, 14)
    num_orders = random.randint(5, 7)  # Generate 5-7 orders

    conn = get_connection()
    cursor = conn.cursor()

    # Status weights for today's orders
    status_weights = [
        ('pending', 0.4),    # 40% pending
        ('preparing', 0.3),  # 30% preparing
        ('completed', 0.2),  # 20% completed
        ('cancelled', 0.1)   # 10% cancelled
    ]

    order_count = 0

    # Business hours: 8 AM to current hour (if during business hours)
    current_hour = datetime.now().hour
    max_hour = min(current_hour if 8 <= current_hour <= 22 else 22, 22)
    
    for _ in range(num_orders):
        # Generate order time
        hour = random.randint(8, max_hour)
        minute = random.randint(0, 59)
        order_time = today.replace(hour=hour, minute=minute)
        
        # Select status
        status = random.choices(
            [s[0] for s in status_weights],
            weights=[s[1] for s in status_weights]
        )[0]

        # Generate order items (1-6 items per order)
        num_items = random.choices(
            [1, 2, 3, 4, 5, 6],
            weights=[10, 25, 30, 20, 10, 5]  # Most orders have 2-4 items
        )[0]
        
        order_items = []
        order_total = 0
        
        for _ in range(num_items):
            item = random.choice(menu_items)
            quantity = random.randint(1, 3)
            subtotal = float(item['price']) * quantity
            
            order_items.append({
                'id': item['id'],
                'name': item['name'],
                'price': float(item['price']),
                'quantity': quantity,
                'subtotal': subtotal,
                'image': item['image']
            })
            order_total += subtotal

        # Randomly assign a user
        user = random.choice(users)
        
        # Randomly assign a table (80% chance for today's orders)
        table_id = random.choice(tables)['id'] if random.random() < 0.8 else None

        # Create the order
        cursor.execute("""
            INSERT INTO orders (user_id, items, total, status, table_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user['id'],
            json.dumps(order_items),
            order_total,
            status,
            table_id,
            order_time.strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        order_count += 1

    # Commit changes
    conn.commit()
    conn.close()
    print(f"Successfully generated {order_count} new orders for {today.date()}")

if __name__ == "__main__":
    add_today_orders()