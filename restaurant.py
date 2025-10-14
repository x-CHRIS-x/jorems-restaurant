from flask import Flask, render_template, request, session, redirect, url_for, flash
from crud import *
from crud_tables import *
from werkzeug.security import check_password_hash
from functools import wraps
from werkzeug.utils import secure_filename
import os
from flask import send_file
import io
import json
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import inch

app = Flask(__name__)
app.secret_key = "legaspixyz"

# Initialize database tables
init_tables()

UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in") or not session.get("is_staff"):
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def _ensure_cart_schema(cart_items):
    # Ensure each cart item has price and image fields and correct subtotal
    if not cart_items:
        return []
    menu_items = get_menu_items()
    menu_index = {str(m["id"]): m for m in menu_items}
    name_index = {m["name"]: m for m in menu_items}
    normalized = []
    for c in cart_items:
        item_name = c.get("name")
        menu_item = name_index.get(item_name)
        price = c.get("price") if c.get("price") is not None else (menu_item["price"] if menu_item else 0)
        image = c.get("image") if c.get("image") else (menu_item["image"] if menu_item else "")
        qty = int(c.get("qty", 0))
        request_note = c.get("request", "")
        subtotal = price * qty
        normalized.append({
            "id": menu_item["id"] if menu_item else None,
            "name": item_name,
            "qty": qty,
            "price": price,
            "request": request_note,
            "subtotal": subtotal,
            "image": image,
        })
    return normalized

def _cart_summary(cart_items):
    subtotal = sum(item["subtotal"] for item in cart_items)
    taxes = round(subtotal * 0.12, 2)  # 12% VAT
    total = round(subtotal + taxes, 2)
    return subtotal, taxes, total

@app.route("/")
def index():
    menu = get_menu_items()
    # Normalize session cart
    session["cart"] = _ensure_cart_schema(session.get("cart", []))
    cart = session.get("cart", [])

    # Convert sqlite3.Row to dict and include current quantity in menu listing
    menu_list = []
    for item in menu:
        item_dict = dict(item)
        # Find item in cart, matching by ID and no special request
        cart_item = next((c for c in cart if str(c.get("id")) == str(item_dict["id"]) and not c.get("request")), None)
        if cart_item:
            item_dict["quantity"] = cart_item["qty"]
        else:
            item_dict["quantity"] = 0
        menu_list.append(item_dict)

    order_number = get_next_order_number()
    subtotal, taxes, total = _cart_summary(cart)

    return render_template("index.html", menu=menu_list, cart=cart, order_number=order_number, subtotal=subtotal, taxes=taxes, total=total)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Check if passwords match
        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match")

        # Check if user already exists
        existing_user = get_user_by_username(username)
        if existing_user:
            return render_template("register.html", error="Username already taken")

        # Create the user
        create_user(username, password, is_staff=0)

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/add_item", methods=["POST"])
def add_item():
    if "cart" not in session:
        session["cart"] = []

    # This will hold the items to be added/updated in the cart
    items_to_process = []
    menu_items = get_menu_items()

    for item in menu_items:
        item_id_str = str(item["id"])
        qty_str = request.form.get(f"item_qty_{item_id_str}")
        
        if qty_str:
            try:
                qty = int(qty_str)
                if qty > 0:
                    # We found an item with a quantity, prepare it for the cart
                    items_to_process.append({
                        "id": item["id"],
                        "name": item["name"],
                        "qty": qty,
                        "price": item["price"],
                        "image": item["image"],
                        "request": "" # Bulk add has no special request
                    })
            except (ValueError, TypeError):
                continue
    
    # Merge the processed items with the existing cart
    cart = session.get("cart", [])
    for new_item in items_to_process:
        # For bulk add, there's no special request. The key includes the item ID and an empty request.
        item_key = f"{new_item['id']}_"

        # Find if a similar item (same ID, no request) is already in the cart
        existing_item_index = -1
        for i, cart_item in enumerate(cart):
            # A cart item's key is its ID and request note. For bulk add, the request is always empty.
            cart_item_key = f"{cart_item.get('id')}_{cart_item.get('request', '')}"
            if cart_item_key == item_key:
                existing_item_index = i
                break
        
        if existing_item_index != -1:
            # If item exists, add the new quantity to the existing quantity.
            cart[existing_item_index]["qty"] += new_item["qty"]
            cart[existing_item_index]["subtotal"] = cart[existing_item_index]["qty"] * cart[existing_item_index]["price"]
        else:
            # Add as a new item, ensuring it has a key
            new_item["subtotal"] = new_item["qty"] * new_item["price"]
            new_item["key"] = item_key
            cart.append(new_item)

    session["cart"] = [item for item in cart if item["qty"] > 0] # Clean up items with 0 quantity
    session.modified = True
    return redirect(url_for("cart"))

