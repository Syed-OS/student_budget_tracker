# app.py
from decimal import Decimal, ROUND_HALF_UP
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Response
import calendar
from datetime import datetime, date
from sqlalchemy import func
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from config import Config
from extensions import db, login_manager  # ✅ use the shared instances
from models import User, Budget, Expense, Quote

CATEGORIES = ["Food", "Transport", "Rent", "Books", "Supplies", "Fun", "Health", "Other"]

# --- App & Config ---
app = Flask(__name__)
app.config.from_object(Config)

# --- Jinja filters: money + date ---
@app.template_filter("money")
def money_filter(value):
    try:
        d = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"${d:,.2f}"
    except Exception:
        return "$0.00"

@app.template_filter("ymd")
def ymd_filter(dt):
    try:
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""

# Trust proxy headers (needed for real IP & HTTPS detection in production)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# CSRF protection
csrf = CSRFProtect(app)

# Rate limiter
limiter = Limiter(get_remote_address, app=app, default_limits=[])

# --- Init extensions ---
db.init_app(app)
login_manager.init_app(app)

# --- Create tables ---
with app.app_context():
    db.create_all()

# Handle CSRF errors globally
@app.errorhandler(CSRFError)
def handle_csrf(e):
    flash("Security check failed (CSRF). Please try again.", "error")
    return redirect(url_for("index")), 400

def month_bounds(ym: str | None) -> tuple[date, date, str]:
    """
    Returns (first_day, last_day, label) for a given 'YYYY-MM' string.
    If ym is None or invalid, uses the current month.
    """
    today = date.today()
    try:
        if ym:
            y, m = ym.split("-")
            y, m = int(y), int(m)
            first = date(y, m, 1)
        else:
            first = date(today.year, today.month, 1)
    except Exception:
        first = date(today.year, today.month, 1)

    last = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
    label = first.strftime("%B %Y")  # e.g., "August 2025"
    return first, last, label


def csv_safe(cell: str) -> str:
    """
    Prevent CSV injection for cells starting with = + - @
    """
    if not cell:
        return ""
    s = str(cell)
    if s[0] in ("=", "+", "-", "@"):
        return "'" + s
    return s


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
@limiter.limit("3 per minute")
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

@limiter.limit("5 per minute")
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
    from sqlalchemy import func
    today = date.today()
    first_day = date(today.year, today.month, 1)

    # Active budget
    active_budget = Budget.query.filter_by(
        user_id=current_user.id,
        start_date=first_day
    ).first()

    total_spent = 0
    percent_remaining = None

    if active_budget:
        total_spent = db.session.query(func.coalesce(func.sum(Expense.amount), 0))\
            .filter(
                Expense.user_id == current_user.id,
                Expense.date >= datetime(today.year, today.month, 1)
            ).scalar()

        remaining = active_budget.amount - total_spent
        percent_remaining = max(0, float(remaining) / float(active_budget.amount) * 100)

    expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= datetime(today.year, today.month, 1)
    ).order_by(Expense.date.desc()).limit(10).all()

    return render_template(
        "dashboard.html",
        user=current_user,
        budget=active_budget,
        expenses=expenses,
        total_spent=total_spent,
        percent_remaining=percent_remaining,
        categories=CATEGORIES,
        rollover_prompt=(active_budget is None)
        )

from datetime import date
import calendar
from flask import jsonify

@app.post("/set_budget")
@login_required
def set_budget():
    try:
        amount_str = request.form.get("amount", "").strip()
        if not amount_str:
            msg = "Please enter an amount."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": msg}), 400
            flash(msg, "error")
            return redirect(url_for("dashboard"))

        try:
            amount_val = float(amount_str)
        except ValueError:
            msg = "Invalid number format for budget."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": msg}), 400
            flash(msg, "error")
            return redirect(url_for("dashboard"))

        if amount_val <= 0:
            msg = "Amount must be greater than zero."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": msg}), 400
            flash(msg, "error")
            return redirect(url_for("dashboard"))

        today = date.today()
        first_day = date(today.year, today.month, 1)
        last_day = date(today.year, today.month,
                        calendar.monthrange(today.year, today.month)[1])

        budget = Budget.query.filter_by(
            user_id=current_user.id,
            start_date=first_day
        ).first()

        if budget:
            budget.amount = float(budget.amount) + amount_val
            budget.end_date = last_day
            success_msg = f"Added ${amount_val:.2f} to this month's budget."
        else:
            budget = Budget(
                user_id=current_user.id,
                amount=amount_val,
                start_date=first_day,
                end_date=last_day
            )
            db.session.add(budget)
            success_msg = f"Budget set to ${amount_val:.2f} for this month."

        db.session.commit()

        # Calculate updated percent for health bar
        from sqlalchemy import func
        total_spent = db.session.query(func.coalesce(func.sum(Expense.amount), 0))\
            .filter(
                Expense.user_id == current_user.id,
                Expense.date >= first_day
            ).scalar()

        percent_remaining = max(0, (float(budget.amount) - float(total_spent)) / float(budget.amount) * 100)

        # If AJAX request, return JSON
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "success": success_msg,
                "budget": float(budget.amount),
                "total_spent": float(total_spent),
                "remaining": float(budget.amount) - float(total_spent),
                "percent": percent_remaining
            })

        flash(success_msg, "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        app.logger.error(f"Error in set_budget: {e}")
        msg = "An unexpected error occurred while setting the budget."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg}), 500
        flash(msg, "error")
        return redirect(url_for("dashboard"))

