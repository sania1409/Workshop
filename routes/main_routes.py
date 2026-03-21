import re
from flask import Blueprint, flash, render_template, request, session, redirect, url_for
from sqlalchemy import or_
from werkzeug.security import generate_password_hash
from extensions import db
from models import (
    Complaint,
    ComplaintLockerProfile,
    DeviceType,
    HardwareWorkshop,
    InternalDemandIssueVoucher,
    Location,
    ServiceMemo,
    TechnicianProfile,
    User,
    UserAuth,
)

main_routes = Blueprint("main_routes", __name__)
DEFAULT_LOCATIONS = ["head_office", "station", "workshop", "other"]
TECH_SKILL_OPTIONS = ["laptop", "desktop", "printer", "scanner", "network", "other"]


def _admin_required():
    return "user_id" in session and session.get("role") == "admin"


def _build_unique_username(email: str) -> str:
    base = (email.split("@")[0] or "user").strip().lower()
    candidate = base
    suffix = 1
    while User.query.filter_by(username=candidate).first():
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def _valid_password(password: str) -> bool:
    return bool(password) and len(password) >= 7 and re.search(r"[0-9\W_]", password)


def _get_locations():
    names = [l.name for l in Location.query.order_by(Location.name.asc()).all() if l.name]
    if names:
        return names
    return DEFAULT_LOCATIONS


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
    if not _admin_required():
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
    internal_demand_vouchers = (
        HardwareWorkshop.query
        .filter(HardwareWorkshop.item_description.isnot(None))
        .order_by(HardwareWorkshop.created_at.desc())
        .all()
    )
    voucher_groups = {}
    voucher_order = []
    for voucher in internal_demand_vouchers:
        key = voucher.complaint_no or "-"
        if key not in voucher_groups:
            voucher_groups[key] = []
            voucher_order.append(key)
        voucher_groups[key].append(voucher)
    internal_voucher_rows = [
        {"complaint_no": key, "items": voucher_groups[key]}
        for key in voucher_order
    ]
    return render_template(
        "admin_dashboard.html",
        pending_admin_memos=pending_admin_memos,
        completed_admin_memos=completed_admin_memos,
        internal_voucher_rows=internal_voucher_rows,
    )


@main_routes.route("/admin/internal-demand-vouchers/<int:complaint_id>", methods=["POST"])
def admin_upsert_internal_demand_voucher(complaint_id):
    if not _admin_required():
        return redirect(url_for("auth_routes.login"))

    complaint = Complaint.query.get_or_404(complaint_id)

    item_description = (request.form.get("item_description", "") or "").strip()
    quantity_issued_raw = (request.form.get("quantity_issued", "") or "").strip()
    remarks = (request.form.get("remarks", "") or "").strip() or None

    if not item_description:
        flash(f"Item description is required for complaint #{complaint.id}.", "danger")
        return redirect(url_for("main_routes.admin_dashboard"))

    try:
        quantity_issued = int(quantity_issued_raw)
    except ValueError:
        flash(f"Quantity issued must be a number for complaint #{complaint.id}.", "danger")
        return redirect(url_for("main_routes.admin_dashboard"))

    if quantity_issued <= 0:
        flash(f"Quantity issued must be greater than 0 for complaint #{complaint.id}.", "danger")
        return redirect(url_for("main_routes.admin_dashboard"))

    existing = InternalDemandIssueVoucher.query.filter_by(complaint_id=complaint.id).first()
    if existing:
        existing.item_description = item_description
        existing.quantity_issued = quantity_issued
        existing.remarks = remarks
        existing.created_by_admin_id = session["user_id"]
        flash(f"Voucher updated for complaint #{complaint.id}.", "success")
    else:
        db.session.add(
            InternalDemandIssueVoucher(
                complaint_id=complaint.id,
                item_description=item_description,
                quantity_issued=quantity_issued,
                remarks=remarks,
                created_by_admin_id=session["user_id"],
            )
        )
        flash(f"Voucher created for complaint #{complaint.id}.", "success")

    db.session.commit()
    return redirect(url_for("main_routes.admin_dashboard"))


@main_routes.route("/admin/manage-users")
def admin_manage_users():
    if not _admin_required():
        return redirect(url_for("auth_routes.login"))

    technicians = (
        User.query
        .filter(User.role == "technician")
        .order_by(User.full_name.asc(), User.username.asc())
        .all()
    )
    complaint_lockers = (
        User.query
        .filter(User.role == "complaint_locker")
        .order_by(User.full_name.asc(), User.username.asc())
        .all()
    )
    devices = DeviceType.query.order_by(DeviceType.name.asc()).all()
    locations = Location.query.order_by(Location.name.asc()).all()
    return render_template(
        "admin_manage_users.html",
        technicians=technicians,
        complaint_lockers=complaint_lockers,
        devices=devices,
        locations=locations,
        locker_location_options=_get_locations(),
        tech_skill_options=TECH_SKILL_OPTIONS,
    )