@app.route("/add_single_item", methods=["POST"])
def add_single_item():
    item_id = request.form.get("item_id")
    request_note = request.form.get("request", "").strip()
    qty = int(request.form.get("quantity", 1))
    
    item = get_menu_item_by_id(item_id)
    if not item:
        flash("Item not found.", "danger")
        return redirect(url_for("index"))

    if item:
        try:
            price = float(item['price'])
            subtotal = qty * price
        except ValueError:
            return redirect(url_for("index"))
        
        if "cart" not in session:
            session["cart"] = []
        
        cart = session["cart"]
        found = False
        for cart_item in cart:
            # If both items have no special request, match by ID
            # Or if both items have the same special request and ID
            if (str(cart_item.get("id")) == str(item_id) and 
                cart_item.get("request", "") == request_note):
                cart_item["qty"] += qty
                cart_item["subtotal"] = cart_item["qty"] * cart_item["price"]
                found = True
                break
        
        if not found:
            cart.append({
                "id": item['id'],
                "name": item['name'], 
                "qty": qty, 
                "price": price, 
                "subtotal": subtotal, 
                "image": item['image'],
                "request": request_note
            })
        
        session["cart"] = cart
        session.modified = True
    
    flash(f"Added {item['name']} to your order.", "success")
    return redirect(url_for("index"))

@app.route("/add_multiple_items", methods=["POST"])
def add_multiple_items():
    item_ids = request.form.getlist("item_id[]")
    item_names = request.form.getlist("item_name[]")
    item_prices = request.form.getlist("item_price[]")
    item_images = request.form.getlist("item_image[]")
    item_quantities = request.form.getlist("item_quantity[]")

    if "cart" not in session:
        session["cart"] = []
    
    cart = session["cart"]

    for i in range(len(item_ids)):
        qty = int(item_quantities[i])
        if qty > 0:
            item_id = item_ids[i]
            name = item_names[i]
            price = float(item_prices[i])
            image = item_images[i]

            # Check if item already in cart
            found = False
            for cart_item in cart:
                # Match items by ID and ensure no special request
                if str(cart_item.get("id")) == str(item_id) and not cart_item.get("request"):
                    cart_item["qty"] += qty
                    cart_item["subtotal"] = cart_item["qty"] * cart_item["price"]
                    found = True
                    break

            if not found:
                cart.append({
                    "id": item_id,
                    "name": name,
                    "qty": qty,
                    "price": price,
                    "image": image,
                    "subtotal": qty * price,
                    "request": ""  # Explicitly set empty request for bulk-added items
                })

    session["cart"] = cart
    session.modified = True
    return redirect(url_for("index"))

@app.route("/update_cart", methods=["POST"])
def update_cart():
    item_id = request.form.get("item_id")
    change = int(request.form.get("change", 0))
    return_to = request.form.get("return_to")
    
    if not item_id or change == 0:
        return redirect(url_for("index"))
    
    # Get the menu item details
    menu_items = get_menu_items()
    item = None
    for menu_item in menu_items:
        if str(menu_item["id"]) == str(item_id):
            item = menu_item
            break
    
    if not item:
        return redirect(url_for("index"))
    
    if "cart" not in session:
        session["cart"] = []
    
    cart = session["cart"]
    found = False
    
    # Find existing item in cart
    for cart_item in cart:
        # We must match by a consistent key. Since this is a simple +/- update,
        # we assume it doesn't have a special request.
        cart_item_key = f"{cart_item.get('id')}_{cart_item.get('request', '')}"
        if cart_item_key == f"{item['id']}_":
            new_qty = cart_item["qty"] + change
            if new_qty <= 0:
                # Remove item from cart if quantity becomes 0 or negative
                cart.remove(cart_item)
            else:
                # Update quantity, price, image, and subtotal
                cart_item["qty"] = new_qty
                cart_item["price"] = item["price"]
                cart_item["image"] = item["image"]
                cart_item["subtotal"] = new_qty * item["price"]
            found = True
            break
    
    # If item not in cart and we're adding (change > 0)
    if not found and change > 0:
        cart.append({
            "id": item["id"],
            "name": item["name"],
            "qty": change,
            "price": item["price"],
            "subtotal": change * item["price"],
            "image": item["image"]
        })
    
    session["cart"] = cart
    session.modified = True
    
    if return_to == "budget_mode":
        return redirect(url_for("budget_mode", _anchor=f"item-{item_id}"))
    elif return_to == "tables":
        return redirect(url_for("tables", _anchor=f"item-{item_id}"))
    elif return_to == "staff_menu":
        return redirect(url_for("staff_menu", _anchor=f"item-{item_id}"))
        
    return redirect(url_for("index", _anchor=f"item-{item_id}"))

