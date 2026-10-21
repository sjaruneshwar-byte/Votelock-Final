import os

from dotenv import load_dotenv
from flask import Flask, redirect, url_for, render_template

from database import init_db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key")

init_db()

from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.voters import voters_bp
from routes.candidates import candidates_bp
from routes.qr import qr_bp
from routes.voting import voting_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(voters_bp)
app.register_blueprint(candidates_bp)
app.register_blueprint(qr_bp)
app.register_blueprint(voting_bp)


@app.route("/")
def index():
    # First screen asks whether this is an administrator or voter session.
    return render_template("role_select.html")


@app.route("/health")
def health():
    return {"status": "ok", "application": "VoteLock"}


if __name__ == "__main__":
    print("=" * 60)
    print("VoteLock Smart Electronic Voting System")
    print("=" * 60)
    print("Admin login     : http://127.0.0.1:5000/login")
    print("Admin register  : http://127.0.0.1:5000/register")
    print("Voter portal    : http://127.0.0.1:5000/voter/login")
    print("Admin verify    : http://127.0.0.1:5000/qr/scanner")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
