from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, UserAuth, TechnicianProfile, ComplaintLockerProfile
from extensions import db

auth_routes = Blueprint("auth_routes", __name__)


def _build_unique_username(email: str) -> str:
    base = (email.split("@")[0] or "user").strip().lower()
    candidate = base
    suffix = 1
    while User.query.filter_by(username=candidate).first():
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


@auth_routes.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        auth = UserAuth.query.filter_by(email=email).first()
        if auth and check_password_hash(auth.password_hash, password):
            user = auth.user
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role

            flash("Logged in successfully!", "success")
            if user.role == "technician":
                return redirect(url_for("main_routes.technician_dashboard"))
            if user.role == "complaint_locker":
                return redirect(url_for("main_routes.locker_dashboard"))
            if user.role == "admin":
                return redirect(url_for("main_routes.admin_dashboard"))
            return redirect(url_for("main_routes.dashboard"))

        flash("Invalid email or password", "danger")

    return render_template("login.html")


# @auth_routes.route("/register", methods=["GET", "POST"])
# def register():
#     if request.method == "POST":
#         email = request.form.get("email", "").strip().lower()
#         password = request.form.get("password", "")
#         full_name = request.form.get("full_name", "").strip() or None
#         contact = request.form.get("contact", "").strip() or None
#         role = request.form.get("role", "").strip()
#         skill = request.form.get("skill", "").strip()

#         allowed_roles = {"technician", "complain_locker", "other"}

#         if not email or not password or role not in allowed_roles:
#             flash("Email, password, and valid role are required.", "danger")
#             return render_template("register.html")

#         if role == "technician" and not skill:
#             flash("Skill is required for technician role.", "danger")
#             return render_template("register.html")

#         if UserAuth.query.filter_by(email=email).first():
#             flash("Email already exists", "danger")
#             return render_template("register.html")

#         try:
#             user = User(
#                 username=_build_unique_username(email),
#                 full_name=full_name,
#                 contact=contact,
#                 role=role,
#             )
#             db.session.add(user)
#             db.session.flush()

#             auth = UserAuth(
#                 user_id=user.id,
#                 email=email,
#                 password_hash=generate_password_hash(password),
#             )
#             db.session.add(auth)

#             if role == "technician":
#                 db.session.add(TechnicianProfile(user_id=user.id, skills=skill))

#             db.session.commit()
#             flash("Account created! Please login.", "success")
#             return redirect(url_for("auth_routes.login"))
#         except Exception:
#             db.session.rollback()
#             flash("Registration failed. Please try again.", "danger")

#     return render_template("register.html")
@auth_routes.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip() or None
        contact = request.form.get("contact", "").strip() or None
        role = request.form.get("role", "").strip()
        skill = request.form.get("skill", "").strip()

        allowed_roles = {"technician", "complaint_locker", "other"}

        if not email or not password or role not in allowed_roles:
            flash("Email, password, and valid role are required.", "danger")
            return render_template("register.html")

        if role == "technician" and not skill:
            flash("Skill is required for technician role.", "danger")
            return render_template("register.html")

        if UserAuth.query.filter_by(email=email).first():
            flash("Email already exists", "danger")
            return render_template("register.html")

        try:
            user = User(
                username=_build_unique_username(email),
                full_name=full_name,
                contact=contact,
                role=role,
                designation=None,   # <-- explicitly empty
                department=None,
                staff_no=None
            )
            db.session.add(user)
            db.session.flush()

            auth = UserAuth(
                user_id=user.id,
                email=email,
                password_hash=generate_password_hash(password),
            )
            db.session.add(auth)

            if role == "technician":
                db.session.add(
                    TechnicianProfile(
                        user_id=user.id,
                        skills=skill,
                        availability_status="available",
                        max_active_jobs=1,
                    )
                )
            elif role == "complaint_locker":
                db.session.add(
                    ComplaintLockerProfile(
                        user_id=user.id
                    )
                )

            db.session.commit()
            flash("Account created! Please login.", "success")
            return redirect(url_for("auth_routes.login"))

        except Exception:
            db.session.rollback()
            flash("Registration failed. Please try again.", "danger")

    return render_template("register.html")

@auth_routes.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for("auth_routes.login"))
