
from flask import Flask, render_template, request, session, redirect, url_for, flash
from db import init_db
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


@app.route("/")
def index():
    menu = get_menu_items()  # Use get_menu_items() from crud.py
    return render_template("index.html", menu=menu)

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

@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    cart_items = session.get("cart", [])
    total = sum(item['subtotal'] for item in cart_items)
    session["cart"] = []
    session.modified = True
    return render_template("checkout_success.html", order=cart_items, total=total)

@app.route("/clear_cart", methods=["POST"])
def clear_cart():
    session["cart"] = []
    session.modified = True
    return redirect(url_for("cart"))

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
