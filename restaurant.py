from flask import Flask, render_template, request, session, redirect, url_for, flash
from crud import *
from werkzeug.security import check_password_hash
from functools import wraps
from werkzeug.utils import secure_filename
import os
from flask import send_file
import io
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import qrcode


UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.secret_key = "legaspixyz"


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
        subtotal = price * qty
        normalized.append({
            "id": menu_item["id"] if menu_item else None,
            "name": item_name,
            "qty": qty,
            "price": price,
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
        item_dict["quantity"] = 0
        for cart_item in cart:
            if cart_item["name"] == item_dict["name"]:
                item_dict["quantity"] = cart_item["qty"]
                break
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

@app.route("/add_single_item", methods=["POST"])
def add_single_item():
    item_id = request.form.get("item_id")
    name = request.form.get("item_name")
    price = request.form.get("item_price")
    qty = request.form.get("quantity")
    image = request.form.get("item_image")
    
    if name and price and qty and image:
        try:
            qty = int(qty)
            price = float(price)
            subtotal = qty * price
        except ValueError:
            return redirect(url_for("index"))
        
        if "cart" not in session:
            session["cart"] = []
        
        cart = session["cart"]
        found = False
        for cart_item in cart:
            if cart_item["name"] == name:
                cart_item["qty"] += qty
                cart_item["price"] = price
                cart_item["image"] = image
                cart_item["subtotal"] = cart_item["qty"] * price
                found = True
                break
        
        if not found:
            cart.append({"name": name, "qty": qty, "price": price, "subtotal": subtotal, "image": image})
        
        session["cart"] = cart
        session.modified = True
    
    return redirect(url_for("cart"))

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
        if cart_item["name"] == item["name"]:
            new_qty = cart_item["qty"] + change
            if new_qty <= 0:
                # Remove item from cart if quantity becomes 0 or negative
                cart.remove(cart_item)
            else:
                # Update quantity and subtotal
                cart_item["qty"] = new_qty
                cart_item["price"] = item["price"]
                cart_item["image"] = item["image"]
                cart_item["subtotal"] = new_qty * item["price"]
            found = True
            break
    
    # If item not in cart and we're adding (change > 0)
    if not found and change > 0:
        cart.append({
            "name": item["name"],
            "qty": change,
            "price": item["price"],
            "subtotal": change * item["price"],
            "image": item["image"]
        })
    
    session["cart"] = cart
    session.modified = True
    
    if return_to == "budget_mode":
        # Return to budget mode without enforcing budget yet; enforcement happens on Order
        return redirect(url_for("budget_mode"))
    return redirect(url_for("index"))

@app.route("/remove_item", methods=["POST"])
def remove_item():
    name = request.form.get("item_name")
    if not name:
        return redirect(url_for("index"))
    cart = session.get("cart", [])
    cart = [c for c in cart if c.get("name") != name]
    session["cart"] = cart
    session.modified = True
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

        return render_template("login.html", error="Invalid username or password.")
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

# --- STAFF ROUTES ---
@app.route("/staff")
@staff_required
def staff_dashboard():
    menu_items = get_menu_items()
    return render_template("staff_dashboard.html", menu_items=menu_items)

@app.route("/staff/add_item", methods=["POST"])
@staff_required
def staff_add_item():
    name = request.form.get("name")
    price = request.form.get("price")
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
                create_menu_item(name, float(price), db_image_path)
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
                update_menu_item(item_id, name, float(price), db_image_path)
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


# ⬇️ this should stay last
if __name__ == "__main__":
    app.run(debug=True)
