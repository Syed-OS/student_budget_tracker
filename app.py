# app.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

# --- App & Config ---
app = Flask(__name__)
app.config.from_object(Config)

# --- Extensions ---
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"  # where to send unauthenticated users later

# --- Simple health check (sanity test) ---
@app.get("/health")
def health():
    return "ok"

if __name__ == "__main__":
    # Dev server (we'll use gunicorn in production)
    app.run(debug=True)
