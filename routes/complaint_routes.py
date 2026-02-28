from datetime import datetime
import re
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from sqlalchemy import or_
from extensions import db
from models import Complaint, ComplaintLockerProfile, ServiceMemo, TechnicianProfile, User

complaint_routes = Blueprint("complaint_routes", __name__)
DEVICE_TYPES = ["laptop", "desktop", "printer", "scanner", "network", "other"]


def _get_or_create_locker_profile(user_id: int):
    locker = ComplaintLockerProfile.query.filter_by(user_id=user_id).first()
    if locker:
        return locker

    locker = ComplaintLockerProfile(user_id=user_id)
    db.session.add(locker)
    db.session.commit()
    return locker


def _to_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _skill_tokens(skills_text: str):
    if not skills_text:
        return []
    parts = re.split(r"[,;/\n]+", skills_text.lower())
    return [p.strip() for p in parts if p.strip()]


def _normalize_words(text: str):
    return [w for w in re.split(r"[^a-z0-9]+", (text or "").lower()) if w]


def _technician_active_load(user_id: int):
    complaint_load = Complaint.query.filter(
        Complaint.technician_id == user_id,
        Complaint.status.in_(["in_progress"]),
    ).count()
    memo_load = ServiceMemo.query.filter(
        ServiceMemo.assigned_to == user_id,
        ServiceMemo.task_performed.is_(False),
    ).count()
    return complaint_load + memo_load


def _pick_technician_for_task(device_type: str, task_text: str):
    task_text = (task_text or "").lower()
    tech_profiles = (
        TechnicianProfile.query
        .join(User, TechnicianProfile.user_id == User.id)
        .filter(User.role == "technician")
        .all()
    )

    best_user_id = None
    best_score = 0
    best_load = None
    device_aliases = {
        "laptop": {"laptop", "notebook"},
        "desktop": {"desktop", "computer", "pc"},
        "printer": {"printer"},
        "scanner": {"scanner"},
        "network": {"network", "lan", "wifi", "internet", "router", "switch"},
        "other": {"other"},
    }
    target_device_tokens = device_aliases.get(device_type, {device_type})

    for profile in tech_profiles:
        # Only offline technicians are excluded hard.
        if profile.availability_status == "offline":
            continue

        tokens = _skill_tokens(profile.skills)
        if not tokens:
            continue

        active_load = _technician_active_load(profile.user_id)
        max_jobs = profile.max_active_jobs or 1

        # Determine free/busy from live load (prevents stale status blocking assignment).
        if active_load >= max_jobs:
            profile.availability_status = "busy"
            continue
        profile.availability_status = "available"

        score = 0
        # Strong preference for explicit device match from dropdown.
        token_words = set()
        for token in tokens:
            token_words.update(_normalize_words(token))
        if token_words.intersection(target_device_tokens):
            score += 5

        for token in tokens:
            token_l = token.lower()
            if token_l in task_text:
                score += 1
                continue
            token_parts = _normalize_words(token_l)
            if token_parts and any(part in task_text for part in token_parts):
                score += 1

        if score <= 0:
            continue

        if score > best_score or (score == best_score and (best_load is None or active_load < best_load)):
            best_score = score
            best_load = active_load
            best_user_id = profile.user_id

    return best_user_id


def _pick_technician_for_complaint(title: str, description: str, device_type: str):
    complaint_text = f"{title or ''} {description or ''}"
    return _pick_technician_for_task(device_type=device_type, task_text=complaint_text)


def _refresh_technician_availability(user_id: int):
    profile = TechnicianProfile.query.filter_by(user_id=user_id).first()
    if not profile or profile.availability_status == "offline":
        return

    max_jobs = profile.max_active_jobs or 1
    active_load = _technician_active_load(user_id)
    profile.availability_status = "busy" if active_load >= max_jobs else "available"


