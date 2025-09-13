
from flask import Flask, render_template, request, session, redirect, url_for

app = Flask(__name__)
app.secret_key = "legaspixyz"  # needed for session

menu = [
    {'id': 1, 'name': 'Tapsilog', 'price': 120},
    {'id': 2, 'name': 'Longsilog', 'price': 100},
    {'id': 3, 'name': 'Tocilog', 'price': 100},
    {'id': 4, 'name': 'Hotsilog', 'price': 90},
    {'id': 5, 'name': 'Bangsilog', 'price': 110},
    {'id': 6, 'name': 'Burger Combo', 'price': 150},
    {'id': 7, 'name': 'Spaghetti Combo', 'price': 140},
    {'id': 8, 'name': 'Chicken with Rice', 'price': 130},
    {'id': 9, 'name': 'Burger Steak with Rice', 'price': 135}
]

@app.route("/")
def index():
    return render_template("index.html", menu=menu)

@app.route("/order", methods=["POST"])
def order():
    if "cart" not in session:
        session["cart"] = []
    cart = session["cart"]
    for item in menu:
        qty = int(request.form.get(f"quantity_{item['id']}", 0))
        if qty > 0:
            # Check if item already in cart
            found = False
            for cart_item in cart:
                if cart_item["name"] == item["name"]:
                    cart_item["qty"] += qty
                    cart_item["subtotal"] += qty * item["price"]
                    found = True
                    break
            if not found:
                cart.append({
                    "name": item["name"],
                    "qty": qty,
                    "subtotal": qty * item["price"]
                })
    session["cart"] = cart
    session.modified = True
    return redirect(url_for("cart"))

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
                "subtotal": subtotal
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
    # This accepts order even if over budget
    items = []
    total = float(request.form.get("total", 0))
    print("/order_confirm POST data:", dict(request.form))  # DEBUG
    # Collect all items from the form
    for item in menu:
        item_id = str(item["id"])
        name = request.form.get(f"item_name_{item_id}")
        qty = request.form.get(f"item_qty_{item_id}")
        subtotal = request.form.get(f"item_subtotal_{item_id}")
        if name and qty and subtotal:
            try:
                qty = int(qty)
                subtotal = float(subtotal)
            except ValueError:
                continue
            items.append({"name": name, "qty": qty, "subtotal": subtotal})
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

@app.route("/cart")
def cart():
    return render_template("cart.html", cart=session.get("cart", []))

@app.route("/clear_cart", methods=["POST"])
def clear_cart():
    session["cart"] = []
    session.modified = True
    return redirect(url_for("cart"))

if __name__ == "__main__":
    app.run(debug=True)
