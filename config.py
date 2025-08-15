import os
from dotenv import load_dotenv

# Load .env (Gunicorn doesn't auto-load it)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Config:
    # Secrets
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-insecure-fallback-change-me")

    # Database (SQLite file in project root)
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session cookie hardening (turn these ON in production)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # SESSION_COOKIE_SECURE = True  # uncomment when on HTTPS

    # CSRF settings (Flask-WTF)
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 2  # 2 hours
    WTF_CSRF_METHODS = ["POST", "PUT", "PATCH", "DELETE"]

    # Optionally expose X-RateLimit-* headers
    RATELIMIT_HEADERS_ENABLED = True