# -----------------------------------
# Complaint Locker Dashboard Data
# -----------------------------------
@complaint_routes.route("/locker/complaints")
def locker_complaints():

    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    # Get locker profile
    locker = _get_or_create_locker_profile(session["user_id"])

    complaints = Complaint.query.filter_by(locker_id=locker.id).all()

    return render_template("locker_complaints.html", complaints=complaints)


# -----------------------------------
# Create New Complaint
# -----------------------------------
@complaint_routes.route("/locker/complaints/new", methods=["GET", "POST"])
def create_complaint():

    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    locker = _get_or_create_locker_profile(session["user_id"])

    if request.method == "POST":

        title = request.form.get("title")
        device_type = request.form.get("device_type", "").strip().lower()
        description = request.form.get("description")

        if not title or not description or device_type not in DEVICE_TYPES:
            flash("Title, device type, and description are required.", "danger")
            return render_template("new_complaint.html", device_types=DEVICE_TYPES)

        technician_id = _pick_technician_for_complaint(title, description, device_type)
        complaint = Complaint(
            locker_id=locker.id,
            technician_id=technician_id,
            title=title,
            device_type=device_type,
            description=description,
            status="in_progress" if technician_id else "open",
            assigned_at=datetime.utcnow() if technician_id else None,
        )

        db.session.add(complaint)
        if technician_id:
            _refresh_technician_availability(technician_id)
        db.session.commit()

        if technician_id:
            technician = User.query.get(technician_id)
            technician_name = (technician.full_name or technician.username) if technician else "Technician"
            flash(f"Complaint created and assigned to {technician_name}.", "success")
        else:
            flash("Complaint created. No technician skill match found yet.", "warning")
        return redirect(url_for("complaint_routes.locker_complaints"))

    return render_template("new_complaint.html", device_types=DEVICE_TYPES)


# -----------------------------------
# View Complaint
# -----------------------------------
@complaint_routes.route("/locker/complaints/<int:id>")
def view_complaint(id):

    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    locker = _get_or_create_locker_profile(session["user_id"])
    complaint = Complaint.query.get_or_404(id)

    if complaint.locker_id != locker.id:
        abort(403)

    return render_template("view_complaint.html", complaint=complaint)


# -----------------------------------
# Service Memo List
# -----------------------------------
@complaint_routes.route("/locker/service-memos")
def locker_service_memos():
    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    # Keep backward compatibility for old rows where created_by_user_id is NULL.
    memos = (
        ServiceMemo.query
        .filter(
            or_(
                ServiceMemo.created_by_user_id == session["user_id"],
                (ServiceMemo.created_by_user_id.is_(None) & (ServiceMemo.user_name == session.get("username")))
            )
        )
        .order_by(ServiceMemo.service_id.desc())
        .all()
    )
    return render_template("locker_service_memos.html", memos=memos)


# -----------------------------------
# Create Service Memo (Locker Input)
# -----------------------------------
@complaint_routes.route("/locker/service-memos/new", methods=["GET", "POST"])
def create_service_memo():
    if "user_id" not in session or session.get("role") != "complaint_locker":
        return redirect(url_for("auth_routes.login"))

    if request.method == "POST":
        complain_no = request.form.get("complain_no", "").strip()
        if not complain_no:
            flash("Complain number is required.", "danger")
            return render_template("new_service_memo.html")

        device_type = request.form.get("product_name", "").strip().lower()
        memo_text = " ".join([
            request.form.get("model", "").strip(),
            request.form.get("user_details", "").strip(),
            request.form.get("status", "").strip(),
        ])
        technician_id = _pick_technician_for_task(device_type=device_type, task_text=memo_text)

        memo = ServiceMemo(
            complain_no=complain_no,
            location=request.form.get("location", "").strip() or None,
            ext_no=request.form.get("ext_no", "").strip() or None,
            user_name=session.get("username"),
            created_by_user_id=session["user_id"],
            staff_no=request.form.get("staff_no", "").strip() or None,
            ip_address=request.form.get("ip_address", "").strip() or None,
            product_name=request.form.get("product_name", "").strip() or None,
            model=request.form.get("model", "").strip() or None,
            serial_no=request.form.get("serial_no", "").strip() or None,
            ram=request.form.get("ram", "").strip() or None,
            hdd=request.form.get("hdd", "").strip() or None,
            lniata=request.form.get("lniata", "").strip() or None,
            fault=("fault" in request.form),
            data_backup=("data_backup" in request.form),
            date_in=_to_date(request.form.get("date_in", "").strip()),
            status=request.form.get("status", "").strip() or "pending",
            user_details=request.form.get("user_details", "").strip() or None,
            diagnosed=False,
            date_out=None,
            task_performed=False,
            assigned_to=technician_id,
        )

        db.session.add(memo)
        if technician_id:
            _refresh_technician_availability(technician_id)
        db.session.commit()
        if technician_id:
            technician = User.query.get(technician_id)
            technician_name = (technician.full_name or technician.username) if technician else "Technician"
            flash(f"Service memo submitted and assigned to {technician_name}.", "success")
        else:
            flash("Service memo submitted. No technician skill match found yet.", "warning")
        return redirect(url_for("complaint_routes.locker_service_memos"))

    return render_template("new_service_memo.html")