from datetime import datetime

@limiter.limit("10 per minute") 
@app.post("/add_expense")
@login_required
def add_expense():
    try:
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        note = request.form.get("note", "").strip()

        if not amount or float(amount) <= 0:
            msg = "Please enter a valid expense amount."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": msg}), 400
            flash(msg, "error")
            return redirect(url_for("dashboard"))

        if not category:
            msg = "Category is required."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": msg}), 400
            flash(msg, "error")
            return redirect(url_for("dashboard"))
        
        # Find current month's budget
        today = date.today()
        first_day = date(today.year, today.month, 1)
        active_budget = Budget.query.filter_by(
            user_id=current_user.id,
            start_date=first_day
        ).first()

        if active_budget:
            from sqlalchemy import func
            total_spent = db.session.query(func.coalesce(func.sum(Expense.amount), 0))\
                .filter(
                    Expense.user_id == current_user.id,
                    Expense.date >= datetime(today.year, today.month, 1)
                ).scalar()
            remaining = float(active_budget.amount) - float(total_spent)

            if float(amount) > remaining:
                msg = "You cannot spend more than your remaining budget."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"error": msg}), 400
                flash(msg, "error")
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

        # Compute updated budget percent
        today = date.today()
        first_day = date(today.year, today.month, 1)
        active_budget = Budget.query.filter_by(
            user_id=current_user.id,
            start_date=first_day
        ).first()

        percent_remaining = None
        remaining = None
        if active_budget:
            from sqlalchemy import func
            total_spent = db.session.query(func.coalesce(func.sum(Expense.amount), 0))\
                .filter(
                    Expense.user_id == current_user.id,
                    Expense.date >= datetime(today.year, today.month, 1)
                ).scalar()
            remaining = float(active_budget.amount) - float(total_spent)
            percent_remaining = max(0, remaining / float(active_budget.amount) * 100)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "success": "Expense added.",
                "remaining": remaining,
                "percent": percent_remaining
            })

        flash("Expense added.", "success")
    except ValueError:
        msg = "Invalid number format for expense."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg}), 400
        flash(msg, "error")

    return redirect(url_for("dashboard"))

@app.get("/expense/<int:expense_id>/edit")
@login_required
def edit_expense(expense_id):
    exp = Expense.query.get_or_404(expense_id)
    if exp.user_id != current_user.id:
        flash("Not authorized.", "error")
        return redirect(url_for("dashboard"))
    return render_template("expense_edit.html", expense=exp, categories=CATEGORIES)

@app.post("/expense/<int:expense_id>/edit")
@login_required
def update_expense(expense_id):
    exp = Expense.query.get_or_404(expense_id)
    if exp.user_id != current_user.id:
        flash("Not authorized.", "error")
        return redirect(url_for("dashboard"))

    try:
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        note = request.form.get("note", "").strip()

        if not amount or float(amount) <= 0:
            flash("Please enter a valid amount.", "error")
            return redirect(url_for("edit_expense", expense_id=expense_id))
        if not category:
            flash("Category is required.", "error")
            return redirect(url_for("edit_expense", expense_id=expense_id))

        exp.amount = amount
        exp.category = category
        exp.note = note or None
        db.session.commit()
        flash("Expense updated.", "success")
    except ValueError:
        flash("Invalid number format.", "error")

    return redirect(url_for("dashboard"))

@app.post("/expense/<int:expense_id>/delete")
@login_required
def delete_expense(expense_id):
    exp = Expense.query.get_or_404(expense_id)
    if exp.user_id != current_user.id:
        flash("Not authorized.", "error")
        return redirect(url_for("dashboard"))

    db.session.delete(exp)
    db.session.commit()
    flash("Expense deleted.", "success")
    return redirect(url_for("dashboard"))

import random
from flask import jsonify

