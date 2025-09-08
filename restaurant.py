from flask import Flask, render_template, request

app = Flask(__name__)

# Sample menu (in-memory, no database)
menu = [
	{"name": "Tapsilog", "price": 120, "available": True, "daily_limit": 10, "ordered_today": 0},
	{"name": "Longsilog", "price": 100, "available": True, "daily_limit": 10, "ordered_today": 0},
	{"name": "Pancit Canton", "price": 80, "available": True, "daily_limit": 10, "ordered_today": 0},
	{"name": "Burger Meal", "price": 150, "available": True, "daily_limit": 5, "ordered_today": 0},
	{"name": "Chicken Sandwich", "price": 130, "available": True, "daily_limit": 5, "ordered_today": 0},
]

@app.route('/')
def index():
	return render_template("index.html", menu=menu)

@app.route('/budget', methods=['GET', 'POST'])
def budget():
	suggested = []
	budget = 0
	if request.method == 'POST':
		budget = float(request.form.get("budget", 0))
		# Only suggest available items within budget
		suggested = [
			item for item in menu 
			if item['available'] and item['price'] <= budget and item['ordered_today'] < item['daily_limit']
		]
	return render_template("budget.html", suggested=suggested, budget=budget)

if __name__ == "__main__":
	app.run(debug=True)
