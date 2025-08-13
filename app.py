# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from config import Config
from extensions import db, login_manager  # ✅ use the shared instances
from models import User, Budget, Expense, Quote

# --- App & Config ---
app = Flask(__name__)
app.config.from_object(Config)

# --- Init extensions ---
db.init_app(app)
login_manager.init_app(app)

# --- Create tables ---
with app.app_context():
    db.create_all()

# ---------- ROUTES ----------

@app.get("/health")
def health():
    return "ok"

@app.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# ---------- AUTH ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("signup"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("signup"))
        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("signup"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return redirect(url_for("signup"))

        hashed = generate_password_hash(password)
        u = User(username=username, email=email, password_hash=hashed)
        db.session.add(u)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        login_user(user)
        flash("Logged in.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@app.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("login"))

@app.get("/dashboard")
@login_required
def dashboard():
    today = date.today()
    first_day = date(today.year, today.month, 1)

    active_budget = Budget.query.filter_by(
        user_id=current_user.id,
        start_date=first_day
    ).first()

    expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= datetime(today.year, today.month, 1)
    ).order_by(Expense.date.desc()).limit(10).all()

    return render_template(
        "dashboard.html",
        user=current_user,
        budget=active_budget,
        expenses=expenses
    )


from datetime import date
import calendar

@app.post("/set_budget")
@login_required
def set_budget():
    try:
        amount = request.form.get("amount", "").strip()
        if not amount or float(amount) <= 0:
            flash("Please enter a valid budget amount.", "error")
            return redirect(url_for("dashboard"))

        today = date.today()
        first_day = date(today.year, today.month, 1)
        last_day = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])

        # Check if budget exists for this month
        budget = Budget.query.filter_by(user_id=current_user.id, start_date=first_day).first()
        if budget:
            budget.amount = amount
            budget.end_date = last_day
            flash("Budget updated for this month.", "success")
        else:
            budget = Budget(
                user_id=current_user.id,
                amount=amount,
                start_date=first_day,
                end_date=last_day
            )
            db.session.add(budget)
            flash("Budget set for this month.", "success")

        db.session.commit()
    except ValueError:
        flash("Invalid number format for budget.", "error")

    return redirect(url_for("dashboard"))

from datetime import datetime

@app.post("/add_expense")
@login_required
def add_expense():
    try:
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        note = request.form.get("note", "").strip()

        if not amount or float(amount) <= 0:
            flash("Please enter a valid expense amount.", "error")
            return redirect(url_for("dashboard"))
        if not category:
            flash("Category is required.", "error")
            return redirect(url_for("dashboard"))

        expense = Expense(
            user_id=current_user.id,
            amount=amount,
            category=category,
            note=note or None,
            date=datetime.utcnow()
        )
        db.session.add(expense)
        db.session.commit()
        flash("Expense added.", "success")
    except ValueError:
        flash("Invalid number format for expense.", "error")

    return redirect(url_for("dashboard"))


# Debug URL map
with app.app_context():
    print("\n=== URL MAP ===")
    for rule in app.url_map.iter_rules():
        print(rule)
    print("==============\n")

if __name__ == "__main__":
    app.run(debug=True)
