from flask import Blueprint, render_template, redirect, url_for, request, flash, session
import re
from werkzeug.security import generate_password_hash, check_password_hash
try:
    from passlib.hash import scrypt as passlib_scrypt
except Exception:  # pragma: no cover - optional dependency
    passlib_scrypt = None
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


def _valid_password(password: str) -> bool:
    # Minimum 7 characters and at least one number or special character.
    return bool(password) and len(password) >= 7 and re.search(r"[0-9\W_]", password)


def _verify_password(stored_hash: str, password: str) -> bool:
    if not stored_hash:
        return False
    try:
        return check_password_hash(stored_hash, password)
    except ValueError:
        if passlib_scrypt and stored_hash.startswith("$scrypt$"):
            return passlib_scrypt.verify(password, stored_hash)
        return False


@auth_routes.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        auth = UserAuth.query.filter_by(email=email).first()
        if auth and _verify_password(auth.password_hash, password):
            if auth.password_hash.startswith("$scrypt$"):
                auth.password_hash = generate_password_hash(password)
                db.session.commit()
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
    if "user_id" not in session or session.get("role") != "admin":
        flash("Only admin can register new users.", "danger")
        return redirect(url_for("auth_routes.login"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip() or None
        contact = request.form.get("contact", "").strip() or None
        staff_no = request.form.get("staff_no", "").strip().upper() or None
        role = request.form.get("role", "").strip()
        skill = request.form.get("skill", "").strip()

        allowed_roles = {"technician", "complaint_locker", "other"}

        if not email or not password or role not in allowed_roles:
            flash("Email, password, and valid role are required.", "danger")
            return render_template("register.html")

        if not _valid_password(password):
            flash("Password must be at least 7 characters and include at least one number or special character.", "danger")
            return render_template("register.html")

        if not staff_no:
            flash("Staff No is required.", "danger")
            return render_template("register.html")

        if not re.fullmatch(r"[A-Za-z][0-9]{5}", staff_no):
            flash("Staff No format must be 1 letter followed by 5 digits (example: A12345).", "danger")
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
                staff_no=staff_no
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
