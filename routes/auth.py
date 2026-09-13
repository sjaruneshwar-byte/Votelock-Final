import hashlib
import os
import secrets
import smtplib
import time
from email.message import EmailMessage

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import add_audit_log, get_db, get_voter, get_voter_by_username


auth_bp = Blueprint("auth", __name__)


def _clear_registration_session():
    for key in (
        "registration_name",
        "registration_email",
        "registration_password",
        "registration_otp",
        "otp_expiry",
    ):
        session.pop(key, None)


def send_otp_email(receiver_email, otp):
    sender_email = os.getenv("SMTP_EMAIL") or os.getenv("MAIL_USERNAME")
    sender_password = os.getenv("SMTP_PASSWORD") or os.getenv("MAIL_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")

    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        smtp_port = 587

    if not sender_email or not sender_password:
        print("[VoteLock] SMTP_EMAIL/SMTP_PASSWORD is missing.")
        print(f"[VoteLock DEMO] OTP for {receiver_email}: {otp}")
        return False

    message = EmailMessage()
    message["Subject"] = "VoteLock Admin Registration OTP"
    message["From"] = sender_email
    message["To"] = receiver_email
    message.set_content(
        f"""Hello,

Your VoteLock administrator registration OTP is:

{otp}

This OTP is valid for 10 minutes.

Regards,
VoteLock Smart Electronic Voting System
"""
    )

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password.replace(" ", ""))
            server.send_message(message)
        print(f"[VoteLock] OTP sent successfully to {receiver_email}")
        return True
    except Exception as exc:
        print(f"[VoteLock] Email error: {type(exc).__name__}: {exc}")
        print(f"[VoteLock DEMO] OTP for {receiver_email}: {otp}")
        return False


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter email and password.", "error")
            return redirect(url_for("auth.login"))

        conn = get_db()
        admin = conn.execute("SELECT * FROM admins WHERE email=?", (email,)).fetchone()
        conn.close()

        if not admin or not check_password_hash(admin["password_hash"], password):
            flash("Invalid administrator credentials.", "error")
            return redirect(url_for("auth.login"))

        if not admin["is_verified"]:
            flash("Please verify your email before logging in.", "error")
            return redirect(url_for("auth.login"))

        session.clear()
        session["admin_id"] = admin["id"]
        session["admin_name"] = admin["name"]
        session["admin_email"] = admin["email"]
        add_audit_log("ADMIN_LOGIN", f"Administrator {email} logged in.")
        return redirect(url_for("admin.dashboard"))

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("auth.register"))
        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("auth.register"))
        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("auth.register"))

        conn = get_db()
        exists = conn.execute("SELECT id FROM admins WHERE email=?", (email,)).fetchone()
        conn.close()
        if exists:
            flash("An administrator with this email already exists.", "error")
            return redirect(url_for("auth.login"))

        otp = f"{secrets.randbelow(900000) + 100000}"
        session["registration_name"] = name
        session["registration_email"] = email
        session["registration_password"] = generate_password_hash(password)
        session["registration_otp"] = hashlib.sha256(otp.encode()).hexdigest()
        session["otp_expiry"] = time.time() + 600

        if not send_otp_email(email, otp):
            # Keep the OTP session for demo mode so the terminal OTP can still be used.
            flash("Email delivery failed. For the lab demo, use the OTP printed in the terminal.", "error")
        else:
            flash("OTP sent to your email address.", "success")

        return redirect(url_for("auth.verify_otp"))

    return render_template("register.html")


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if "registration_email" not in session:
        flash("Please register first.", "error")
        return redirect(url_for("auth.register"))

    if request.method == "POST":
        entered = request.form.get("otp", "").strip()
        if not entered or not entered.isdigit() or len(entered) != 6:
            flash("Enter the 6-digit OTP.", "error")
            return redirect(url_for("auth.verify_otp"))

        if time.time() > float(session.get("otp_expiry", 0)):
            _clear_registration_session()
            flash("OTP expired. Please register again.", "error")
            return redirect(url_for("auth.register"))

        entered_hash = hashlib.sha256(entered.encode()).hexdigest()
        if entered_hash != session.get("registration_otp"):
            flash("Invalid OTP. Please try again.", "error")
            return redirect(url_for("auth.verify_otp"))

        name = session["registration_name"]
        email = session["registration_email"]
        password_hash = session["registration_password"]

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO admins(name,email,password_hash,is_verified) VALUES(?,?,?,1)",
                (name, email, password_hash),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            flash("An administrator with this email already exists.", "error")
            return redirect(url_for("auth.login"))
        conn.close()

        _clear_registration_session()
        add_audit_log("ADMIN_REGISTERED", f"Administrator {email} verified registration.")
        flash("Registration successful. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    remaining = max(0, int(float(session.get("otp_expiry", 0)) - time.time()))
    return render_template(
        "verify_otp.html",
        email=session.get("registration_email"),
        remaining_seconds=remaining,
    )


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/voter/login", methods=["GET", "POST"])
def voter_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().upper()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Enter voter username and password.", "error")
            return redirect(url_for("auth.voter_login"))

        voter = get_voter_by_username(username)
        if not voter or not voter["password_hash"]:
            flash("Invalid voter credentials.", "error")
            return redirect(url_for("auth.voter_login"))

        if not check_password_hash(voter["password_hash"], password):
            flash("Invalid voter credentials.", "error")
            return redirect(url_for("auth.voter_login"))

        if voter["has_voted"]:
            flash("This voter has already voted.", "error")
            return redirect(url_for("auth.voter_login"))

        session.clear()
        session["voter_id"] = voter["voter_id"]
        session["voter_name"] = voter["name"]
        session["voter_username"] = voter["username"]
        session["voter_authenticated"] = True
        add_audit_log("VOTER_LOGIN", f"Voter {voter['voter_id']} opened the voter portal.", voter["voter_id"])
        return redirect(url_for("auth.voter_portal"))

    return render_template("voter_login.html")


@auth_bp.route("/voter/portal")
def voter_portal():
    if not session.get("voter_authenticated") or not session.get("voter_id"):
        return redirect(url_for("auth.voter_login"))

    voter = get_voter(session["voter_id"])
    if not voter:
        session.clear()
        flash("Voter account was not found.", "error")
        return redirect(url_for("auth.voter_login"))

    if voter["has_voted"]:
        session.clear()
        flash("This voter has already voted.", "error")
        return redirect(url_for("auth.voter_login"))

    return render_template("voter_qr.html", voter=voter)


@auth_bp.route("/voter/logout")
def voter_logout():
    voter_id = session.get("voter_id")
    if voter_id:
        add_audit_log("VOTER_LOGOUT", f"Voter {voter_id} left the voter portal.", voter_id)
    session.clear()
    return redirect(url_for("auth.voter_login"))
