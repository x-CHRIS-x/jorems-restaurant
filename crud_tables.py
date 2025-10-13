import sqlite3

DATABASE = "database/database.db"

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_tables():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            is_staff INTEGER DEFAULT 0
        )
    """)

    # Create menu_items table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            image TEXT,
            description TEXT
        )
    """)

    # Create orders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            items TEXT,
            total REAL,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Create tables table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_number INTEGER NOT NULL,
        capacity INTEGER NOT NULL,
        status TEXT DEFAULT 'available' CHECK(status IN ('available', 'occupied'))
    )
    """)
    
    # Add table_id column to orders table if it doesn't exist
    cursor.execute("PRAGMA table_info(orders)")
    columns = cursor.fetchall()
    if not any(col["name"] == "table_id" for col in columns):
        cursor.execute("ALTER TABLE orders ADD COLUMN table_id INTEGER REFERENCES tables(id)")
    
    # Initialize some default tables if none exist
    cursor.execute("SELECT COUNT(*) as count FROM tables")
    if cursor.fetchone()["count"] == 0:
        # Create 10 default tables with different capacities
        default_tables = [
            (1, 2), (2, 2),  # 2-seater tables
            (3, 4), (4, 4), (5, 4),  # 4-seater tables
            (6, 6), (7, 6),  # 6-seater tables
            (8, 8),  # 8-seater table
            (9, 10), (10, 10)  # 10-seater tables
        ]
        cursor.executemany(
            "INSERT INTO tables (table_number, capacity) VALUES (?, ?)",
            default_tables
        )
    
    conn.commit()
    conn.close()

# TABLES CRUD
def create_table(table_number, capacity, status="available"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tables (table_number, capacity, status) VALUES (?, ?, ?)",
        (table_number, capacity, status)
    )
    conn.commit()
    conn.close()

def get_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables")
    tables = cursor.fetchall()
    conn.close()
    return tables

def get_table_by_id(table_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tables WHERE id = ?", (table_id,))
    table = cursor.fetchone()
    conn.close()
    return table

def update_table_status(table_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tables SET status = ? WHERE id = ?", (status, table_id))
    conn.commit()
    conn.close()

def assign_table_to_order(table_id, order_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET table_id = ? WHERE id = ?", (table_id, order_id))
    cursor.execute("UPDATE tables SET status = 'occupied' WHERE id = ?", (table_id,))
    conn.commit()
    conn.close()

def unassign_table(table_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tables SET status = 'available' WHERE id = ?", (table_id,))
    conn.commit()
    conn.close()