from flask import Blueprint, redirect, render_template, session, url_for

from database import get_dashboard_stats, get_recent_logs

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required():
    return "admin_id" in session


@admin_bp.route("/")
def home():
    if not admin_required():
        return redirect(url_for("auth.login"))
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/dashboard")
def dashboard():
    if not admin_required():
        return redirect(url_for("auth.login"))
    return render_template(
        "dashboard.html",
        stats=get_dashboard_stats(),
        logs=get_recent_logs(10),
        admin_name=session.get("admin_name", "Administrator"),
    )
