
from flask import Flask, render_template, request, session, redirect, url_for, flash
from functools import wraps

app = Flask(__name__)
app.secret_key = "legaspixyz"

menu = [
    {'id': 1, 'name': 'Tapsilog <br> Masarap to luto ni Marc Jorem Legazpi', 'price': 120, 'image': 'images/tapsilog.jpg'},
    {'id': 2, 'name': 'Longsilog', 'price': 100, 'image': 'images/longsilog.jpg'},
    {'id': 3, 'name': 'Tocilog', 'price': 100, 'image': 'images/tocilog.jpg'},
    {'id': 4, 'name': 'Hotsilog', 'price': 90, 'image': 'images/hotsilog.jpg'},
    {'id': 5, 'name': 'Bangsilog', 'price': 110, 'image': 'images/bangsilog.jpg'},
    {'id': 6, 'name': 'Burger Combo', 'price': 150, 'image': 'images/burger-combo.jpg'},
    {'id': 7, 'name': 'Spaghetti Combo', 'price': 140, 'image': 'images/spaghetti-combo.jpg'},
    {'id': 8, 'name': 'Chicken with Rice', 'price': 130, 'image': 'images/chicken-rice.jpg'},
    {'id': 9, 'name': 'Burger Steak with Rice', 'price': 135, 'image': 'images/burger-steak.jpg'}
]

users = {
    "user1": "pass1",
    "user2": "pass2"
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def index():
    return render_template("index.html", menu=menu)

@app.route("/add_item", methods=["POST"])
def add_item():
    """Adds a single item to the cart."""
    if "cart" not in session:
        session["cart"] = []
    cart = session["cart"]

    item_id = int(request.form.get("item_id"))
    quantity = int(request.form.get("quantity", 0))
    
    item_to_add = next((item for item in menu if item['id'] == item_id), None)

    if item_to_add and quantity > 0:
        found = False
        for cart_item in cart:
            if cart_item["name"] == item_to_add["name"]:
                cart_item["qty"] += quantity
                cart_item["subtotal"] += quantity * item_to_add["price"]
                found = True
                break
        if not found:
            cart.append({"name": item_to_add["name"], "qty": quantity, "subtotal": quantity * item_to_add["price"], "image": item_to_add["image"]})
        flash(f'Added {quantity} x {item_to_add["name"]} to your cart.', 'success')
    session["cart"] = cart
    session.modified = True
    return redirect(url_for("index"))

@app.route("/budget", methods=["POST"])
def budget():
    budget = float(request.form.get("budget", 0))
    suggested = [item for item in menu if item["price"] <= budget]
    return render_template("budget.html", suggested=suggested, budget=budget)

@app.route("/budget_order", methods=["POST"])
def budget_order():
    budget = float(request.form.get("budget_value", 0))
    total = 0
    selected_items = []

    for item in menu:
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
    for item in menu:
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
        if username in users and users[username] == password:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("cart"))
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
    app.run(debug=True)
