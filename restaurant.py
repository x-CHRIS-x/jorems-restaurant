from flask import Flask, render_template, request, session, redirect, url_for, flash
from crud import *
from functools import wraps

app = Flask(__name__)
app.secret_key = "legaspixyz"
    # Removed teardown_appcontext(close_db) since close_db is not imported

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
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

        flash("Registration successful! Please log in.")
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


@app.route("/budget_mode", methods=["POST"])
def budget_mode():
    budget = float(request.form.get("budget_value", 0))
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
        if user and user['password'] == password:
            session["logged_in"] = True
            session["username"] = username
            session["user_id"] = user['id']
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Invalid username or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    session.pop("username", None)
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
    return render_template("checkout_confirm.html", cart=cart_items)

@app.route("/confirm_checkout", methods=["POST"])
@login_required
def confirm_checkout():
    cart_items = session.get("cart", [])
    total = sum(item['subtotal'] for item in cart_items)
    # Optionally persist order with order number
    if session.get("logged_in"):
        user_id = session.get("user_id")
        try:
            create_order(user_id, str(cart_items), total, status="pending")
        except Exception:
            pass
    session["cart"] = []
    session.modified = True
    return render_template("checkout_success.html", order=cart_items, total=total)

@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    cart_items = session.get("cart", [])
    total = sum(item['subtotal'] for item in cart_items)
    if session.get("logged_in"):
        user_id = session.get("user_id")
        try:
            create_order(user_id, str(cart_items), total, status="pending")
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

if __name__ == "__main__":
    app.run(debug=True)
