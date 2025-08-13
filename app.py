from flask import Flask
from config import Config
from extensions import db, login_manager

# --- App & Config ---
app = Flask(__name__)
app.config.from_object(Config)

# --- Initialize extensions ---
db.init_app(app)
login_manager.init_app(app)

# --- Import models AFTER init ---
from models import User, Budget, Expense, Quote

with app.app_context():
    db.create_all()

# --- Routes ---
@app.get("/health")
def health():
    return "ok"

if __name__ == "__main__":
    app.run(debug=True)