@app.route("/remove_item", methods=["POST"])
def remove_item():
    name = request.form.get("item_name")
    # A more robust implementation would use a unique cart item ID
    return_to = request.form.get("return_to")
    if not name:
        return redirect(url_for("index"))
    # This is a simple removal by name, which might remove multiple items if they have different requests.
    cart = session.get("cart", [])
    cart = [c for c in cart if c.get("name") != name]
    session["cart"] = cart
    session.modified = True
    
    if return_to == "tables":
        return redirect(url_for("tables"))
    elif return_to == "staff_menu":
        return redirect(url_for("staff_menu"))
    return redirect(url_for("index"))

@app.route("/budget_mode", methods=["GET", "POST"])
def budget_mode():
    if request.method == "POST":
        budget = float(request.form.get("budget_value", 0))
        session["budget_value"] = budget
    else:
        budget = float(session.get("budget_value", 0))
    menu = get_menu_items()
    session["cart"] = _ensure_cart_schema(session.get("cart", []))
    cart = session.get("cart", [])
    suggested = []
    
    for item in menu:
        if item["price"] <= budget:
            # Convert Row to dictionary and add current quantity
            item_dict = dict(item)
            item_dict["quantity"] = 0
            for cart_item in cart:
                if cart_item["name"] == item_dict["name"]:
                    item_dict["quantity"] = cart_item["qty"]
                    break
            suggested.append(item_dict)
    
    order_number = get_next_order_number()
    subtotal, taxes, total = _cart_summary(cart)
    return render_template("budget_order.html", suggested=suggested, budget=budget, cart=cart, order_number=order_number, subtotal=subtotal, taxes=taxes, total=total)

@app.route("/budget_order", methods=["POST"])
def budget_order():
    budget = float(request.form.get("budget_value", 0))
    total = 0
    selected_items = []
    for item in get_menu_items():
        qty_str = request.form.get(f"quantity_{item['id']}")
        try:
            qty = int(qty_str) if qty_str else 0
        except ValueError:
            qty = 0
        if qty > 0:
            subtotal = qty * item["price"]
            selected_items.append({
                "id": item["id"],
                "name": item["name"],
                "qty": qty,
                "price": item["price"],
                "subtotal": subtotal,
                "image": item["image"]
            })
            total += subtotal
    if total > budget:
        return render_template("budget_exceed.html", total=total, budget=budget, order=selected_items)
    if "cart" not in session:
        session["cart"] = []
    cart = session["cart"]
    for item in selected_items:
        found = False
        for cart_item in cart:
            if cart_item["name"] == item["name"]:
                cart_item["qty"] += item["qty"]
                cart_item["subtotal"] += item["subtotal"]
                found = True
                break
        if not found:
            cart.append(item)
    session["cart"] = cart
    session.modified = True
    return redirect(url_for("cart"))

