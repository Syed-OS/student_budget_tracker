from flask import Flask
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Tiny sanity endpoint (optional, for later testing)
@app.get("/health")
def health():
    return "ok"

if __name__ == "__main__":
    # Dev server (we'll switch to gunicorn in production)
    app.run(debug=True)