@main_routes.route("/admin/devices", methods=["POST"])
def admin_add_device():
    if not _admin_required():
        return redirect(url_for("auth_routes.login"))

    device_name = (request.form.get("device_name", "") or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_ -]{2,50}", device_name):
        flash("Device name must be 2-50 chars and use letters, numbers, spaces, '-' or '_'.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))

    if DeviceType.query.filter_by(name=device_name).first():
        flash("Device already exists.", "warning")
        return redirect(url_for("main_routes.admin_manage_users"))

    db.session.add(DeviceType(name=device_name))
    db.session.commit()
    flash("Device added.", "success")
    return redirect(url_for("main_routes.admin_manage_users"))


@main_routes.route("/admin/devices/<int:device_id>/delete", methods=["POST"])
def admin_delete_device(device_id):
    if not _admin_required():
        return redirect(url_for("auth_routes.login"))

    device = DeviceType.query.get_or_404(device_id)
    in_use = (
        Complaint.query.filter(Complaint.device_type == device.name).first()
        or ServiceMemo.query.filter(ServiceMemo.product_name == device.name).first()
    )
    if in_use:
        flash("Cannot remove device that is already used in complaints/memos.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))

    db.session.delete(device)
    db.session.commit()
    flash("Device removed.", "success")
    return redirect(url_for("main_routes.admin_manage_users"))


@main_routes.route("/admin/technicians", methods=["POST"])
def admin_add_technician():
    if not _admin_required():
        return redirect(url_for("auth_routes.login"))

    email = (request.form.get("email", "") or "").strip().lower()
    password = request.form.get("password", "") or ""
    full_name = (request.form.get("full_name", "") or "").strip() or None
    contact = (request.form.get("contact", "") or "").strip() or None
    skills = (request.form.get("skills", "") or "").strip().lower()
    staff_no = (request.form.get("staff_no", "") or "").strip().upper() or None

    if not email or not password or not skills:
        flash("Email, password, and skills are required for technician.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))
    if skills not in TECH_SKILL_OPTIONS:
        flash("Please select a valid technician skill from the dropdown.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))
    if not _valid_password(password):
        flash("Password must be at least 7 characters and include at least one number or special character.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))
    if staff_no and not re.fullmatch(r"[A-Za-z][0-9]{5}", staff_no):
        flash("Staff No format must be 1 letter followed by 5 digits (example: A12345).", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))
    if UserAuth.query.filter_by(email=email).first():
        flash("Email already exists.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))

    try:
        user = User(
            username=_build_unique_username(email),
            full_name=full_name,
            contact=contact,
            role="technician",
            designation=(request.form.get("designation", "") or "").strip() or None,
            department=(request.form.get("department", "") or "").strip() or None,
            staff_no=staff_no,
        )
        db.session.add(user)
        db.session.flush()

        db.session.add(UserAuth(
            user_id=user.id,
            email=email,
            password_hash=generate_password_hash(password),
        ))
        db.session.add(TechnicianProfile(
            user_id=user.id,
            skills=skills,
            availability_status="available",
            max_active_jobs=1,
        ))
        db.session.commit()
        flash("Technician added.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to add technician.", "danger")

    return redirect(url_for("main_routes.admin_manage_users"))


@main_routes.route("/admin/technicians/<int:user_id>/delete", methods=["POST"])
def admin_delete_technician(user_id):
    if not _admin_required():
        return redirect(url_for("auth_routes.login"))

    user = User.query.get_or_404(user_id)
    if user.role != "technician":
        flash("User is not a technician.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))

    active_complaints = Complaint.query.filter(
        Complaint.technician_id == user.id,
        or_(Complaint.status.in_(["open", "in_progress"]), Complaint.status.is_(None)),
    ).count()
    active_memos = ServiceMemo.query.filter(
        ServiceMemo.assigned_to == user.id,
        or_(ServiceMemo.task_performed.is_(False), ServiceMemo.task_performed.is_(None)),
    ).count()
    if active_complaints > 0 or active_memos > 0:
        flash("Cannot delete technician with active assigned work.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))

    try:
        TechnicianProfile.query.filter_by(user_id=user.id).delete()
        UserAuth.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        flash("Technician deleted.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to delete technician.", "danger")
    return redirect(url_for("main_routes.admin_manage_users"))


@main_routes.route("/admin/complaint-lockers", methods=["POST"])
def admin_add_complaint_locker():
    if not _admin_required():
        return redirect(url_for("auth_routes.login"))

    email = (request.form.get("email", "") or "").strip().lower()
    password = request.form.get("password", "") or ""
    full_name = (request.form.get("full_name", "") or "").strip() or None
    contact = (request.form.get("contact", "") or "").strip() or None
    staff_no = (request.form.get("staff_no", "") or "").strip().upper() or None
    location = (request.form.get("location", "") or "").strip().lower() or None

    if not email or not password:
        flash("Email and password are required for complaint locker.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))
    if not _valid_password(password):
        flash("Password must be at least 7 characters and include at least one number or special character.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))
    if staff_no and not re.fullmatch(r"[A-Za-z][0-9]{5}", staff_no):
        flash("Staff No format must be 1 letter followed by 5 digits (example: A12345).", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))
    if UserAuth.query.filter_by(email=email).first():
        flash("Email already exists.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))
    if location and location not in _get_locations():
        flash("Please select a valid complaint locker location from the dropdown.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))

    try:
        user = User(
            username=_build_unique_username(email),
            full_name=full_name,
            contact=contact,
            role="complaint_locker",
            designation=(request.form.get("designation", "") or "").strip() or None,
            department=(request.form.get("department", "") or "").strip() or None,
            staff_no=staff_no,
        )
        db.session.add(user)
        db.session.flush()

        db.session.add(UserAuth(
            user_id=user.id,
            email=email,
            password_hash=generate_password_hash(password),
        ))
        db.session.add(ComplaintLockerProfile(
            user_id=user.id,
            department=user.department,
            location=location,
        ))
        db.session.commit()
        flash("Complaint locker added.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to add complaint locker.", "danger")

    return redirect(url_for("main_routes.admin_manage_users"))


@main_routes.route("/admin/locations", methods=["POST"])
def admin_add_location():
    if not _admin_required():
        return redirect(url_for("auth_routes.login"))

    location_name = (request.form.get("location_name", "") or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_ -]{2,50}", location_name):
        flash("Location name must be 2-50 chars and use letters, numbers, spaces, '-' or '_'.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))

    if Location.query.filter_by(name=location_name).first():
        flash("Location already exists.", "warning")
        return redirect(url_for("main_routes.admin_manage_users"))

    db.session.add(Location(name=location_name))
    db.session.commit()
    flash("Location added.", "success")
    return redirect(url_for("main_routes.admin_manage_users"))


@main_routes.route("/admin/locations/<int:location_id>/delete", methods=["POST"])
def admin_delete_location(location_id):
    if not _admin_required():
        return redirect(url_for("auth_routes.login"))

    location = Location.query.get_or_404(location_id)
    if ComplaintLockerProfile.query.filter_by(location=location.name).first() or ServiceMemo.query.filter_by(location=location.name).first():
        flash("Cannot remove a location that is already in use.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))

    db.session.delete(location)
    db.session.commit()
    flash("Location removed.", "success")
    return redirect(url_for("main_routes.admin_manage_users"))


@main_routes.route("/admin/complaint-lockers/<int:user_id>/delete", methods=["POST"])
def admin_delete_complaint_locker(user_id):
    if not _admin_required():
        return redirect(url_for("auth_routes.login"))

    user = User.query.get_or_404(user_id)
    if user.role != "complaint_locker":
        flash("User is not a complaint locker.", "danger")
        return redirect(url_for("main_routes.admin_manage_users"))

    locker_profile = ComplaintLockerProfile.query.filter_by(user_id=user.id).first()
    if locker_profile:
        complaint_count = Complaint.query.filter_by(locker_id=locker_profile.id).count()
        if complaint_count > 0:
            flash("Cannot delete complaint locker with existing complaints.", "danger")
            return redirect(url_for("main_routes.admin_manage_users"))

    try:
        ComplaintLockerProfile.query.filter_by(user_id=user.id).delete()
        UserAuth.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        flash("Complaint locker deleted.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to delete complaint locker.", "danger")
    return redirect(url_for("main_routes.admin_manage_users"))


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
            or_(
                Complaint.status.in_(["open", "in_progress"]),
                Complaint.status.is_(None),
            ),
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
            or_(
                ServiceMemo.task_performed.is_(False),
                ServiceMemo.task_performed.is_(None),
            ),
            or_(
                ServiceMemo.diagnosed.is_(False),
                ServiceMemo.diagnosed.is_(None),
            ),
        )
        .order_by(ServiceMemo.last_updated.desc())
        .all()
    )
    diagnosed_service_memos = (
        ServiceMemo.query
        .filter(
            ServiceMemo.assigned_to == user_id,
            ServiceMemo.diagnosed.is_(True),
            or_(
                ServiceMemo.task_performed.is_(False),
                ServiceMemo.task_performed.is_(None),
            ),
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
        diagnosed_service_memos=diagnosed_service_memos,
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