@app.route("/order_confirm", methods=["POST"])
def order_confirm():
    items = []
    total = float(request.form.get("total", 0))
    for item in get_menu_items():
        item_id = str(item["id"])
        name = request.form.get(f"item_name_{item_id}")
        qty = request.form.get(f"item_qty_{item_id}")
        subtotal = request.form.get(f"item_subtotal_{item_id}")
        image = request.form.get(f"item_image_{item_id}")
        if name and qty and subtotal and image:
            try:
                qty = int(qty)
                subtotal = float(subtotal)
            except ValueError:
                continue
            items.append({"name": name, "qty": qty, "subtotal": subtotal, "image": image})
    if "cart" not in session:
        session["cart"] = []
    cart = session["cart"]
    for item in items:
        found = False
        for cart_item in cart:
            if cart_item["name"] == item["name"]:
                cart_item["qty"] += item["qty"]
                cart_item["subtotal"] += item["subtotal"]
                found = True
                break
        if not found:
            cart.append(item)
    session["cart"] = cart
    session.modified = True
    return redirect(url_for("cart"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = get_user_by_username(username)

        if user:
            # Check for modern hashed password first
            is_valid = check_password_hash(user['password'], password)

            # If hash check fails, check for legacy plain-text password
            if not is_valid and user['password'] == password:
                is_valid = True
                # Upgrade the password to a secure hash in the background
                update_user_password(user['id'], password)
                flash("Your password has been securely updated!", "info")

            if is_valid:
                session["logged_in"] = True
                session["username"] = username
                session["user_id"] = user['id']
                session["is_staff"] = user['is_staff']
                
                if user['is_staff']:
                    flash(f"Welcome back, Staff {user['username']}!", "info")
                    return redirect(url_for("staff_dashboard"))
                return redirect(url_for("index"))

        flash("Invalid username or password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    session.pop("username", None)
    session.pop("is_staff", None)
    return redirect(url_for("index"))

@app.route("/cart")
def cart():
    return render_template("cart.html", cart=session.get("cart", []))

@app.route("/checkout_confirm", methods=["POST"])
@login_required
def checkout_confirm():
    cart_items = session.get("cart", [])
    if not cart_items:
        return redirect(url_for("cart"))
    # If budget mode is active, enforce budget before confirming
    try:
        budget_value = float(session.get("budget_value", 0))
    except (TypeError, ValueError):
        budget_value = 0
    if budget_value > 0:
        subtotal = sum(item['subtotal'] for item in cart_items)
        if subtotal > budget_value:
            return render_template("budget_exceed.html", total=subtotal, budget=budget_value, order=cart_items)
    return render_template("checkout_confirm.html", cart=cart_items)

@app.route("/confirm_checkout", methods=["POST"])
@login_required
def confirm_checkout():
    cart_items = session.get("cart", [])
    total = sum(item['subtotal'] for item in cart_items)

    if not cart_items:
        flash("Cart is empty!", "danger")
        return redirect(url_for("cart"))

    # Save order in DB
    order_id = None
    if session.get("logged_in"):
        user_id = session.get("user_id")
        try:
            order_id = create_order(user_id, json.dumps(cart_items), total, status="pending")
            
            # If this is a staff order and a table was selected, assign it
            if session.get("is_staff") and session.get("selected_table"):
                table_id = session["selected_table"]["id"]
                assign_table_to_order(table_id, order_id)
                session.pop("selected_table", None)  # Clear selected table from session
                
        except Exception as e:
            print("DB error:", e)

    # ✅ Generate QR Code with full order details
    qr_data = f"Order #{order_id}\nTotal: ₱{total:.2f}\nItems:\n"
    for item in cart_items:
        qr_data += f"- {item['name']} x{item['qty']} (₱{item['subtotal']})\n"

    qr_img = qrcode.make(qr_data)
    qr_folder = os.path.join("static", "qr")
    os.makedirs(qr_folder, exist_ok=True)
    qr_path = os.path.join(qr_folder, f"order_{order_id or 'temp'}.png")
    qr_img.save(qr_path)
    
    session["last_order"] = cart_items.copy()       
    
    session["cart"] = []
    session.pop("budget_value", None)
    session.modified = True

    return render_template(
        "checkout_success.html",
        order=cart_items,
        total=total,
        order_id=order_id,
        qr_image=f"/{qr_path}"
    )

@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    cart_items = session.get("cart", [])
    total = sum(item['subtotal'] for item in cart_items)
    if session.get("logged_in"):
        user_id = session.get("user_id")
        try:
            create_order(user_id, json.dumps(cart_items), total, status="pending")
        except Exception:
            pass
    session["cart"] = []
    session.modified = True
    return render_template("checkout_success.html", order=cart_items, total=total)

@app.route("/clear_cart", methods=["POST"])
def clear_cart():
    session["cart"] = []
    session.modified = True
    return redirect(url_for("cart"))

@app.route("/download_receipt")
def download_receipt():
    cart_items = session.get("last_order")
    if not cart_items:
        flash("No recent order to download.", "warning")
        return redirect(url_for("index"))

    buffer = io.BytesIO()
    
    # Small receipt page size
    from reportlab.lib.pagesizes import inch
    receipt_width = 3 * inch
    receipt_height = 5 * inch

    pdf = canvas.Canvas(buffer, pagesize=(receipt_width, receipt_height))
    
    pdf.setFont("Helvetica-Bold", 10)
    # Multi-line header
    header_lines = [
        "THANK YOU FOR YOUR ORDER",
        "on JM Restaurant",
        "Give this to cashier or staff"
    ]
    y = receipt_height - 20
    for line in header_lines:
        pdf.drawString(10, y, line)
        y -= 12  # line spacing

    y -= 10  # extra space before QR code

    # Generate QR code
    qr_data = "Order Details:\n"
    total = 0
    for item in cart_items:
        qr_data += f"{item['name']} x{item['qty']} - ₱{item.get('subtotal', 0):.2f}\n"
        total += item.get('subtotal', 0)

    qr_img = qrcode.make(qr_data)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # Embed QR code
    from reportlab.lib.utils import ImageReader
    qr_image = ImageReader(qr_buffer)
    pdf.drawImage(qr_image, 10, y - 120, width=100, height=100)
    y -= 130

    pdf.setFont("Helvetica", 9)
    for item in cart_items:
        line = f"{item['name']} x{item['qty']} - ₱{item.get('subtotal', 0):.2f}"
        pdf.drawString(10, y, line)
        y -= 12

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(10, y - 10, f"Total: ₱{total:.2f}")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="receipt.pdf", mimetype="application/pdf")

@app.route("/my_orders")
@login_required
def my_orders():
    user_id = session.get("user_id")
    if not user_id:
        flash("You must be logged in to see your orders.", "warning")
        return redirect(url_for("login"))

    orders_data = get_orders_by_user(user_id)
    orders = []
    for order_row in orders_data:
        order = dict(order_row)
        try:
            order['items'] = json.loads(order['items'])
        except (json.JSONDecodeError, TypeError):
            order['items'] = []
        orders.append(order)
    
    return render_template("my_orders.html", orders=orders)


# --- STAFF ROUTES ---
@app.route("/staff/tables")
@staff_required
def tables():
    tables = get_tables()
    # Get cart information
    session["cart"] = _ensure_cart_schema(session.get("cart", []))
    cart = session.get("cart", [])
    order_number = get_next_order_number()
    subtotal, taxes, total = _cart_summary(cart)
    
    return render_template("tables.html", 
                         tables=tables,
                         cart=cart,
                         order_number=order_number,
                         subtotal=subtotal,
                         taxes=taxes,
                         total=total,
                         selected_table=session.get("selected_table"))

@app.route("/staff/select_table", methods=["POST"])
@staff_required
def select_table():
    table_id = request.form.get("table_id")
    table_number = request.form.get("table_number")
    if not table_id or not table_number:
        flash("No table selected", "error")
        return redirect(url_for("tables"))
    
    # Store selected table in session
    session["selected_table"] = {
        "id": table_id,
        "number": table_number
    }
    session.modified = True
    
    flash(f"Table {table_number} selected for this order", "success")
    return redirect(url_for("tables"))

@app.route("/staff/unselect_table", methods=["POST"])
@staff_required
def unselect_table():
    session.pop("selected_table", None)
    session.modified = True
    return redirect(url_for("tables"))

@app.route("/staff/menu")
@staff_required
def staff_menu():
    menu = get_menu_items()
    # Normalize session cart
    session["cart"] = _ensure_cart_schema(session.get("cart", []))
    cart = session.get("cart", [])

    # Convert sqlite3.Row to dict and include current quantity in menu listing
    menu_list = []
    for item in menu:
        item_dict = dict(item)
        cart_item = next((c for c in cart if c["id"] == item["id"]), None)
        item_dict["quantity"] = cart_item["qty"] if cart_item else 0
        menu_list.append(item_dict)

    order_number = get_next_order_number()
    subtotal, taxes, total = _cart_summary(cart)
    
    return render_template("staff_menu.html", menu=menu_list, cart=cart, order_number=order_number, subtotal=subtotal, taxes=taxes, total=total)

@app.route("/staff")
@staff_required
def staff_dashboard():
    menu_items = get_menu_items()
    return render_template("staff_dashboard.html", menu_items=menu_items)

@app.route("/staff/table_list")
@staff_required
def table_list():
    tables = get_tables()
    return render_template("table_list.html", tables=tables)

@app.route("/staff/clear_table", methods=["POST"])
@staff_required
def clear_table():
    table_id = request.form.get("table_id")
    if table_id:
        try:
            update_table_status(table_id, "available")
            flash("Table marked as available.", "success")
        except Exception as e:
            flash(f"Error clearing table: {str(e)}", "error")
    else:
        flash("No table specified.", "error")
    return redirect(url_for("table_list"))

@app.route("/staff/add_item", methods=["POST"])
@staff_required
def staff_add_item():
    name = request.form.get("name")
    price = request.form.get("price")
    description = request.form.get("description")
    image_file = request.files.get('image')

    if name and price and image_file:
        try:
            # Save the uploaded file
            filename = secure_filename(image_file.filename)
            if '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
                # Ensure the upload folder exists
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                image_path = os.path.join(UPLOAD_FOLDER, filename)
                image_file.save(image_path)
                
                # Store the relative path
                db_image_path = os.path.join('images', filename).replace('\\', '/')
                create_menu_item(name, float(price), db_image_path, description)
            else:
                flash("Invalid image file type.", "danger")
                return redirect(url_for("staff_dashboard"))

            flash("Menu item added successfully!", "success")
        except Exception as e:
            flash(f"Error adding item: {e}", "danger")
    else:
        flash("All fields are required.", "warning")
    return redirect(url_for("staff_dashboard"))

@app.route("/staff/edit_item/<int:item_id>", methods=["GET", "POST"])
@staff_required
def staff_edit_item(item_id):
    item = get_menu_item_by_id(item_id)
    if not item:
        flash("Menu item not found.", "danger")
        return redirect(url_for("staff_dashboard"))

    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        description = request.form.get("description")
        image_file = request.files.get('image')

        db_image_path = item['image'] # Keep old image by default

        if image_file and image_file.filename != '':
            # A new file was uploaded, so save it
            filename = secure_filename(image_file.filename)
            if '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS:
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                image_path = os.path.join(UPLOAD_FOLDER, filename)
                image_file.save(image_path)
                db_image_path = os.path.join('images', filename).replace('\\', '/')
            else:
                flash("Invalid image file type. Item not updated.", "danger")
                return render_template("edit_menu_item.html", item=item)
        if name and price:
            try:
                update_menu_item(item_id, name, float(price), db_image_path, description)
                flash("Menu item updated successfully!", "success")
                return redirect(url_for("staff_dashboard"))
            except Exception as e:
                flash(f"Error updating item: {e}", "danger")
        else:
            flash("All fields are required.", "warning")
    
    return render_template("edit_menu_item.html", item=item)

@app.route("/staff/delete_item/<int:item_id>", methods=["POST"])
@staff_required
def staff_delete_item(item_id):
    try:
        delete_menu_item(item_id)
        flash("Menu item deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting item: {e}", "danger")
    return redirect(url_for("staff_dashboard"))

@app.route("/staff/orders")
@staff_required
def staff_orders():
    orders_data = get_orders()
    orders = []
    for order_row in orders_data:
        order = dict(order_row)
        user = get_user_by_id(order['user_id'])
        order['username'] = user['username'] if user else 'Unknown'
        try:
            # The 'items' are stored as a JSON string, so we parse it
            loaded_items = json.loads(order['items'])
            # Ensure items are always in a list, even if it's a single dict
            if isinstance(loaded_items, dict):
                loaded_items = [loaded_items]
            order['items'] = loaded_items
        except (json.JSONDecodeError, TypeError):
            order['items'] = [] # Handle cases where items might be malformed
        orders.append(order)
    
    return render_template("staff_orders.html", orders=orders)

@app.route("/staff/update_order_status", methods=["POST"])
@staff_required
def update_order_status():
    order_id = request.form.get("order_id")
    new_status = request.form.get("status")
    if order_id and new_status:
        try:
            update_order(order_id, new_status)
            flash(f"Order #{order_id} status updated to '{new_status}'.", "success")
        except Exception as e:
            flash(f"Error updating order status: {e}", "danger")
    else:
        flash("Invalid request to update order status.", "warning")
    return redirect(url_for("staff_orders"))

# ⬇️ this should stay last
if __name__ == "__main__":
    app.run(debug=True)