@app.get("/get_quote")
@login_required
def get_quote():
    quote = Quote.query.order_by(db.func.random()).first()
    if quote:
        return jsonify({"quote": quote.text})
    return jsonify({"quote": "No quotes found."})

@app.get("/stats/categories")
@login_required
def stats_categories():
    from sqlalchemy import func
    today = date.today()
    first_day = date(today.year, today.month, 1)

    rows = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label("total")
    ).filter(
        Expense.user_id == current_user.id,
        Expense.date >= datetime(today.year, today.month, 1)
    ).group_by(Expense.category).all()

    data = {cat: float(total) for cat, total in rows}
    return jsonify(data)


@app.get("/stats/daily")
@login_required
def stats_daily():
    from sqlalchemy import func
    today = date.today()
    first_day = date(today.year, today.month, 1)

    rows = db.session.query(
        func.strftime("%Y-%m-%d", Expense.date),  # date as string
        func.sum(Expense.amount).label("total")
    ).filter(
        Expense.user_id == current_user.id,
        Expense.date >= datetime(today.year, today.month, 1)
    ).group_by(func.strftime("%Y-%m-%d", Expense.date))\
     .order_by(func.strftime("%Y-%m-%d", Expense.date)).all()

    # cumulative sum
    daily_totals = {}
    running_total = 0
    for day_str, total in rows:
        running_total += float(total)
        daily_totals[day_str] = running_total

    return jsonify(daily_totals)

@app.get("/summary")
@login_required
def summary():
    ym = request.args.get("month")  # format: YYYY-MM
    first, last, label = month_bounds(ym)

    # Active (or historical) budget for that month (by start_date)
    budget = Budget.query.filter_by(user_id=current_user.id, start_date=first).first()

    # Totals for that month
    total_spent = db.session.query(func.coalesce(func.sum(Expense.amount), 0))\
        .filter(
            Expense.user_id == current_user.id,
            Expense.date >= datetime(first.year, first.month, 1),
            Expense.date < datetime(last.year, last.month, last.day, 23, 59, 59)
        ).scalar()

    # Top categories
    cat_rows = db.session.query(
        Expense.category, func.sum(Expense.amount).label("total")
    ).filter(
        Expense.user_id == current_user.id,
        Expense.date >= datetime(first.year, first.month, 1),
        Expense.date < datetime(last.year, last.month, last.day, 23, 59, 59)
    ).group_by(Expense.category).order_by(func.sum(Expense.amount).desc()).all()

    top_categories = [(c, float(t)) for c, t in cat_rows]

    # Biggest single expense
    biggest = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= datetime(first.year, first.month, 1),
        Expense.date < datetime(last.year, last.month, last.day, 23, 59, 59)
    ).order_by(Expense.amount.desc()).first()

    # Remaining (only if a budget exists)
    remaining = float(budget.amount) - float(total_spent) if budget else None

    # Average daily spend (over days elapsed in that month if current; else full month)
    today = date.today()
    if first.year == today.year and first.month == today.month:
        days_elapsed = max(1, today.day)  # at least 1
    else:
        days_elapsed = (last - first).days + 1
    avg_daily = float(total_spent) / days_elapsed if days_elapsed else 0.0

    return render_template(
        "summary.html",
        month_label=label,
        month_param=first.strftime("%Y-%m"),
        budget=budget,
        total_spent=float(total_spent or 0),
        remaining=remaining,
        avg_daily=avg_daily,
        top_categories=top_categories,
        biggest=biggest
    )


@app.get("/summary.csv")
@login_required
def summary_csv():
    ym = request.args.get("month")
    first, last, label = month_bounds(ym)

    rows = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= datetime(first.year, first.month, 1),
        Expense.date < datetime(last.year, last.month, last.day, 23, 59, 59)
    ).order_by(Expense.date.asc()).all()

    def generate():
        yield "date,category,note,amount\n"
        for r in rows:
            d = r.date.strftime("%Y-%m-%d")
            cat = csv_safe(r.category or "")
            note = csv_safe(r.note or "")
            amt = f"{float(r.amount):.2f}"
            # basic CSV escaping for commas/quotes
            def esc(x: str) -> str:
                if "," in x or '"' in x:
                    return '"' + x.replace('"', '""') + '"'
                return x
            yield f"{d},{esc(cat)},{esc(note)},{amt}\n"

    filename = f"expenses_{first.strftime('%Y_%m')}.csv"
    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# Debug URL map
with app.app_context():
    print("\n=== URL MAP ===")
    for rule in app.url_map.iter_rules():
        print(rule)
    print("==============\n")

@app.after_request
def add_security_headers(resp):
    csp = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )
    resp.headers["Content-Security-Policy"] = csp
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp

if __name__ == "__main__":
    app.run(debug=True)
