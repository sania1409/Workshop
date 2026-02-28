from flask import Blueprint, render_template, session, redirect, url_for
from models import Complaint, ServiceMemo, TechnicianProfile

main_routes = Blueprint("main_routes", __name__)


# -------------------------
# Home
# -------------------------
@main_routes.route("/")
def home():
    if "user_id" in session:
        # Auto redirect based on role
        role = session.get("role")

        if role == "technician":
            return redirect(url_for("main_routes.technician_dashboard"))

        if role == "complaint_locker":
            return redirect(url_for("main_routes.locker_dashboard"))

        if role == "admin":
            return redirect(url_for("main_routes.admin_dashboard"))

        return redirect(url_for("main_routes.dashboard"))

    return redirect(url_for("auth_routes.login"))


# -------------------------
# General Dashboard
# -------------------------
@main_routes.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth_routes.login"))

    return render_template("dashboard1.html")


# -------------------------
# Admin Dashboard
# -------------------------
@main_routes.route("/admin_dashboard")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("auth_routes.login"))

    pending_admin_memos = (
        ServiceMemo.query
        .filter(
            ServiceMemo.diagnosed.is_(True),
            ServiceMemo.task_performed.is_(False),
        )
        .order_by(ServiceMemo.last_updated.desc())
        .all()
    )
    completed_admin_memos = (
        ServiceMemo.query
        .filter(ServiceMemo.task_performed.is_(True))
        .order_by(ServiceMemo.last_updated.desc())
        .all()
    )

    return render_template(
        "admin_dashboard.html",
        pending_admin_memos=pending_admin_memos,
        completed_admin_memos=completed_admin_memos,
    )


# -------------------------
# Technician Dashboard
# -------------------------
@main_routes.route("/technician/dashboard")
def technician_dashboard():
    if "user_id" not in session or session.get("role") != "technician":
        return redirect(url_for("auth_routes.login"))

    user_id = session["user_id"]
    technician_profile = TechnicianProfile.query.filter_by(user_id=user_id).first()

    active_complaints = (
        Complaint.query
        .filter(
            Complaint.technician_id == user_id,
            Complaint.status.in_(["in_progress"]),
        )
        .order_by(Complaint.updated_at.desc(), Complaint.created_at.desc())
        .all()
    )
    completed_complaints = (
        Complaint.query
        .filter(
            Complaint.technician_id == user_id,
            Complaint.status == "closed",
        )
        .order_by(Complaint.updated_at.desc(), Complaint.created_at.desc())
        .all()
    )
    active_service_memos = (
        ServiceMemo.query
        .filter(
            ServiceMemo.assigned_to == user_id,
            ServiceMemo.task_performed.is_(False),
        )
        .order_by(ServiceMemo.last_updated.desc())
        .all()
    )
    completed_service_memos = (
        ServiceMemo.query
        .filter(
            ServiceMemo.assigned_to == user_id,
            ServiceMemo.task_performed.is_(True),
        )
        .order_by(ServiceMemo.last_updated.desc())
        .all()
    )

    return render_template(
        "technician_dashboard.html",
        technician_profile=technician_profile,
        active_complaints=active_complaints,
        completed_complaints=completed_complaints,
        active_service_memos=active_service_memos,
        completed_service_memos=completed_service_memos,
    )


# -------------------------
# Complaint Locker Dashboard
# -------------------------
@main_routes.route("/locker/dashboard")
def locker_dashboard():
    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    return render_template("locker_dashboard.html")