# -----------------------------------
# Technician Updates Complaint Status
# -----------------------------------
@complaint_routes.route("/technician/complaints/<int:id>/status", methods=["POST"])
def technician_update_complaint_status(id):
    if "user_id" not in session or session.get("role") != "technician":
        return redirect(url_for("auth_routes.login"))

    complaint = Complaint.query.get_or_404(id)
    if complaint.technician_id != session["user_id"]:
        abort(403)

    new_status = request.form.get("status", "").strip()
    if new_status not in {"in_progress", "closed"}:
        flash("Invalid complaint status.", "danger")
        return redirect(url_for("main_routes.technician_dashboard"))

    complaint.status = new_status
    _refresh_technician_availability(session["user_id"])
    db.session.commit()
    flash("Complaint status updated.", "success")
    return redirect(url_for("main_routes.technician_dashboard"))


# -----------------------------------
# Technician Views/Diagnoses Service Memo
# -----------------------------------
@complaint_routes.route("/technician/service-memos/<int:service_id>", methods=["GET", "POST"])
def technician_view_service_memo(service_id):
    if "user_id" not in session or session.get("role") != "technician":
        return redirect(url_for("auth_routes.login"))

    memo = ServiceMemo.query.get_or_404(service_id)
    if memo.assigned_to != session["user_id"]:
        abort(403)

    if request.method == "POST":
        diagnosis_notes = request.form.get("diagnosis_notes", "").strip()
        if not diagnosis_notes:
            flash("Diagnosis notes are required.", "danger")
            return render_template("technician_view_service_memo.html", memo=memo)

        memo.diagnosis_notes = diagnosis_notes
        memo.diagnosed = True
        memo.status = "diagnosed"
        db.session.commit()
        flash("Memo diagnosed successfully.", "success")
        return redirect(url_for("main_routes.technician_dashboard"))

    return render_template("technician_view_service_memo.html", memo=memo)


# -----------------------------------
# Admin Reviews/Completes Service Memo
# -----------------------------------
@complaint_routes.route("/admin/service-memos/<int:service_id>", methods=["GET", "POST"])
def admin_view_service_memo(service_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("auth_routes.login"))

    memo = ServiceMemo.query.get_or_404(service_id)

    if request.method == "POST":
        admin_action_notes = request.form.get("admin_action_notes", "").strip()
        if not admin_action_notes:
            flash("Admin action notes are required.", "danger")
            return render_template("admin_view_service_memo.html", memo=memo)

        memo.admin_action_notes = admin_action_notes
        memo.task_performed = True
        memo.status = "completed"
        memo.date_out = datetime.utcnow().date()
        db.session.commit()

        if memo.assigned_to:
            _refresh_technician_availability(memo.assigned_to)
            db.session.commit()

        flash("Service memo marked as completed.", "success")
        return redirect(url_for("main_routes.admin_dashboard"))

    return render_template("admin_view_service_memo.html", memo=memo)
