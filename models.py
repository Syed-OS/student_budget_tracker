# models.py
from datetime import datetime, date
from sqlalchemy import Numeric, UniqueConstraint, Index
from flask_login import UserMixin
from extensions import db, login_manager


# ----------------------
# User model
# ----------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    budgets = db.relationship("Budget", backref="user", lazy=True)
    expenses = db.relationship("Expense", backref="user", lazy=True)

    def get_id(self):
        return str(self.id)


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))


# ----------------------
# Budget model (one per month)
# ----------------------
class Budget(db.Model):
    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(Numeric(10, 2), nullable=False)  # money-safe
    start_date = db.Column(db.Date, nullable=False)     # first day of month
    end_date = db.Column(db.Date, nullable=False)       # last day of month

    __table_args__ = (
        UniqueConstraint("user_id", "start_date", name="uq_budget_user_month"),
        Index("ix_budget_user_month", "user_id", "start_date"),
    )


# ----------------------
# Expense model
# ----------------------
class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(Numeric(10, 2), nullable=False)  # money-safe
    category = db.Column(db.String(50), nullable=False, index=True)
    note = db.Column(db.String(255), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_expenses_user_date", "user_id", "date"),
    )


# ----------------------
# Quote model
# ----------------------
class Quote(db.Model):
    __tablename__ = "quotes"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=True)
